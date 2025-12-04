import random, re, aiohttp, string

# database

DB_HOST_SERVER = 'localhost'
DB_HOST_LOCAL = '185.247.18.169'
DB_PORT = 5432
DB_USERNAME = 'postgres'
DB_PASSWORD = 'Opg123opg'
DB_BASE_NAME = 'postgres'

# nodemaven mob proxy

nodemaven_mob_proxy_data = [
    'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-7e0aa42c8bf74-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080',
    'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-7e0aa42c8bf74-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080',
    'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-f50f436a6d254-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080',
    'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-2089aa239acf4-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080',
    'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-7f147d809be54-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080',
    'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-e15b6e1ee97c4-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080',
    'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-7370b9d3403f4-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080',
    'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-3f9fa76581f04-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080',
    'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-6c8d9de51d764-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080',
    'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-1672614f767b4-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080',
    'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-540010aa5aac4-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080'
]

nodemaven_api_key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzYyNTI0ODU3LCJpYXQiOjE3NjI1MjMwNTcsImp0aSI6IjNkNmE4NWEwMmYyOTQ0MTZhYmNiODE4ZjRmMGU1NTc3IiwidXNlcl9pZCI6IjAyN2Y5MGU0LTc3NTYtNDU2OS04NmEzLTU4MDczZmM3YTAxMSJ9.i9TDxfHW9smd_fBYqz-XpbWVMVpqHlnux-na2Zdld4o'

nodemaven_proxy_rotating = {'http': 'https://vmolostvov96_gmail_com-country-any-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080', 'https': 'http://vmolostvov96_gmail_com-country-any-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080/'}

# proxy config mobile ipv4 us
nodemaven_proxy_server = 'gate.nodemaven.com'
nodemaven_proxy_port = '8080'
nodemaven_proxy_login = 'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-{}-filter-medium'
# nodemaven_proxy_login = 'https://vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-3e85cb8c21534-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080'
# nodemaven_proxy_login = 'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-64bc6e4fc5d64-filter-medium'
# nodemaven_proxy_login = 'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-7d0a575e412a4-filter-medium'
nodemaven_proxy_pw = 'e3ibl6cpq4'


def generate_password(length=20):
    # Define allowed characters (letters, digits, and specific symbols)
    chars = string.ascii_letters + string.digits + "!@$%^&*()_-+"

    # Generate password by choosing random characters
    password = ''.join(random.choice(chars) for _ in range(length))

    return password

def get_random_mob_proxy():
    proxy = random.choices(population=nodemaven_mob_proxy_data)[0]
    proxies = {
        "http": f"http://{proxy}",
        "https": f"http://{proxy}"
    }
    return proxies


def get_random_mob_proxy_aiohttp():
    proxy = random.choices(population=nodemaven_mob_proxy_data)[0]
    proxy_url = f"http://{proxy.split('@')[-1]}"
    proxy_auth = aiohttp.BasicAuth(proxy.split('@')[0].split(':')[0], proxy.split('@')[0].split(':')[1])
    return proxy_url, proxy_auth

# some help func

def merge_files_with_delimiter(file1_path, file2_path, delimiter='|'):
    """
    Объединяет два файла построчно, разделяя строки заданным разделителем,
    и перезаписывает результат в первый файл.

    :param file1_path: Путь к первому файлу (будет перезаписан)
    :param file2_path: Путь ко второму файлу
    :param delimiter: Разделитель между строками (по умолчанию '|')
    """
    with open(file1_path, 'r', encoding='utf-8') as file1, \
         open(file2_path, 'r', encoding='utf-8') as file2:
        merged_lines = []
        for line1, line2 in zip(file1, file2):
            merged_lines.append(f"{line1.strip()}{delimiter}{line2.strip()}\n")

    # теперь перезаписываем первый файл
    with open(file1_path, 'w', encoding='utf-8') as f:
        f.writelines(merged_lines)

    print(f"[+] Файл '{file1_path}' успешно обновлён ({len(merged_lines)} строк).")


# Пример использования
# merge_files_with_delimiter('x_accs.txt', 'user_agents.txt', 'x_accs2.txt')


def parse_accounts_to_list(file_path='x_accs.txt'):
    """
    Парсит файл с данными аккаунтов и возвращает список словарей с структурированными данными.

    Формат строки:
    username:pass:mail:token|server:port:proxy_login:proxy_pass|user_agent

    Если в первой части больше 4 элементов (доп. двоеточия) — лишние игнорируются.
    """
    twitter_working_accounts = []

    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            if not line:
                continue

            try:
                # Разделяем основную часть и прокси
                account_part, proxy_part, ua = line.split('|')

                # --- Парсим аккаунт ---
                account_split = account_part.split(':')
                if len(account_split) < 5:
                    raise ValueError("Недостаточно данных в account_part")

                # Берём только первые 5 элемента, остальное игнорируем
                screen_name, password, email, email_pw, auth_token = account_split[:5]

                # --- Парсим прокси ---
                proxy_split = proxy_part.split(':')
                if len(proxy_split) < 4:
                    raise ValueError("Недостаточно данных в proxy_part")

                server_ip, port, proxy_login, proxy_pass = proxy_split[:4]

                # --- Формируем структуру ---
                twitter_working_accounts.append({
                    'screen_name': screen_name,
                    'password': password,
                    'proxy': f"{proxy_login}:{proxy_pass}@{server_ip}:{port}",
                    'auth_token': auth_token,
                    'ua': ua
                })

            except Exception as e:
                print(f"[ERROR] Ошибка парсинга строки:\n{line}\nПричина: {e}\n")
                continue

    return twitter_working_accounts

# twitter_working_accounts = parse_accounts_to_list('x_accs_test.txt')

