import time

import requests, contextlib, json
from typing import Any, Dict, List, Optional, Set
import asyncio
from cdp_sniffer import sniff_headers, SniffMatch
from multiprocessing import Process, Queue

# FOLDER = "inbox"
# TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
# # PROXIES = {"http": "socks5://user:pass@host:port", "https": "socks5://user:pass@host:port"}
# CLIENT_ID = "8b4ba9dd-3ea5-4e5f-86f1-ddba2230dcf2"
# REFRESH_TOKEN = "M.C557_BAY.0.U.-CgCmeAr6JYwKNhNbbTs9xUYA3nOoUR7R2E!aDc3aUIMlkWzS6S45I15gk8sIAE7c0IOqdEWLMGM1QiFMB4JDiK*aoKHsB79g1pG6xDPBjXFicoge*QqBHI6sRVjtCJD8IIv8YQEN9WsskLNPu4ra5rCHTihEKFzQARwzRa95Hsu0IQiysVqnG5bT6xGxvg6P1xX9z2Fyg1I0tKuTnZdgXCB8!gb6GWJAUiKcrYtK9zrXKlMKq1YguTf*fW2YoWpXt9fZs2lhc8*XCc6pWDdB6XmEVgl7r2aYBGpHwuCROn6*5BkS2OFvqfB7A9uZuEkq!ntqaF!WhngAmycsdelo1kHL8fYNOO*QK42Uo9uh1u6FVlRBiY7huu*r9bSa70p8JgFg7PnsM6l7OUMuwMzRdjo$"
#
# # Obtain access_token via refresh_token for Microsoft Graph scopes.
# payload = {"client_id": CLIENT_ID,
#            "grant_type": "refresh_token",
#            "refresh_token": REFRESH_TOKEN,
#            "scope": "https://graph.microsoft.com/.default"}
# headers = {"Content-Type": "application/x-www-form-urlencoded"}
# # response = requests.post(TOKEN_URL, data=payload, headers=headers, proxies=PROXIES)
# r = requests.post(TOKEN_URL, data=payload, headers=headers)
# print(r.status_code, r.text)
# r.raise_for_status()
# access_token = r.json()["access_token"]
#
# # Read messages from Inbox using Microsoft Graph API access.
# url = f"https://graph.microsoft.com/v1.0/me/mailFolders/{FOLDER}/messages"
# headers = {"Authorization": f"Bearer {access_token}"}
# # response = requests.get(url, headers=headers, proxies=PROXIES)
# response = requests.get(url, headers=headers)
# messages = response.json().get("value", [])
#
# # Print messages
# for msg in messages:
#     print(f"From: {msg.get('from', {}).get('emailAddress', {}).get('address')}")
#     print(f"Subject: {msg.get('subject')}")
#     print(f"Body: {msg.get('body', {}).get('content', '')}")


# CLIENT_ID = "8b4ba9dd-3ea5-4e5f-86f1-ddba2230dcf2"
# TENANT = "common"  # или ваш tenant id
# AUTHORITY = f"https://login.microsoftonline.com/{TENANT}"
# SCOPES = ["Mail.Read"]  # можно добавить User.Read
#
# CACHE_FILE = "msal_cache.bin"
#
# cache = msal.SerializableTokenCache()
# if os.path.exists(CACHE_FILE):
#     cache.deserialize(open(CACHE_FILE, "r").read())
#
# app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY, token_cache=cache)
#
# accounts = app.get_accounts()
# result = None
# if accounts:
#     result = app.acquire_token_silent(SCOPES, account=accounts[0])
#
# if not result:
#     flow = app.initiate_device_flow(scopes=SCOPES)
#     if "user_code" not in flow:
#         raise RuntimeError("Failed to create device flow: " + json.dumps(flow, indent=2))
#     print(flow["message"])  # тут будет код и ссылка
#     result = app.acquire_token_by_device_flow(flow)
#
# if "access_token" not in result:
#     raise RuntimeError("Token error: " + json.dumps(result, indent=2))
#
# # сохранить кэш (там и refresh внутри)
# open(CACHE_FILE, "w").write(cache.serialize())
#
# access_token = result["access_token"]
#
# r = requests.get(
#     "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?$top=10",
#     headers={"Authorization": f"Bearer {access_token}"}
# )
# print(r.status_code, r.text[:500])

