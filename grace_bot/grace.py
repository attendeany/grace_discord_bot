import asyncio
import logging
import sqlite3
from collections import Counter
from typing import Optional

import discord
from grace_bot.application_commands import guild_app_commands_payload

log = logging.getLogger('grace_bot')
messages_per_level = 5

hello_message = {
    'content': 'Hello',
    'embed': discord.Embed(description='Ahhh!')
}


async def KickMember(guild: discord.Guild, member_id, reason=None):
    if not guild.me.guild_permissions.kick_members:
        return 'Мне необходимо право кикать участников'

    try:
        await guild.kick(discord.Object(int(member_id)), reason=reason)
    except discord.Forbidden:
        return 'Мне запрещено выгонять этого участника'
    except discord.HTTPException:
        log.exception(f'Cannot kick user from {guild} with {member_id=}')
    else:
        return f'Пользователь <@{member_id}> выгнан.'

    return 'Что-то пошло не так'


async def BanMember(guild: discord.Guild, member_id, reason=None):
    if not guild.me.guild_permissions.kick_members:
        return 'Мне необходимо право банить участников'

    try:
        await guild.ban(discord.Object(int(member_id)), reason=reason, delete_message_days=0)
    except discord.Forbidden:
        return 'Мне запрещено банить этого участника'
    except discord.HTTPException:
        log.exception(f'Cannot ban user from {guild} with {member_id=}')
    else:
        return f'Пользователь <@{member_id}> забанен.'
    return 'Что-то пошло не так'


async def UnbanMember(guild: discord.Guild, user_name: str, reason=None):
    if not guild.me.guild_permissions.kick_members:
        return 'Мне необходимо право банить участников'

    target = None
    for ban_entry in await guild.bans():
        if user_name in str(ban_entry):
            if target:
                return f'Найдено более одного участника с именем {user_name}. Уточните ваш запрос'
            target = ban_entry.user
    if not target:
        return f'Не удалось найти {user_name} в списке забаненных пользователей'

    try:
        await guild.unban(target, reason=reason)
    except discord.HTTPException:
        log.exception(f'Cannot unban {target} from {guild}')
    else:
        return f'Пользователь {target.mention} разбанен.'
    return 'Что-то пошло не так'


