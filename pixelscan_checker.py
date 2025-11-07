import requests, base64
from urllib.parse import urlparse, urlunparse

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

def proxy_check(proxy_string: str, url: str, timeout: float = 15.0):
    info = parse_proxy_string(proxy_string)
    proxies = build_proxy_dict(info)
    auth_header = make_proxy_auth_header(info["username"], info["password"])
    headers["Proxy-Authorization"] = auth_header

    print("== Proxy info ==")
    print(f" proxy_url: {info['proxy_url']}")
    print(f" username: {info['username']!r}")
    print(f" password: {'***' if info['password'] else None}")
    print()

    try:
        print(f"-> GET {url} via proxy (timeout {timeout}s)")
        resp = requests.get(url, headers=headers, proxies=proxies, timeout=timeout)
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

    # Выводим результат
    print("== Result ==")
    print("status_code:", resp.status_code)
    print("elapsed:", resp.elapsed)

    analyze = resp.json()

    print("proxy_ip:", analyze['ip'])
    print("proxy_score:", analyze['score'])
    print("proxy_quality:", analyze['quality'])

    return {
        "ok": True,
        "status_code": resp.status_code,
        "elapsed": resp.elapsed.total_seconds(),
        "proxy_ip": analyze['ip'],
        "proxy_score": analyze['score'],
        "proxy_quality": analyze['quality']
    }


if __name__ == '__main__':
    pixelscan_url = 'https://936665286.extension.pixelscan.net/'
    proxy_str = 'http://vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-865a112cf3f84-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080'
    proxy_check(proxy_str, pixelscan_url)