headers = {
    "action": "FindConversation",
        "authorization": 'MSAuth1.0 usertoken="EwAYBOl3BAAU0wDjFA6usBY8gB2LLZHCr9gRQlcAAdWmxjdDlThI589zrde4Vhxhl+x8vofRIVRWV96qXx1/zmmmDoI1fQC/hi3fn0qnyjSjULElnAKt8uoONQ4lIM4wHvMa0+xQqICycZrAeSi/46ZC41J9LU/wR7+w1TtY5i7IbBUkWoODJo/iuf7LNFUr5Kdp3XMPnXbndUwBj2mH1Wh7aP2nm+Vy5COXoLoLMkLym6sqyOI5mOGlhjRD2Qbbh+h2eKfuOGrLa83czZY4+HvUdJM0P5iBU3bGYk819eNeYeHtCT8aOPgp64U0AdzvNgAppAc140HN+7X/1F7GLPpvRsZvY1QX9MwaQMta270+l6Lx98P6dIOMeCJMIVgQZgAAEJaofl1NBqFYMmtCPF9/wkHgAk+LBpE6EtwckknKSBTmcXm9vtZBEvRz2rrAhmh9RqZfQ4EqWWU/HFHaIHNbvpDhXhQ2p32lDpvADG4szI9vZt19W8D4z/f+N+ubQEafHMg2h++V5vmgwX4eUrbVUaRrRvaEyL7XOzBn+CiY7B3Gq4P5D9uet9O/TL4gKLw1YHY15u9T7KvHZqxqPOQSrHZxiurAZdOlJTmAscDohVR1HBrcXp3K7uJKNoGg9kKUp0/fbd41vLWF+QeV2+ZZBpT4b36jmSLjMZ77VIw/ecbIuN8uYL6rs6K6vaeipQhaRk6fq02VoLjkuTXMdP2/07SyzPiEBSO3CmY7vZdkAb1WXoZQgjuzl1WLXlzSJO9tUJIw17quj94lwp9E+g844L3eQs0OGfGpovVZx7CnWGBV8MQCH6wTk+blqLaR51b/QXlh/JHJcs5tRwmAcKSWBMSbv42P1BKo7M5BsHZ4niA5FMJLW0eNlb5EohR+9kIZo822kDgKp0aapH4bzOtF1cPSrvG3TpFPC8RnQLEbhT1nObJzf7fvTrJMJRKdBlJEtJiAcz+frV1tk/wQetGpKXc7jCjl+PUOLOXGINDPIqYo1b3eTFkAi9cO73eLAN/U5/zUSi1RmS3VFfJXjGJ3MUEHTMqHwAJhngxsss2XQJCjDFDJ82MWUFxV3YroPtOXGpGt3L4jrbstTcJGh2AuABi/9Fa6Vo4/df7J+NmmYl7UTq4wo7jDOzfVpC1rdHtIlfdO7F7+sapHDGFIhM4ExZUKDc2IFlryEqbXl1tUMN8OndhCnUUcoSh4O0J1gbG49IacVIYVmbLC2FE8XPQPgHNhcJqOVdcKjhNF8ZgVi6Hffz3f060tZoE8dkiEq912paepTrm7zJKTjUPcMmQVObUWBIyAsFX2T3nZQKhkqNb3SapLiQByfBL0QeWWKHZB0nW2Pg2Btd50XekZZGdVCdeyb2ACWD88MmLb7/hQCYM9vCYlAw==", type="MSACT"',    "content-type": "application/json; charset=utf-8",
    "ms-cv": "VzA+K5UlJP9LL/Md/8qeAE.91",
    "prefer": "IdType=\"ImmutableId\", exchange.behavior=\"IncludeThirdPartyOnlineMeetingProviders\"",
    "referer": "",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        "x-anchormailbox": "PUID:00030001A2FB52C0@84df9e7f-e9f6-40af-b435-aaaaaaaaaaaa",
    "x-owa-correlationid": "1269eda0-8250-837f-c6af-11b36335c1c3",
    "x-owa-hosted-ux": "false",
    "x-owa-sessionid": "ec82502a-6ef7-4173-8696-629810eb101b",
        "x-owa-urlpostdata": "%7B%22__type%22%3A%22FindConversationJsonRequest%3A%23Exchange%22%2C%22Header%22%3A%7B%22__type%22%3A%22JsonRequestHeaders%3A%23Exchange%22%2C%22RequestServerVersion%22%3A%22V2018_01_08%22%2C%22TimeZoneContext%22%3A%7B%22__type%22%3A%22TimeZoneContext%3A%23Exchange%22%2C%22TimeZoneDefinition%22%3A%7B%22__type%22%3A%22TimeZoneDefinitionType%3A%23Exchange%22%2C%22Id%22%3A%22FLE%20Standard%20Time%22%7D%7D%7D%2C%22Body%22%3A%7B%22ParentFolderId%22%3A%7B%22__type%22%3A%22TargetFolderId%3A%23Exchange%22%2C%22BaseFolderId%22%3A%7B%22__type%22%3A%22FolderId%3A%23Exchange%22%2C%22Id%22%3A%22AQMkADAwATMwMAExLWEyZmItNTJjMC0wMAItMDAKAC4AAANRbf4cKBw%2FRLZMGKmLYGbjAQAQgNI1LCr3SbPco4el3cAIAAACAQwAAAA%3D%22%7D%7D%2C%22ConversationShape%22%3A%7B%22__type%22%3A%22ConversationResponseShape%3A%23Exchange%22%2C%22BaseShape%22%3A%22IdOnly%22%7D%2C%22ShapeName%22%3A%22ReactConversationListView%22%2C%22Paging%22%3A%7B%22__type%22%3A%22IndexedPageView%3A%23Exchange%22%2C%22BasePoint%22%3A%22Beginning%22%2C%22Offset%22%3A0%2C%22MaxEntriesReturned%22%3A25%7D%2C%22ViewFilter%22%3A%22All%22%2C%22SortOrder%22%3A%5B%7B%22__type%22%3A%22SortResults%3A%23Exchange%22%2C%22Order%22%3A%22Descending%22%2C%22Path%22%3A%7B%22__type%22%3A%22PropertyUri%3A%23Exchange%22%2C%22FieldURI%22%3A%22ConversationLastDeliveryOrRenewTime%22%7D%7D%2C%7B%22__type%22%3A%22SortResults%3A%23Exchange%22%2C%22Order%22%3A%22Descending%22%2C%22Path%22%3A%7B%22__type%22%3A%22PropertyUri%3A%23Exchange%22%2C%22FieldURI%22%3A%22ConversationLastDeliveryTime%22%7D%7D%5D%2C%22FocusedViewFilter%22%3A0%2C%22SearchFolderId%22%3A%7B%22__type%22%3A%22FolderId%3A%23Exchange%22%2C%22Id%22%3A%22AQMkADAwATMwMAExLWEyZmItNTJjMC0wMAItMDAKAC4AAANRbf4cKBw%2FRLZMGKmLYGbjAQAQgNI1LCr3SbPco4el3cAIAAACPiwAAAA%3D%22%7D%7D%7D",
    "x-req-source": "Mail"
}

