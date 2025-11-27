import time
from seleniumbase import SB


def login(username, password, user_agent, proxy):
    with SB(uc=True, xvfb=True, headed=True, agent=user_agent, proxy=proxy) as sb:
        sb.uc_open('https://x.com/i/flow/login')
        input()
        sb.wait_for_element_visible("input[name='text']", timeout=20).send_keys(username)
        time.sleep(1)
        sb.uc_gui_press_key('ENTER')
        sb.wait_for_element_visible("input[name='password']").send_keys(password)
        time.sleep(1)
        sb.uc_gui_press_key('ENTER')

        sb.wait_for_element_visible("a[href='/home']")

        print('logged in')

        print(sb.get_cookies())

if __name__ == '__main__':
    login('ganusarkate1993', 'lG64q29V0N', 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1', 'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-dc1d0ac669594-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080')