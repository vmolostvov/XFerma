import time, traceback, telebot, pyautogui, os
from alarm_bot import admin_error
import asyncio, pyperclip
from seleniumbase import cdp_driver
# from seleniumbase import decorators
# from seleniumbase import sb_cdp
from seleniumbase import SB


def login(username, password, user_agent, proxy):
    pyperclip.copy(username)
    try:
        with SB(uc=True, xvfb=True, headed=True, agent=user_agent, proxy=proxy, locale_code='en') as sb:
            sb.activate_cdp_mode("https://x.com/i/flow/login")
            # sb.wait_for_element_visible("input[name='text']", timeout=30)
            for i in range(3):
                try:
                    sb.cdp.gui_click_with_offset("input[name='text']", 30, 20, timeframe=1)
                except:
                    continue


            # sb.uc_gui_press_keys('ganusarkate199' + '3')
            # sb.cdp.
            # sb.uc_gui_press_keys(username)
            # time.sleep(10)
            os.system("""osascript -e 'tell application "System Events" to keystroke "v" using command down'""")
            for i in range(10):
                try:
                    sb.cdp.gui_click_element("input[name='texfghganusarkate1993t']")
                except:
                    continue
            # time.sleep(100)
            # login_input = sb.wait_for_element_visible("input[name='text']", timeout=3000)
            # login_input.send_keys(username)
            # login_input = sb.wait_for_element_visible("input[name='teerfxt']", timeout=3000)
            next_button = sb.find_element_by_text('Next', tag_name='button')
            next_button.uc_click()
            # sb.sleep(1000)
            # sb.uc_gui_press_key('ENTER')
            sb.wait_for_element_visible("input[name='password']").send_keys(password)
            time.sleep(100)

        # sb = sb_cdp.Chrome('https://x.com/i/flow/login', headed=True, proxy=proxy)
        # driver = await cdp_driver.start_async()
        # tab = await driver.get('https://x.com/i/flow/login')
        # login_input = await tab.select("input[name='text']", timeout=30)
        # await login_input.send_keys_async(username)
        # await asyncio.sleep(1)
        # next_button = await tab.find_element_by_text('Next', best_match=True)
        # await next_button.click_async()
        # time.sleep(100)

        # sb.wait_for_element_visible("input[name='password']").send_keys(password)
        # time.sleep(1)
        # sb.uc_gui_press_key('ENTER')
        #
        # sb.wait_for_element_visible("a[href='/home']")

        print('logged in')

        # print(sb.get_cookies())
    except:
        # pass
        admin_error(traceback.format_exc())
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

# if __name__ == '__main__':
#     login('ganusarkate1993', 'lG64q29V0N', 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1', 'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-dc1d0ac669594-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080')


async def main():
    driver = await cdp_driver.start_async(proxy="vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-dc1d0ac669594-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080")
    print("Opening first page")
    tab = await driver.get("https://seleniumbase.io/simple/login")
    # await asyncio.sleep(1000)
    # web_audit_vip_user_message_with_photo_test('680688412', driver.(, 'log 1')
    print("Finding an element")
    h4 = await tab.select("h4")
    print(h4.text)
    await asyncio.sleep(2)
    print("Opening second page")
    tab = await driver.get("https://seleniumbase.io/demo_page")
    print("Finding an element")
    h1 = await tab.select("h1")
    print(h1.text)
    await asyncio.sleep(2)

if __name__ == "__main__":
    # Call an async function with awaited methods
    # loop = asyncio.new_event_loop()
    # with decorators.print_runtime("Async Example"):
    #     loop.run_until_complete(login('ganusarkate1993', 'lG64q29V0N', 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1', 'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-dc1d0ac669594-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080'))
    login('harshvardhan145', '472j1u2oKQ', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0', 'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-5daef2b226f74-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080')