def remove_after_pipe(file_path, output_path=None):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    cleaned_lines = [line.split('|')[0].rstrip() + '\n' for line in lines]

    # Если указан путь для сохранения — записываем туда
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(cleaned_lines)
    else:
        # Иначе — перезаписываем оригинальный файл
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(cleaned_lines)


def format_tweet_data(tweet_data: dict) -> str:
    return (
        f"Tweet Info:\n"
        f"{'-' * 60}\n"
        f"Created At          : {tweet_data.get('created_at', '')}\n"
        f"Timestamp           : {tweet_data.get('created_at_timestamp', '')}\n"
        f"Tweet ID            : {tweet_data.get('id', '')}\n"
        f"Text                : {tweet_data.get('full_text', '')}\n"
        f"Retweeted Text      : {tweet_data.get('retweeted_full_text', '')}\n"
        f"Followers           : {tweet_data.get('followers_count', '')}\n"
        f"Blue Verified       : {tweet_data.get('blue_verified', '')}\n"
        f"Tweet URL           : {tweet_data.get('url', '')}\n"
        f"Entities URLs       : {tweet_data.get('entities_urls', [])}\n"
        f"Entities Media      : {tweet_data.get('entities_media', '')}\n"
        f"Quoted Tweet Media  : {tweet_data.get('quoted_tweet_media', '')}\n"
        f"Is Reply            : {tweet_data.get('is_reply', False)}"
    )


def parse_cid(proxy_str: str) -> str | None:
    """
    Извлекает CID (часть после 'medium:' и до '@') из строки прокси NodeMaven.
    Возвращает None, если не найдено.
    """
    match = re.search(r"sid-([a-zA-Z0-9]+)", proxy_str)
    return match.group(1) if match else None


# ======= АКТУАЛЬНЫЕ PULL'Ы UA (окт 2025) =======
MOBILE_IPHONE = [
    # iOS 18 / 17 — Mobile Safari
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
]

MOBILE_ANDROID = [
    # Samsung Galaxy
    "Mozilla/5.0 (Linux; Android 15; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",  # S24 Ultra
    "Mozilla/5.0 (Linux; Android 14; SM-S926B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",  # S24+
    "Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",  # S24
    "Mozilla/5.0 (Linux; Android 14; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",  # S21 Ultra
    "Mozilla/5.0 (Linux; Android 13; SM-A546E) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36",  # A54

    # Google Pixel
    "Mozilla/5.0 (Linux; Android 15; Pixel 9 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 15; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 7a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",

    # Xiaomi / Redmi
    "Mozilla/5.0 (Linux; Android 14; Xiaomi 14 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Redmi Note 13 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Mi 13T) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",

    # OnePlus
    "Mozilla/5.0 (Linux; Android 15; OnePlus 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; OnePlus 11R) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",

    # Oppo / Realme
    "Mozilla/5.0 (Linux; Android 14; OPPO Find X7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Realme GT 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",

    # Huawei / Honor
    "Mozilla/5.0 (Linux; Android 13; HUAWEI P60 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; HONOR Magic6 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",

    # Vivo / iQOO
    "Mozilla/5.0 (Linux; Android 14; vivo X100 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; iQOO 12) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",

    # ASUS / Nothing / Sony
    "Mozilla/5.0 (Linux; Android 14; ASUS Zenfone 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Nothing Phone 2a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Sony Xperia 1 V) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36",

    # Motorola / Infinix
    "Mozilla/5.0 (Linux; Android 14; moto edge 50 pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Infinix GT 20 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",
]
DESKTOP_CHROME = [
    # Chrome 139–140 на Windows/macOS/Linux
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
]

DESKTOP_OTHERS = [
    # Safari 17/18 (macOS Sequoia), Firefox 130+, Edge 140+, Opera 115+
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 OPR/115.0.0.0",
]

def _pick_desktop_ua(chrome_ratio: float = 0.8) -> str:
    """Десктоп: chrome_ratio → Chrome, иначе один из других."""
    if random.random() < chrome_ratio:
        return random.choice(DESKTOP_CHROME)
    return random.choice(DESKTOP_OTHERS)

def _pick_mobile_ua() -> str:
    """Мобильные: 50% iPhone, 50% Android."""
    if random.random() < 0.5:
        return random.choice(MOBILE_IPHONE)
    return random.choice(MOBILE_ANDROID)

def _pick_user_agent(mobile_ratio: float = 0.4, desktop_chrome_ratio: float = 0.8) -> str:
    """
    40% (по умолчанию) — мобильные (iPhone/Android);
    60% — десктоп; среди десктопов 80% — Chrome.
    """
    if random.random() < mobile_ratio:
        return _pick_mobile_ua()
    return _pick_desktop_ua(chrome_ratio=desktop_chrome_ratio)

def append_user_agents(file_path: str, mobile_ratio: float = 0.8, desktop_chrome_ratio: float = 0.8):
    """
    Добавляет User-Agent к каждой строке файла через '|', ПЕРЕЗАПИСЫВАЯ исходный файл.
    - mobile_ratio: доля мобильных UA (0..1), по умолчанию 0.8
    - desktop_chrome_ratio: доля Chrome среди десктопов (0..1), по умолчанию 0.8
    """
    with open(file_path, "r", encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f if ln.strip()]

    with open(file_path, "w", encoding="utf-8") as f:
        for ln in lines:
            ua = _pick_user_agent(mobile_ratio, desktop_chrome_ratio)
            f.write(f"{ln}|{ua}\n")


def make_main_file_with_accs():
    merge_files_with_delimiter('x_accs.txt', 'proxy.txt')
    append_user_agents('x_accs.txt')


if __name__ == '__main__':
    print(generate_password())