class GraceDatabase:
    def __init__(self):
        self.database = sqlite3.connect('data/grace.db')
        self.cursor = self.database.cursor()

        self.cursor.execute('PRAGMA foreign_keys = ON')
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id INTEGER UNIQUE            
            )
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS member_activity (
                guild_id INTEGER,
                member_id INTEGER,
                messages INTEGER,
                FOREIGN KEY (guild_id)
                    REFERENCES guilds (guild_id)
                        ON DELETE CASCADE
            )
            """
        )
        self.database.commit()

    def __del__(self):
        self.database.close()

    @property
    def guilds(self) -> list[int]:
        return list(i[0] for i in self.cursor.execute('SELECT guild_id FROM guilds').fetchall())

    def Save(self, user_activity: dict[int, Counter[int, int]]):
        all_guilds = self.guilds
        for new_guild in (i for i in user_activity if i not in all_guilds):
            self.cursor.execute('INSERT INTO guilds (guild_id) VALUES (?)', (new_guild,))

        payloads = []
        for guild_id, activity_data in user_activity.items():
            guild_users: set[int] = set(i[0] for i in self.cursor.execute(
                'SELECT member_id FROM member_activity WHERE guild_id=?', (guild_id,)).fetchall())

            for user_id, messages in activity_data.items():
                if user_id not in guild_users:
                    # new member
                    self.cursor.execute(
                        'INSERT INTO member_activity (guild_id, member_id, messages) VALUES (?, ?, ?)',
                        (guild_id, user_id, messages))
                else:
                    # existing member
                    payloads.append((messages, guild_id, user_id))

        self.cursor.executemany(
            'UPDATE member_activity SET messages=? WHERE guild_id=? AND member_id=?', payloads)
        self.database.commit()

    def Load(self) -> dict[int, Counter[int, int]]:
        all_guilds = self.guilds

        user_activity = {}
        for guild_id in all_guilds:
            user_activity[guild_id] = Counter(dict(
                self.cursor.execute(
                    'SELECT member_id, messages FROM member_activity WHERE guild_id=?', (guild_id,)).fetchall()
            ))

        return user_activity


class GraceBot:

    def __init__(self, client: discord.Client):
        self.client = client

        self.database = GraceDatabase()
        self.user_activity = self.database.Load()

        self.event_channels: dict[int, discord.TextChannel] = {}

    def __del__(self):
        self.database.Save(self.user_activity)
        log.info('Good bye!')

    def AnyTextChannelIn(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        if not (any_channel := self.event_channels.get(guild.id)):
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    self.event_channels[guild.id] = channel
                    any_channel = channel
                    break
            else:
                log.warning(f'Cannot access to text channels in {guild}')
                return

        return any_channel

    async def RegisterGuildApplicationCommands(self, guild: discord.Guild):
        log.info(f'Registering {guild} application commands')
        try:
            await self.client.http.bulk_upsert_guild_commands(
                self.client.application_id, guild.id, guild_app_commands_payload)
        except discord.DiscordException as e:
            log.exception(f'Cannot set {guild} application commands!')
            if guild_channel := self.AnyTextChannelIn(guild):

                class TryAgainView(discord.ui.View):
                    def __init__(self, grace_logic):
                        super().__init__(timeout=None)
                        self.grace_logic: GraceBot = grace_logic
                        self.guild = guild

                    @discord.ui.button(label='Попробовать снова', custom_id='recreate_guild_cmds')
                    async def TryAgain(self, button, interaction: discord.Interaction):
                        self.stop()
                        if await self.grace_logic.RegisterGuildApplicationCommands(self.guild):
                            await interaction.response.send_message('Успешно')
                        else:
                            await interaction.response.send_message('Неудачно')

                await guild_channel.send(
                    'Не могу создать команды для текущего сервера',
                    embed=discord.Embed(description=str(e)[:4000]), view=TryAgainView(self))
        else:
            return True
        return False

    async def SaveLoop(self):
        log.info('Starging save loop')
        while True:
            await asyncio.sleep(60)
            self.database.Save(self.user_activity)

    async def OnReady(self):
        for guild in self.client.guilds:
            await self.RegisterGuildApplicationCommands(guild)
        asyncio.ensure_future(self.SaveLoop())

    async def OnMessage(self, message: discord.Message):
        if message.guild.id not in self.user_activity:
            self.user_activity[message.guild.id] = Counter()

        guild_counter = self.user_activity[message.guild.id]
        guild_counter[message.author.id] += 1

        member_message_count = guild_counter.get(message.author.id)
        if member_message_count % messages_per_level == 0:

            if use_channel := message.channel if message.channel.permissions_for(
                    message.guild.me).send_messages else self.AnyTextChannelIn(message.guild):
                await use_channel.send(
                    f'{message.author.mention}\nПоздравляем! Вы достигли '
                    f'{int(member_message_count / messages_per_level)} уровня!')

            self.database.Save(self.user_activity)

    async def OnInteraction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.application_command:
            return

        data = interaction.data
        command_name = data['name']
        log.info(f"Got {command_name} {interaction.guild} application command")

        if command_name == 'help':
            await interaction.response.send_message(**hello_message)
            return

        require_perm = ''
        if command_name in ('kick', 'Kick User') and not interaction.permissions.kick_members:
            require_perm = 'выгонять участников'
        elif command_name in ('ban', 'Ban User') and not interaction.permissions.ban_members:
            require_perm = 'банить участников'

        if require_perm:
            await interaction.response.send_message(
                f'У вас должно быть право {require_perm}, чтобы использовать эту команду.')
            return

        reason = f"{interaction.user} {command_name} command"

        if command_name == 'unban':
            user_name = data['options'][0]['value']
            await interaction.response.send_message(await UnbanMember(interaction.guild, user_name, reason))
            return

        if data.get('type', 1) == 2:
            # User application command
            user_id = int(data.get('target_id'))
        else:
            # Text application command
            user_id = int(data['options'][0]['value'])

        return_message = 'Неизвестная команда'
        if command_name in ('ban', 'Ban User'):
            return_message = await BanMember(interaction.guild, user_id, reason)
        elif command_name in ('kick', 'Kick User'):
            return_message = await KickMember(interaction.guild, user_id, reason)

        await interaction.response.send_message(return_message)

    async def OnGuildJoin(self, guild: discord.Guild):
        await self.RegisterGuildApplicationCommands(guild)

    async def OnVoiceStateUpdate(
            self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel == after.channel:
            return

        notify_content = ''
        if before.channel:
            # user left voice channel
            notify_content = f'{member.display_name} left {before.channel.mention}'

        if after.channel:
            # user connected to voice channel
            if before.channel:
                notify_content = f'{member.display_name} left {before.channel.mention} ' \
                                 f'and connected to the {after.channel.mention}'
            else:
                notify_content = f'{member.display_name} connected to the {after.channel.mention}'

        if notify_channel := self.AnyTextChannelIn(member.guild):
            await notify_channel.send(notify_content)
