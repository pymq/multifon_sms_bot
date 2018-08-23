import configparser
import datetime
import json
from functools import partial

from bs4 import BeautifulSoup
from matrix_bot_api.matrix_bot_api import MatrixBotAPI
from matrix_bot_api.mregex_handler import MRegexHandler
from mistune import markdown

from api_selenium import UmsConnection
from models import User, Profile, CurrentProfile
from utils import have_access, send_exception

config = configparser.ConfigParser()
config.read('config.ini')
bot_username = config.get('Bot', 'username')
bot_password = config.get('Bot', 'password')
server_url = config.get('Bot', 'server_url')

BOT = MatrixBotAPI(bot_username, bot_password, server_url)

# [(Profile, UmsConnection), ]
CONNECTIONS = []

with open('whitelist_users.txt') as f:
    whitelist = [i.strip() for i in f]

private_access = have_access(usernames=whitelist)

# TODO декоратор is_authorized

markdown = partial(markdown, hard_wrap=True)
with open('bot_help.md', 'r') as f:
    HELP = markdown(f.read())


def hi_callback(room, event):
    room.send_text("Hi, " + event['sender'])


@private_access
@send_exception
def help_callback(room, event):
    room.send_html(HELP)


@private_access
@send_exception
def list_chats_callback(room, event):
    username = event['sender']
    connection = get_current_connection(username)
    if not connection or connection and not connection.is_authorized:
        room.send_text('Отказано. Вы не авторизованы.')
        return

    args = event['content']['body'].split()
    number = args[1] if len(args) >= 2 else 10
    response = connection.get_chat_list(number)
    soup = BeautifulSoup(response, 'xml')
    answer = ''
    for i, msisdn in enumerate(soup.find_all(name='MSISDN'), start=1):
        answer += f'**{str(i)}.** {msisdn.text}\n'
    room.send_html(markdown(answer))


def get_current_connection(username):
    user = User.get_or_create(username=username)[0]
    current_profile = CurrentProfile.get_or_none(user=user)
    if current_profile:
        connection = next(
            (tuple[1] for tuple in CONNECTIONS if tuple[0].owner == user and tuple[0].name == current_profile.profile.name), None)
        return connection
    else:
        return None

def get_current_profile(username):
    user = User.get_or_create(username=username)[0]
    current_profile = CurrentProfile.get_or_none(user=user)
    if current_profile:
        profile = next(
            (tuple[0] for tuple in CONNECTIONS if tuple[0].owner == user and tuple[0].name == current_profile.profile.name), None)
        return profile
    else:
        return None


@private_access
@send_exception
def print_chat_callback(room, event):
    username = event['sender']
    connection = get_current_connection(username)
    if not connection or connection and not connection.is_authorized:
        room.send_text('Отказано. Вы не авторизованы.')
        return

    args = event['content']['body'].split()
    if len(args) < 2:
        room.send_text('Не указано имя диалога')
        return
    adress = args[1]
    number = args[2] if len(args) >= 3 else 10
    response = connection.get_one_box(adress, number=number)
    soup = BeautifulSoup(response, 'xml')
    answer = f'# {adress}\n'
    for i, msg in enumerate(reversed(soup.find_all(name='uniMsg')), start=1):
        dt = msg.find('t').text
        date = datetime.datetime(int(dt[:4]), int(dt[4:6]), int(dt[6:8]), int(dt[8:10]), int(dt[10:12]), int(dt[12:14]))
        answer += f"**{date}** **{msg.find('snd').text}** — {msg.find('ttl').text}\n"
    room.send_html(markdown(answer))


@private_access
@send_exception
def add_or_update_profile_callback(room, event):
    username = event['sender']
    args = event['content']['body'].split()
    profile_name = args[1]
    profile_phone = args[2]
    profile_password = args[3]
    # TODO проверка, есть ли уже профиль с введенными данными.
    # TODO Если есть - вывести сообщение и return
    user = User.get_or_create(username=username)[0]
    profile = Profile.get_or_none(Profile.owner == user, Profile.name == profile_name)
    if profile:
        profile.phone_number = profile_phone
        profile.password = profile_password
        profile.save()
    else:
        profile = Profile.create(owner=user, name=profile_name, phone_number=profile_phone, password=profile_password)
    current_profile = CurrentProfile.get_or_none(user=user)
    if current_profile:
        current_profile.profile = profile
        current_profile.save()
    else:
        current_profile = CurrentProfile.create(user=user, profile=profile)
    connection = UmsConnection(profile_phone, profile_password)
    CONNECTIONS.append((profile, connection))
    captcha = connection.get_captcha()
    url = BOT.client.upload(captcha, 'image/png')
    room.send_text('Профиль добавлен, введите капчу командой captcha <key>')
    room.send_image(url, 'captcha.png')


