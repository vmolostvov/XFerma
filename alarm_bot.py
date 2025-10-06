# -*- coding: utf-8 -*-
import telebot
import time
import traceback
from threading import Thread


bot = telebot.TeleBot('1722063746:AAGKg6kL5ynWfu4Gp55Jsj1EkMzmj7lWvu4')
announce_bot = telebot.TeleBot('6166495322:AAEAKpgemGy5a7TpXJ38qUJqTw4lVcy5N1s')


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



def admin_signal(exception_text, times=20):
    while True:
        try:
            for i in range(times):
                bot.send_message(chat_ids['chat_id'], exception_text, parse_mode='html')
                time.sleep(1.5)
            return
        except:
            pass


def admin_error(exception_text):
    for i in range(3):
        try:
            if len(exception_text) > 4095:
                for x in range(0, len(exception_text), 4095):
                    announce_bot.send_message(chat_ids['chat_id'], text=exception_text[x:x + 4095])
            else:
                announce_bot.send_message(chat_ids['chat_id'], exception_text)
            return
        except:
            print(traceback.format_exc())


def admin_signal_th(text):
    t = Thread(target=admin_signal, args=(text,))
    t.start()
