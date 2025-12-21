from playwright.sync_api import sync_playwright
import json

proxy = "HMP5Cn:G3rW3F@95.164.128.166:9967"
proxy_username_password, proxy_ip_port = proxy.split("@")
proxy_username, proxy_password = proxy_username_password.split(":")

account = "Christi25399674:JVJPumvfDhwoG96:snmzramzila@outlook.com:bW555B12:5511959822361:auth_token=a25d4ae35f443c99b2a80697c90cfd1e4e478f9f"
twitter_screen_name, twitter_password, email, email_password, email_phone, cookie = account.split(":")
auth_token = cookie.split("=")[1] # f092968b2a8c159d8b36c7b16983b270bfddd2b4

################################################################################################################################################

with sync_playwright() as playwright:
    chromium = playwright.chromium # "chromium" or "firefox" or "webkit"
    browser = chromium.launch(
		headless=False,
        proxy={
            "server": proxy_ip_port,
            "username": proxy_username,
			"password": proxy_password
        }
    )
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    context.add_cookies([{'name': 'auth_token', 'value': auth_token, 'domain': 'twitter.com', 'path': '/'}])
    
    page = context.new_page()
    response = page.goto("https://twitter.com/")
    page.wait_for_timeout(5000)
    response = page.goto("https://twitter.com/")
    page.wait_for_timeout(10000)
    page_content = page.content()
    page_cookies = page.context.cookies()
    
    with open(f"{twitter_screen_name}.json", "w") as f:
        json.dump(page_cookies, f)
		
    with open(f"{twitter_screen_name}.txt", "w") as f:	
        f.write(f"""{{
            # {account}
            'screen_name': '{twitter_screen_name}',
            'password': '{twitter_password}',
            'proxy': '{proxy}'
        }}""")
    
    # other actions...
    browser.close()