@private_access
@send_exception
def enter_captcha_callback(room, event):
    username = event['sender']
    connection = get_current_connection(username)
    if connection and connection.is_authorized:
        room.send_text('Не предоставлены данные профиля, либо ввод капчи не требуется')
        return
    key = event['content']['body'].split()[1]
    if connection.send_captcha_key(key):
        room.send_text('Капча подошла, замечательно!')
        user = User.get_or_create(username=username)[0]
        current_profile = CurrentProfile.get_or_none(user=user)
        current_profile.profile.cookies_json = connection.get_cookies_json()
        current_profile.profile.save()
    else:
        room.send_text('Увы, попробуйте ещё раз')
        captcha = connection.get_captcha()
        url = BOT.client.upload(captcha, 'image/png')
        room.send_image(url, 'captcha.png')

@private_access
@send_exception
def get_captcha_callback(room, event):
    username = event['sender']
    connection = get_current_connection(username)
    if connection and connection.is_authorized:
        room.send_text('Не предоставлены данные профиля, либо ввод капчи не требуется')
        return
    captcha = connection.get_captcha()
    url = BOT.client.upload(captcha, 'image/png')
    room.send_image(url, 'captcha.png')


@private_access
@send_exception
def list_profiles_callback(room, event):
    username = event['sender']
    user = User.get_or_none(username=username)
    if not user:
        room.send_text('У вас отсутствуют профили')
    profiles = Profile.select().where(Profile.owner == user)
    answer = ''
    for profile in profiles:
        answer += f"**{profile.name}:** {profile.phone_number} {profile.password}\n"
    if answer:
        room.send_html(markdown(answer))
    else:
        room.send_text('У вас отсутствуют профили')


@private_access
@send_exception
def get_current_profile_callback(room, event):
    username = event['sender']
    user = User.get_or_create(username=username)[0]
    profile = CurrentProfile.get_or_none(user=user)
    if profile:
        answer = f"**{profile.profile.name}:** {profile.profile.phone_number} {profile.profile.password}"
        room.send_html(markdown(answer))
    else:
        room.send_text('У вас не выбран текущий профиль')


@private_access
@send_exception
def select_profile_callback(room, event):
    username = event['sender']
    args = event['content']['body'].split()
    profile_name = args[1]
    user = User.get_or_create(username=username)[0]
    profile = Profile.get_or_none(owner=user, name=profile_name)
    if profile:
        current_profile = CurrentProfile.get_or_none(user=user)
        if current_profile:
            current_profile.profile = profile
            current_profile.save()
        else:
            current_profile = CurrentProfile.create(user=user, profile=profile)
        answer = f"Выбран профиль **{profile.name}:** {profile.phone_number} {profile.password}"
        room.send_html(markdown(answer))
    else:
        room.send_text(f'У вас отсутствует профиль {profile_name}')


@private_access
@send_exception
def remove_profile_callback(room, event):
    username = event['sender']
    # TODO сделать закрытие соединений при удалении профиля
    args = event['content']['body'].split()
    profile_name = args[1]
    user = User.get_or_create(username=username)[0]
    profile = Profile.get_or_none(owner=user, name=profile_name)
    if profile:
        answer = f"Удалён профиль **{profile.name}:** {profile.phone_number} {profile.password}"
        profile.delete_instance()
        room.send_html(markdown(answer))
    else:
        room.send_text(f'У вас отсутствует профиль {profile_name}')


def main():
    profiles = Profile.select()
    for profile in profiles:
        cookies = json.loads(profile.cookies_json) if profile.cookies_json else None
        conn = UmsConnection(profile.phone_number, profile.password, cookies)
        CONNECTIONS.append((profile, conn))

    hi_handler = MRegexHandler("hi", hi_callback)
    BOT.add_handler(hi_handler)

    help_handler = MRegexHandler("^(help|h)$", help_callback)
    BOT.add_handler(help_handler)

    list_chats_handler = MRegexHandler("^list$", list_chats_callback)
    BOT.add_handler(list_chats_handler)

    print_chat_handler = MRegexHandler("^print [\w\.\+]+ ?\d*$", print_chat_callback)
    BOT.add_handler(print_chat_handler)

    add_or_update_profile_handler = MRegexHandler("^profile \w+ \d+ \w+$", add_or_update_profile_callback)
    BOT.add_handler(add_or_update_profile_handler)

    list_profiles_handler = MRegexHandler("^profiles$", list_profiles_callback)
    BOT.add_handler(list_profiles_handler)

    get_current_profile_handler = MRegexHandler("^profile$", get_current_profile_callback)
    BOT.add_handler(get_current_profile_handler)

    select_profile_handler = MRegexHandler("^select \w+$", select_profile_callback)
    BOT.add_handler(select_profile_handler)

    remove_profile_handler = MRegexHandler("^remove \w+$", remove_profile_callback)
    BOT.add_handler(remove_profile_handler)

    enter_captcha_handler = MRegexHandler("^captcha \w+$", enter_captcha_callback)
    BOT.add_handler(enter_captcha_handler)

    get_captcha_handler = MRegexHandler("^captcha$", get_captcha_callback)
    BOT.add_handler(get_captcha_handler)

    BOT.start_polling()

    # Infinitely read stdin to stall main thread while the bot runs in other threads
    while True:
        input()


if __name__ == "__main__":
    main()