def parse_exchange_conversations_min(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse OWA/Exchange response and keep only:
    - title/topic
    - sender (name/email)
    - time (LastDeliveryTime)
    - preview
    - total unread count (sum of UnreadCount)
    - total message count (sum of MessageCount)
    """
    body = payload.get("Body", {}) or {}
    conversations = body.get("Conversations", []) or []

    items: List[Dict[str, Any]] = []
    total_unread = 0
    total_messages = 0

    for c in conversations:
        unread = int(c.get("UnreadCount") or 0)
        msg_count = int(c.get("MessageCount") or 0)

        total_unread += unread
        total_messages += msg_count

        mailbox = (c.get("LastSender") or {}).get("Mailbox") or {}
        sender = {
            "name": mailbox.get("Name"),
            "email": mailbox.get("EmailAddress"),
        }

        items.append({
            "title": c.get("ConversationTopic"),
            "sender": sender,
            "time": c.get("LastDeliveryTime"),   # можно заменить на LastSentTime, если нужно
            "preview": c.get("Preview"),
            "unread": unread,
            "messages": msg_count,
        })

    return {
        "items": items,
        "total_unread": total_unread,
        "total_messages": total_messages,
    }

def get_messages():
    res = requests.post('https://outlook.live.com/owa/0/service.svc?action=FindConversation&app=Mail&n=91', headers=headers)
    return parse_exchange_conversations_min(res.json())


def check_avail_un(un_to_check):

    outlook_h = load_outlook_headers()
    headers_canary = outlook_h['canary']
    headers_cookie = outlook_h['cookie']

    headers = {
        "accept": "application/json",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "ru-RU,ru;q=0.9",
        "cache-control": "no-cache",
        "canary": headers_canary,
        "client-request-id": "ecab7b9117d77cb753ac1ce4fe7b4db6",
        "connection": "keep-alive",
        "content-length": "143",
        "content-type": "application/json; charset=utf-8",
        "cookie": headers_cookie,
        "correlationid": "ecab7b9117d77cb753ac1ce4fe7b4db6",
        "host": "signup.live.com",
        "hpgact": "0",
        "hpgid": "200225",
        "origin": "https://signup.live.com",
        "pragma": "no-cache",
        "referer": "https://signup.live.com/signup?sru=https%3a%2f%2flogin.live.com%2foauth20_authorize.srf%3flc%3d1049%26client_id%3d9199bf20-a13f-4107-85dc-02114787ef48%26cobrandid%3dab0455a0-8d03-46b9-b18b-df2f57b9e44c%26mkt%3dRU-RU%26opid%3d5CB2EBA2E6FA06B3%26opidt%3d1767697482%26uaid%3decab7b9117d77cb753ac1ce4fe7b4db6%26contextid%3d402E075F99619CAB%26opignore%3d1&mkt=RU-RU&uiflavor=web&lw=1&fl=dob%2cflname%2cwld&cobrandid=ab0455a0-8d03-46b9-b18b-df2f57b9e44c&client_id=9199bf20-a13f-4107-85dc-02114787ef48&uaid=ecab7b9117d77cb753ac1ce4fe7b4db6&suc=9199bf20-a13f-4107-85dc-02114787ef48&fluent=2&lic=1",
        "sec-ch-ua": "\"Chromium\";v=\"142\", \"Google Chrome\";v=\"142\", \"Not_A Brand\";v=\"99\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"macOS\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    }

    data = {"includeSuggestions": True, "signInName": f"{un_to_check}@outlook.com", "uiflvr": 1001, "scid": 100118,
            "uaid": "7f545ae303fad124560c092458670f1d", "hpgid": 200225}

    for i in range(5):
        res = requests.get('https://signup.live.com/API/CheckAvailableSigninNames', json=data, headers=headers)
        content = res.json()

        try:
            if res.status_code == 200 and content['apiCanary']:
                return content.get('isAvailable')
        except KeyError:
            if i == 2:
                new_outlook_headers = get_canary_key_outlook_mp()
                headers['canary'] = new_outlook_headers['canary']
                headers['cookie'] = new_outlook_headers['cookie']


def get_canary_key_outlook(
    timeout: int = 60,
    out_file: str = "outlook_headers.json",
) -> Dict[str, str]:
    """
    Waits until all watched headers are found or timeout expires.
    Saves them to JSON and returns dict like:
    {"canary": "...", "cookie": "..."}
    """

    watch: Set[str] = {"canary", "cookie"}
    found: Dict[str, str] = {}
    done_event = asyncio.Event()

    def on_match(m: SniffMatch):
        nonlocal found

        for k, v in m.matched.items():
            # сохраняем первое найденное значение
            if k not in found:
                found[k] = v
                print(f"[FOUND] {k} = {v[:80]}...")

        # если нашли всё — сигналим завершение
        if watch.issubset(found.keys()):
            done_event.set()

    async def runner():
        sniff_task = asyncio.create_task(
            sniff_headers(
                url="https://signup.live.com/signup",
                watch=watch,
                duration=timeout,
                only_types={"xhr", "fetch"},
                on_match=on_match,
                # print_all_requests=True
            )
        )

        try:
            await asyncio.wait_for(done_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            print("[WARN] Timeout reached, returning partial result")
        finally:
            sniff_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sniff_task

        # ---- ЗАПИСЬ В JSON ----
        if found:
            payload = {
                "source": "outlook_signup",
                "headers": found,
            }
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

        return found

    return asyncio.run(runner())

def get_canary_key_outlook_worker(q):
    res = get_canary_key_outlook()
    q.put(res)

def get_canary_key_outlook_mp():
    q = Queue()
    p = Process(target=get_canary_key_outlook_worker, args=(q,))
    p.start()
    p.join(timeout=60)

    if p.is_alive():
        p.terminate()

    return q.get()


def load_outlook_headers(
    path: str = "outlook_headers.json",
) -> Dict[str, Optional[str]]:
    """
    Loads outlook headers from JSON file.

    Returns:
        {
            "canary": str | None,
            "cookie": str | None
        }
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        headers = data.get("headers", {})
        return {
            "canary": headers.get("canary"),
            "cookie": headers.get("cookie"),
        }

    except FileNotFoundError:
        print(f"[ERROR] File not found: {path}")
    except json.JSONDecodeError:
        print(f"[ERROR] Invalid JSON in: {path}")
    except Exception as e:
        print(f"[ERROR] Failed to read {path}: {e}")

    return {
        "canary": None,
        "cookie": None,
    }

if __name__ == '__main__':
    print(get_canary_key_outlook_mp())