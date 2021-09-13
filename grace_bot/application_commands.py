guild_app_commands_payload = [
    {
        'name': 'help',
        'description': 'Вывести приветствие бота',
        'type': 1,
    },
    {
        'name': 'kick',
        'description': 'Выгнать пользователя',
        'type': 1,
        'options': [
            {
                'type': 6,
                'name': 'user',
                'description': 'пользователь, которого вы хотите выгнать',
                'required': True
            }
        ]
    },
    {
        'name': 'ban',
        'description': 'Забанить пользователя',
        'type': 1,
        'options': [
            {
                'type': 6,
                'name': 'user',
                'description': 'пользователь, которого вы хотите забанить',
                'required': True
            }
        ]
    },
    {
        'name': 'unban',
        'description': 'Разбанить пользователя',
        'type': 1,
        'options': [
            {
                'type': 3,
                'name': 'user_name',
                'description': 'имя пользователя, которого вы хотите разбанить (чувствительно к регистру)',
                'required': True
            }
        ]
    },
    {
        'name': 'Kick User',
        'description': '',
        'type': 2,
    },
    {
        'name': 'Ban User',
        'description': '',
        'type': 2,
    }
]
