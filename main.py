import logging
import os
import sys

import discord
from grace_bot.grace import GraceBot

log_level = logging.INFO

log = logging.getLogger('grace_bot')
log.setLevel(log_level)

# log handler
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(
    logging.Formatter(f'[%(asctime)s | %(funcName)s | %(levelname)s]: %(message)s', datefmt='%d.%m.%Y %H:%M:%S'))
log.addHandler(handler)


if __name__ == '__main__':

    intents = discord.Intents(
        guilds=True,
        members=True,
        emojis_and_stickers=True,
        voice_states=True,
        messages=True
    )

    permissions = discord.Permissions(
        administrator=True,
        read_messages=True,
        send_messages=True,
        embed_links=True,
        read_message_history=True,
        external_emojis=True,
        send_messages_in_threads=True,
        kick_members=True,
        ban_members=True
    )

    bot_token = os.getenv('token')
    if not bot_token:
        log.warning("Set the 'token' environment variable!")
        sys.exit(1)

    client = discord.Client(intents=intents, max_messages=500)

    bot_logic = GraceBot(client)

    @client.event
    async def on_ready():
        log.info(f'Logged as {client.user}')
        log.info(f"OAuth url: {discord.utils.oauth_url(str(client.user.id), permissions=permissions, scopes=('bot', 'applications.commands'))}")
        await bot_logic.OnReady()

    @client.event
    async def on_message(message):
        if message.author == client.user:
            return
        await bot_logic.OnMessage(message)

    @client.event
    async def on_interaction(interaction):
        await bot_logic.OnInteraction(interaction)

    @client.event
    async def on_guild_join(guild):
        await bot_logic.OnGuildJoin(guild)

    @client.event
    async def on_voice_state_update(member, before, after):
        await bot_logic.OnVoiceStateUpdate(member, before, after)

    try:
        client.run(bot_token)
    except discord.LoginFailure:
        log.exception('Invalid bot_token!')
