from account_auth import TwitterFrontendFlow
from twitter_search import user_friendship


def login(un, pw, proxy):
    flow = TwitterFrontendFlow.TwitterFrontendFlow(proxies=proxy)
    flow.login_flow()
    flow.LoginJsInstrumentationSubtask()

    print(f"login to twitter account {un}")
    while "LoginSuccessSubtask" not in flow.get_subtask_ids():
        try:
            if "LoginEnterUserIdentifierSSO" in flow.get_subtask_ids():
                print("Telephone number / Email address / User name")
                print(un)
                flow.LoginEnterUserIdentifierSSO(un)
            elif "LoginEnterAlternateIdentifierSubtask" in flow.get_subtask_ids():
                print(flow.content["subtasks"][0]["enter_text"]["primary_text"]["text"])
                flow.LoginEnterAlternateIdentifierSubtask(input())
            elif "LoginEnterPassword" in flow.get_subtask_ids():
                print(flow.content["subtasks"][0]["enter_password"]["primary_text"]["text"])
                print(pw)
                flow.LoginEnterPassword(pw)
            elif "AccountDuplicationCheck" in flow.get_subtask_ids():
                print("AccountDuplicationCheck")
                flow.AccountDuplicationCheck()
            elif "LoginTwoFactorAuthChallenge" in flow.get_subtask_ids():
                header = flow.content["subtasks"][0]["enter_text"]["header"]
                print(header["primary_text"]["text"])
                flow.LoginTwoFactorAuthChallenge(input())
            elif "LoginAcid" in flow.get_subtask_ids():
                header = flow.content["subtasks"][0]["enter_text"]["header"]
                print(header["secondary_text"]["text"])
                flow.LoginAcid(input())
            elif "SuccessExit" in flow.get_subtask_ids():
                break
            else:
                print("Non-supported login methods: " + flow.get_subtask_ids())
                exit(1)
        except:
            print("Error")

    print("Success")
    flow.SaveCookies('test_cookie.json')


if __name__ == '__main__':
    proxy = 'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-acbeddd763fd2-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080'
    proxy = {
        "http": f"http://{proxy}",
        "https": f"http://{proxy}"
    }
    username = 'armyjattsunny'
    password = 'kvzQStMLnB'
    login(username, password, proxy)