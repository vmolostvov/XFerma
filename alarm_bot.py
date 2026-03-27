# -*- coding: utf-8 -*-
import telebot, os
import time
import traceback
from threading import Thread
from telebot import apihelper
from config import get_random_proxy6
from dotenv import load_dotenv

# загружаем переменные из .env
load_dotenv()

LOGS_ERRORS_BOT = os.getenv("TG_LOGS_AND_ERRORS_BOT_TOKEN")
NOTIFY_BOT = os.getenv("TG_NOTIFICATIONS_BOT_TOKEN")
SCREEN_BOT = os.getenv("TG_SCREEN_BOT_TOKEN")


chat_ids = {
    'listing_channel_name': '@TheFastestListing1',
    'chat_id': '680688412',
    'chat_id_ver': '518092938',
    'chat_id_max': '1484918886',
    'chat_id_papa': '329004924',
    'channel_id': '-1001587760342',
    'test_bot_users': 'test_bot_users',
    'bot_users': 'bot_users',
    'test_chat_id': '1796817955',
    'test_channel_id': '-1001319220760',
    'cryptowebaudit_ch': '1946026959'
}


def get_bot_with_proxy(bot_name):
    apihelper.proxy = {
        'https': f'http://{get_random_proxy6()}'
    }

    return telebot.TeleBot(bot_name)

def admin_signal(exception_text, times=20):
    bot = get_bot_with_proxy(NOTIFY_BOT)
    while True:
        try:
            for i in range(times):
                bot.send_message(chat_ids['chat_id'], exception_text, parse_mode='html')
                time.sleep(1.5)
            return
        except:
            pass


def admin_error(exception_text):
    bot = get_bot_with_proxy(LOGS_ERRORS_BOT)
    for i in range(3):
        try:
            if len(exception_text) > 4095:
                for x in range(0, len(exception_text), 4095):
                    bot.send_message(chat_ids['chat_id'], text=exception_text[x:x + 4095])
            else:
                bot.send_message(chat_ids['chat_id'], exception_text)
            return
        except:
            print(traceback.format_exc())


def admin_signal_th(text):
    t = Thread(target=admin_signal, args=(text,))
    t.start()


def send_ss_tg(user, path_to_photo, text):
    bot = get_bot_with_proxy(SCREEN_BOT)
    for i in range(3):
        try:
            with open(path_to_photo, 'rb') as photo:
                bot.send_photo(user, photo=photo, caption=text, parse_mode='html')
            break
        except Exception:
            if 'PHOTO_INVALID_DIMENSIONS' in traceback.format_exc():
                time.sleep(15)