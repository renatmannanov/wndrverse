"""
Delivery channels. MVP: stdout. Telegram channels are stubs (extension point).
"""


def send(text: str, *, channel: str = "stdout") -> None:
    """Send ready text to a channel.

    MVP: 'stdout'. Future: 'telegram_group', 'telegram_dm'.
    """
    if channel == "stdout":
        print(text)
    elif channel in ("telegram_group", "telegram_dm"):
        raise NotImplementedError(f"channel '{channel}' is a future feature")
    else:
        raise ValueError(f"unknown channel: {channel}")
