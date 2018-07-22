import traceback
from functools import wraps
from typing import List


def have_access(usernames: List[str] = None, servers: List[str] = None):
    def decorator(func):
        @wraps(func)
        def wrapped(room, event):
            username = event['sender']
            servername = username.split(':')[1]
            if usernames and username in usernames:
                return func(room, event)
            if servers and servername in servers:
                return func(room, event)

        return wrapped

    return decorator


def send_exception(func):
    @wraps(func)
    def wrapped(room, event):
        try:
            func(room, event)
        except Exception:
            traceback.print_exc()
            room.send_text(traceback.format_exc())

    return wrapped
