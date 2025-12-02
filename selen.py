import time, traceback, telebot, pyautogui, os
from alarm_bot import admin_error
import asyncio, pyperclip
from seleniumbase import cdp_driver
# from seleniumbase import decorators
# from seleniumbase import sb_cdp
from seleniumbase import SB

from twitter_search import parse_tweets_instructions


def login(username, password, proxy):
    # pyperclip.copy(username)
    try:
        with SB(uc=True, xvfb=True, proxy=proxy) as sb:
            sb.activate_cdp_mode("https://x.com/i/flow/login")
            # sb.wait_for_element_visible("input[name='text']", timeout=30)
            # sb.uc_gui_press_keys('ganusarkate199' + '3')
            # sb.cdp.
            # sb.uc_gui_press_keys(username)
            # time.sleep(10)
            # time.sleep(1)
            # os.system("""osascript -e 'tell application "System Events" to keystroke "v" using command down'""")
            # sb.cdp.gui_write(username)
            sb.write("input[name='text']", username, timeout=30)
            print('Entered the un!')
            sb.sleep(1)
            # sb.cdp.gui_click_with_offset("input[name='text']", 30, 20, timeframe=1)
            # sb.click("input[name='text']", timeout=30)
            # for i in range(10):
            #     try:
            #         sb.cdp.gui_click_element("input[name='texfghganusarkate1993t']")
            #     except:
            #         continue
            # time.sleep(100)
            # login_input = sb.wait_for_element_visible("input[name='text']", timeout=3000)
            # login_input.send_keys(username)
            # login_input = sb.wait_for_element_visible("input[name='teerfxt']", timeout=3000)
            sb.sleep(1)
            next_button = sb.cdp.find_element('Next', best_match=True)
            # sb.cdp.gui_press_key('ENTER')
            # sb.uc_gui_press_key('ENTER')
            next_button.click()
            print('Clicked on "Next" button!')
            sb.sleep(1)
            # sb.uc_gui_press_key('ENTER')
            # for i in range(3):
            #     try:
            #         sb.cdp.gui_click_with_offset("input[name='password']", 30, 20, timeframe=1)
            #     except:
            #         continue
            #
            # time.sleep(1)
            # sb.cdp.gui_write(password)
            sb.write("input[name='password']", password, timeout=20)
            print('Entered the pw!')

            next_button = sb.cdp.find_element('Enter', best_match=True)
            next_button.click()
            print('Clicked on "Enter" button!')

            # sb.wait_for_element_visible("input[name='password']").send_keys(password)
            # sb.sleep(1)
            # sb.cdp.gui_press_key('ENTER')
            # sb.uc_gui_press_key('ENTER')

            sb.cdp.open_new_tab('https://x.com/home')
            try:
                sb.cdp.click('div[aria-label="Post text"]', timeout=10)
            except:
                pass
            sb.get('https://x.com/home')

            try:
                sb.cdp.click('div[aria-label="Post text"]', timeout=20)
                # home = sb.cdp.find_element('div[aria-label="Post text"]', timeout=20)
                print('logged in')
                # print(sb.get_cookies()) # 'ad62c41319a26a159917e17868b0a3110cb372a9'
                auth_token = next(c['value'] for c in sb.get_cookies() if c['name'] == 'auth_token')
                return auth_token

            except:
                print(traceback.format_exc())
                print('not logged in')

    except:
        trace = traceback.format_exc()
        print(trace)
        admin_error(trace)
        # web_audit_vip_user_message_with_photo_test('680688412', sb.driver.get_screenshot_as_png(),
        #                                            'log 1')


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
    print(login('keshavc75728566', 'Hjxv3wn87P', 'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-399a85c38e684-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080'))
