import time, traceback, telebot
from seleniumbase import SB
from alarm_bot import admin_error


def login(username, password, user_agent, proxy):
    with SB(uc=True, xvfb=True, headed=True, agent=user_agent, proxy=proxy) as sb:
        try:
            sb.uc_open_with_reconnect('https://x.com/i/flow/login')
            sb.wait_for_element_visible("input[name='text']", timeout=20).send_keys(username)
            time.sleep(1)
            sb.uc_gui_press_key('ENTER')
            sb.wait_for_element_visible("input[name='password']").send_keys(password)
            time.sleep(1)
            sb.uc_gui_press_key('ENTER')

            sb.wait_for_element_visible("a[href='/home']")

            print('logged in')

            print(sb.get_cookies())
        except:
            web_audit_vip_user_message_with_photo_test('680688412', sb.driver.get_screenshot_as_png(),
                                                       'log 1')


def web_audit_vip_user_message_with_photo_test(user, photo, text):
    WebAuditBot = telebot.TeleBot('6408330846:AAFZLrHOqaTYveAlbeO8CzNdth_fTrbRGac')
    for i in range(3):
        try:
            WebAuditBot.send_photo(user, photo=photo, caption=text, parse_mode='html')
            break
        except:
            admin_error(traceback.format_exc())
            time.sleep(2)

if __name__ == '__main__':
    login('ganusarkate1993', 'lG64q29V0N', 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1', 'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-dc1d0ac669594-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080')