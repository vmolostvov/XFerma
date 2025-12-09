import requests, base64, time, string, random
from urllib.parse import urlparse, urlunparse
from config import nodemaven_proxy_pw, nodemaven_proxy_port, nodemaven_proxy_login, nodemaven_proxy_server

headers = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Cookie": "_ga_ZH1CYL80NM=GS2.1.s1762500194$o1$g1$t1762500411$j60$l0$h0; _ga=GA1.1.322639361.1762500194",
    "Host": "936665286.extension.pixelscan.net",
    "Priority": "u=4",
    "proxy-authorization": "",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:144.0) Gecko/20100101 Firefox/144.0"
}

pixelscan_url = 'https://1936645286.extension.pixelscan.net/'

def parse_proxy_string(ps: str):
    """
    Разбирает строку прокси и возвращает dict:
    {
      "scheme": "http" or "https",
      "host": "gate.nodemaven.com",
      "port": 8080,
      "username": "...",  # может быть None
      "password": "...",  # может be None
      "proxy_url": "http://user:pass@host:port"
    }
    """
    parsed = urlparse(ps)
    if not parsed.scheme:
        # если пользователь дал без схемы, предположим http
        parsed = urlparse("http://" + ps)

    username = parsed.username
    password = parsed.password
    host = parsed.hostname
    port = parsed.port
    scheme = parsed.scheme

    # Собираем proxy_url включая креды, чтобы requests понимал proxy auth
    netloc = ""
    if username and password:
        netloc = f"{username}:{password}@{host}"
    else:
        netloc = host
    if port:
        netloc = f"{netloc}:{port}"

    proxy_url = urlunparse((scheme, netloc, "", "", "", ""))

    return {
        "scheme": scheme,
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "proxy_url": proxy_url,
        "raw_parsed": parsed,
    }

def build_proxy_dict(proxy_info):
    # requests expects proxy URL for both http and https (if you want to proxy HTTPS)
    p = proxy_info["proxy_url"]
    return {"http": p, "https": p}

def make_proxy_auth_header(username, password):
    if username is None or password is None:
        return None
    pair = f"{username}:{password}".encode()
    b64 = base64.b64encode(pair).decode()
    return f"Basic {b64}"

def proxy_check(proxy_string: str, timeout: float = 15.0, triple_check: bool = False):
    """
    Проверяет прокси через PixelScan.
    Если triple_check=True — выполняет до 3 попыток,
    но только в случае неуспеха предыдущей проверки.
    """

    def _single_check():
        info = parse_proxy_string(proxy_string)
        proxies = build_proxy_dict(info)
        auth_header = make_proxy_auth_header(info["username"], info["password"])
        headers["Proxy-Authorization"] = auth_header

        print("== Proxy info ==")
        print(f" proxy_url: {info['proxy_url']}")
        print(f" username: {info['username']!r}")
        print(f" password: {'***' if info['password'] else None}\n")

        try:
            print(f"-> GET {pixelscan_url} via proxy (timeout {timeout}s)")
            resp = requests.get(pixelscan_url, headers=headers, proxies=proxies, timeout=timeout)
        except requests.exceptions.ProxyError as e:
            print("ProxyError:", e)
            return {"ok": False, "error": "proxy_error", "exception": str(e)}
        except requests.exceptions.ConnectTimeout as e:
            print("ConnectTimeout:", e)
            return {"ok": False, "error": "timeout", "exception": str(e)}
        except requests.exceptions.SSLError as e:
            print("SSLError:", e)
            return {"ok": False, "error": "ssl_error", "exception": str(e)}
        except Exception as e:
            print("Other error:", e)
            return {"ok": False, "error": "other", "exception": str(e)}

        print("== Result ==")
        print("status_code:", resp.status_code)
        print("elapsed:", resp.elapsed)

        try:
            analyze = resp.json()
        except Exception:
            return {"ok": False, "error": "invalid_json"}

        print("proxy_ip:", analyze.get('ip'))
        print("proxy_score:", analyze.get('score'))
        print("proxy_quality:", analyze.get('quality'))

        return {
            "ok": True,
            "status_code": resp.status_code,
            "elapsed": resp.elapsed.total_seconds(),
            "proxy_ip": analyze.get('ip'),
            "proxy_score": analyze.get('score'),
            "proxy_quality": analyze.get('quality')
        }

    # --- Первая проверка ---
    result = _single_check()

    # Если всё ок — сразу возвращаем
    if result["ok"] or not triple_check:
        return result

    # --- Повторные попытки (максимум 2 дополнительно) ---
    print("\n❗ Proxy failed — starting triple-check mode...\n")

    for attempt in range(2):   # 2 доп. попытки = всего 3
        print(f"🔁 Retry attempt {attempt + 2}/3...\n")
        time.sleep(10)
        new_result = _single_check()

        if new_result["ok"]:
            return new_result

        result = new_result

    return result  # последний результат (неуспешный)


def get_proxy_by_sid(sid):
    return f"{nodemaven_proxy_login.format(sid)}:{nodemaven_proxy_pw}@{nodemaven_proxy_server}:{nodemaven_proxy_port}"


def generate_valid_sid_nodemaven_proxy(length=13):
    hex_chars = string.hexdigits.lower()
    while True:
        sid = ''.join(random.choice(hex_chars) for _ in range(length))
        proxy_analyze = proxy_check(make_proxy_str_for_pixelscan(get_proxy_by_sid(sid)))
        if proxy_analyze['ok'] and proxy_analyze['proxy_quality'] == 'high':
            return sid

def make_proxy_str_for_pixelscan(proxy):
    return f"http://{proxy}"


if __name__ == '__main__':
    # proxy_str = 'http://vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-d0d8eb5c9c0b4-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080'
    # proxy_check(proxy_str)
    print(generate_valid_sid_nodemaven_proxy())
