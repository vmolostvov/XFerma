import random, re, aiohttp

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
    'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-66134b93e4864-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080'
]

nodemaven_proxy_rotating = {'http': 'https://vmolostvov96_gmail_com-country-any-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080', 'https': 'http://vmolostvov96_gmail_com-country-any-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080/'}

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

def merge_files_with_delimiter(file1_path, file2_path, output_path, delimiter='|'):
    """
    Объединяет два файла построчно, разделяя строки заданным разделителем.

    :param file1_path: Путь к первому файлу
    :param file2_path: Путь ко второму файлу
    :param output_path: Путь к выходному файлу
    :param delimiter: Разделитель между строками (по умолчанию '|')
    """
    with open(file1_path, 'r', encoding='utf-8') as file1, \
            open(file2_path, 'r', encoding='utf-8') as file2, \
            open(output_path, 'w', encoding='utf-8') as out_file:
        for line1, line2 in zip(file1, file2):
            # Удаляем символы переноса строки и объединяем с разделителем
            merged_line = f"{line1.strip()}{delimiter}{line2.strip()}\n"
            out_file.write(merged_line)


# Пример использования
# merge_files_with_delimiter('x_accs.txt', 'user_agents.txt', 'x_accs2.txt')


def parse_accounts_to_list(file_path='x_accs.txt'):
    """
    Парсит файл с данными аккаунтов и возвращает список словарей с структурированными данными.

    :param file_path: Путь к файлу с данными
    :return: Список аккаунтов в заданном формате
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

                # Парсим данные аккаунта
                screen_name, password, email, auth_token = account_part.split(':')

                # Парсим данные прокси
                server_ip, port, proxy_login, proxy_pass = proxy_part.split(':')

                # Формируем словарь с данными и добавляем в список
                twitter_working_accounts.append({
                    'screen_name': screen_name,
                    'password': password,
                    'proxy': f"{proxy_login}:{proxy_pass}@{server_ip}:{port}",
                    'auth_token': auth_token,
                    'ua': ua
                })

            except ValueError as e:
                print(f"Ошибка парсинга строки: {line}. Ошибка: {e}")
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
