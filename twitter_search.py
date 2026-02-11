from curl_cffi.requests.exceptions import ProxyError as ProxyError1
from curl_cffi import requests

import json, os, datetime, time, random, urllib.parse, concurrent.futures, traceback, pytz, threading
from multiprocessing.managers import SyncManager

from alarm_bot import admin_error
# from tweeterpyapi import load_accounts_tweeterpy, initialize_client
from config import generate_password
from requests.exceptions import ReadTimeout, ProxyError, ConnectTimeout, SSLError
from selen import get_code_from_email
# from curl_cffi import requests
# from cdp_sniffer import sniff_headers
# from pixelscan_checker import proxy_check, make_proxy_str_for_pixelscan

# import logging
#
# logger = logging.getLogger("flow_login")
# logger.setLevel(logging.INFO)
#
# if not logger.handlers:
#     fmt = logging.Formatter(
#         "%(asctime)s [%(levelname)s] %(message)s",
#         datefmt="%Y-%m-%d %H:%M:%S"
#     )
#     ch = logging.StreamHandler()
#     ch.setLevel(logging.INFO)
#     ch.setFormatter(fmt)
#
#     fh = logging.FileHandler("loggers/flow_login.log", encoding="utf-8")
#     fh.setLevel(logging.INFO)
#     fh.setFormatter(fmt)
#
#     logger.addHandler(ch)
#     logger.addHandler(fh)

twitter_url = 'twitter.com/'

##################################################################################################################################

# session = tls_client.Session(
#     client_identifier="chrome_120",
#     random_tls_extension_order=True
# )
# session.timeout_seconds = 10

# random.shuffle(twitter_working_accounts)


# Индекс для отслеживания текущего аккунта
acc_index = 0
acc_usage_count = 0

# Блокировка для синхронизации доступа к списку аккаунтов
acc_lock = threading.Lock()

##################################################################################################################################

interval = 10 # периодичность проверки списка адресов смарт-контрактов из файла в секундах (следующая проверка через такое количество секунд после завершения предыдущей проверки)
threads = 9 # количество потоков проверки адресов смарт-контрактов (не более количества имеющихся аккаунтов)
contract_addresses_per_search = 20 # количество адресов смарт-контрактов за один поиск
recent_tweets_time_limit = 7*24*3600 # ограничение возраста найденных твитов в секундах
recent_tweets_count_limit = 200 # ограничение количества найденных твитов в штуках за один поиск (на все смарт-контакты в этом поиске)
recent_user_tweets_count_limit = 10 # ограничение количества загружаемыех последних твитов пользователя (на первой странице возвращается до 20 твитов, следующие страницы не загружаются)

# чёрный список пользователей
twitter_username_bl = ['oehsen_277', 'crypto_rick_gm', 'DegenAlertDEX', 'BullishBuyRadar', 'Crypto__KoKo', 'BrantleyJo64527', 'MR_KINGJACK',
                       'cryptonic40', 'HortonDomi52866', 'Launchhunter', 'CalebNelso18302', 'CoinspeedrunBot', 'Hannahcoineth',
                       'Pepe_Army2023', 'belufrancese', 'TheCryptoSquire', 'MarioBullish', 'BinanceArmy100x', 'gianlucabtc',
                       'ShibArmyBullish', 'BinanceArmy100x', 'coinnewscar', 'cryptouboss', 'hugocryptoz', 'felixcryptogm',
                       'gg776650', 'ai5203344', 'wjf110', 'AliyaCrypto', 'audreypromos' 'SnipeguruLock', 'antiscammer2022',
                       'BscSuperAltcoin', 'BatmanGems', 'EthMemeCalls', 'bot_hype13170', 'ethtrendstats', 'snipeguruvol',
                       'lucas_paixalc', 'trendingscams', 'TokensEthereum', 'BondedPump', 'YutiBot3', 'TesaWeb3', 'YutiBot2',
                       'SolanaNewToken', 'NadeneTama91748', 'agateware_gamer', 'adamjia7', 'snipegurusolvol', 'isotone_1998',
                       'DidierRyos14287', 'SolScopeCall', 'iRMsjSEYFDlSrFz', 'nigelniger_1993', 'ballew_johnyyS', 'fraxinella_bro',
                       'DeschompL79648', 'crushing_DJ_', 'PumpaNomicscom', 'cankered_gamer4', 'timely44', '0xOnlyCalls',
                       'dexsignals', 'Lyanwenn', 'Tally_zhangi', 'AgentOyen', 'Kiko_selfl', '88neptunes', 'AutorunCrypto',
                       'Lui16lui2', 'hypedetectorbor', 'Dape_agent', 'ai_xtn']

twitter_text_bl = ['GentleCatCall', 'Angrybot', 'dogeebot_bot', 'There are some smart investors who bought this coin', 'CCaoming',
                   'bobradar.com', 'smart traders are buying it', 'Smart Money Alert', 'Market Momentum Alert', 'NEW SIGNAL CALL DETECTED',
                   'axiom.trade', 'Follow the whales and copy their moves', 'New post in Hype Detector', 'Alpha Calls:',
                   'Keeper_Degen', 'New Project Alert!']

twitter_infl = ['elonmusk', 'matt_furie', 'cz_binance', 'binance', 'sbf_ftx', 'vitalikbuterin', 'beeple', 'blknoiz06']

twitter_username_bl_lowered = list(map(lambda x: x.lower(), twitter_username_bl))

# чёрный список доменов
exclude_list = [
    'opensea.io', 'instagram.com', 'discord.gg', 'github.com', 'urbandictionary.com', 'fandom.com', 'opensource.org',
    'hardhat.org', 'medium.com', 'reuters.com', 'wechat.com', 'bscscan.com', 'twitter.com', 'unicrypt.network',
    'etherscan.', 'google.', 'gitbook.', 'docs.', 'piliapp.com', 'golden.com', 'wikipedia.org', 'ft.com', 'snipe.guru',
    'knowyourmeme.com', 'weibo.cn', 'weibo.com', 'pornhub.com', 'linktr.ee', 'rumble.com', 'discord.com', 'defined.fi',
    'youtube.com', 'hawaiiwildfire.org', 't.co', 'meme-arsenal.com', 'reddit.com', 'dextools.io', 'bloomberg.com',
    'cryptonews.net', 'douyin.com', 'baike.baidu.com', 'rubiks.com', 'looksrare.org', 'tiktok.com', 'coinmarketcap.com',
    'coingecko.com', 'watcher.guru', 'bit.ly', '.pdf', 'whitepaper.', 'white-paper.', 'youtu.be', 'poocoin.app', 't.ly',
    'arbiscan.io', 'kick.me', 'twitch.tv', 'stake.com', 'moontok.io', 'coincatapult.com', 'coinbazooka.com', 'coinscope.co',
    'top100token.com', 'coindiscovery.app', 'coinsniper.net', 'gemsradar.com', 'coinboom.net', 'coinmoonhunt.com',
    'coinsgem.com', 'coinvote.cc', 'cryptach.org', 'cointoplist.net', 'coinpaprika.com', 'flooz.xyz', 'coinmerge.io',
    'cryptotips4all.com', 'coinmooner.com', 'coinranking.com', 'hypemytoken.com', 'coinalpha.app', 'coindizzy.com',
    'coinmetahub.com', 'cryptonextgem.com', 'advanced.coinxhigh.com', 'doctorecoins.com', 'polygonscan.com', 'deca.art',
    'dadc.com', 'uncyclopedia.co', 'litepaper.', 'zeppelin.', 'ethereum.org', 'consensys.net', 'stackexchange.com',
    'xn--2-umb.com', 'eth.wiki', 'solidity.readthedocs', 'docs.ethers', 'ethers.io', 'metamask.io', 'coinscan.com',
    'gnu.org', 'readthedocs.io', 'www.x.com', 'apple.com', 'gleam.io', 'tiktok.com', 'ftx.us', 'jdb.finance', 'foxbusiness.com'
    'github.', 'basescan.', 'reserve.org', 'git.io', 'aave.com', 'ibb.co', 'businessinsider.com', 'mcsweeneys.net',
    'pinksale.finance', 'theblock.co', 'coindesk.', 'huobi.com', 'facebook.', 'kick.com', 'smartcontracts.tools',
    'friend.tech', 'artstation.com', 'zhihu.com', 'gashawk.io', 'uniswap.org', 'thetimes.', 'vogue.com', 'fsf.org',
    'blazex.org', 'tokenmint.io', 'openai.com', 'certik.com', 'dexscreener.com', 'uncx.network', 'x.com', 'dextools.com',
    'justsomething.co', 'balancer.fi', 'metadrop.com', 'solana.com', 'dexpy.io', 'cointelegraph.com', 'knowyourmeme.com',
    'verifytelegram.com', 'coingraph.news', 'onlymoons.io', 'xinbi.com', 'binance.com', 'dexanalyzer.io', 'team.finance',
    'allmylinks.com', 'countingdownto.com', 'peckshield.com', 'yahoo.com', 'verum-news.com', 'wsj.com', 'notateslaapp.com',
    'honeypot.is', 'news.treeofalpha.com', 'nytimes.com', 'cointr.ee', 'tinyurl.com', 'bubblebuybot.com', 'timeanddate.com',
    'videogameschronicle.com', 'mirror.xyz', 'independent.co', 'nbcchicago.com', 'hypebeast.com', 'research.google', 'blackrock.com',
    'prnewswire.com', 'bobbybot.dev', 'binance.us', 'forms.gle', 'spotify.com', 'theblock.pro', 'yews.news', 'snowtrace.io'
    'ftmscan.com', 'coingape.com', 'cryptonews.com', 'cryptogems.info'
]

dextools_root = 'dextools.io/app/en/ether/pair-explorer/'

##################################################################################################################################

# def get_next_acc():
#     global acc_index
#     with acc_lock:
#         acc = twitter_working_accounts[acc_index]
#         acc_index = (acc_index + 1) % len(twitter_working_accounts)  # Переход к следующему x account
#     return acc
#
# def get_next_acc2(get_next=False, get_current=False):
#     global acc_index, acc_usage_count
#     with acc_lock:
#         acc = twitter_working_accounts[acc_index]
#         if get_current:
#             return  acc
#         acc_usage_count += 1
#
#         if acc_usage_count >= 10 or get_next:
#             acc_usage_count = 0
#             acc_index = (acc_index + 1) % len(twitter_working_accounts)
#
#     return acc


def get_proxies_for_twitter_account(twitter_working_account):
    # https://github.com/edeng23/binance-trade-bot/issues/438
    if twitter_working_account['proxy']:
        proxies = {
            "http": f"http://{twitter_working_account['proxy']}",
            "https": f"http://{twitter_working_account['proxy']}"
        }
    else:
        proxies = None
    return proxies

def get_headers_for_twitter_account(twitter_cookies_dict, referer='https://x.com/'):
    headers = {
        'Authority': 'x.com',
        'accept': '*/*',
        'accept-encoding': 'gzip, deflate, br, zstd',
        'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
        'cache-control': 'no-cache',
        'content-type': 'application/json',
        'connection': 'close',
        'cookie': '; '.join(f'{key}={value}' for key, value in twitter_cookies_dict.items()),
        'pragma': 'no-cache',
        'referer': referer,
        'priority': 'u=1,i',
        'sec-ch-ua': '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
        'x-client-transaction-id': '',
        # 'x-client-uuid': 'e9b26073-2b3e-48da-9ae9-8ede706fccac',
        'x-csrf-token': twitter_cookies_dict['ct0'],
        'x-twitter-active-user': 'yes',
        'x-twitter-auth-type': 'OAuth2Session',
        'x-twitter-client-language': 'en'
    }
    headers.pop('x-client-transaction-id', None)
    headers.pop("accept-encoding", None)
    # headers.pop('x-client-uuid', None)
    return headers

def load_cookies_for_twitter_account_from_file(twitter_cookies_filename):
    with open(twitter_cookies_filename, "r") as f:
        cookies = json.load(f)
    cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies}
    return cookies_dict

# login to twitter by tweepy_authlib
def load_cookies_for_twitter_account(twitter_working_account, load_cookies_from_file_if_exists=True):
    twitter_cookies_filename = f"x_accs_cookies/{twitter_working_account['screen_name']}.json"

    if (load_cookies_from_file_if_exists) and (os.path.exists(twitter_cookies_filename)):
        twitter_working_account["cookies_dict"] = load_cookies_for_twitter_account_from_file(twitter_cookies_filename)

def disable_safe_search_for_twitter_account(twitter_working_account):
    # print(f"Отключение безопасного поиска для аккаунта: {account_number}")
    twitter_cookies_dict = twitter_working_account["cookies_dict"]

    headers = get_headers_for_twitter_account(twitter_cookies_dict)
    # proxies = get_proxies_for_twitter_account(twitter_working_account)
    user_id = get_user_id_by_user_screen_name(twitter_working_account["screen_name"], twitter_working_account)
    # user_id = urllib.parse.unquote(twitter_working_account["cookies_dict"]["twid"]).replace("u=", "") # "u%3D1668664483282137098" --> "u=1668664483282137098" --> "1668664483282137098"

    url = f"https://twitter.com/i/api/1.1/strato/column/User/{user_id}/search/searchSafety"
    payload = {
        "optInFiltering": False,
        "optInBlocking": False
    }

    # session.proxies.update(proxies)

    attempts = 0
    loaded_successfully = False
    while not loaded_successfully:
        try:
            response = twitter_working_account['session'].post(url, json=payload, headers=headers)
        except Exception as error:
            attempts += 1
            time.sleep(attempts * random.uniform(1, 3))
        else:
            loaded_successfully = True
            return response

def load_accounts_cookies_login(scraper_accs, disable_safe_search=False):
    global manager, requests_count, lock

    manager = SyncManager()
    manager.start()
    requests_count = manager.Value(int, 0)
    lock = manager.Lock()

    twitter_working_accounts = scraper_accs
    twitter_working_accounts = [dict(working_account, requests=manager.Value(int, 0), requests_successful=manager.Value(int, 0), requests_errors=manager.Value(int, 0)) for working_account in twitter_working_accounts]
    random.shuffle(twitter_working_accounts)

    # загрузка cookies для аккаунтов
    accounts_count = len(twitter_working_accounts)
    # accounts_numbers = list(range(0, accounts_count))
    for twitter_working_account in twitter_working_accounts:
        load_cookies_for_twitter_account(twitter_working_account)

        s = requests.Session(
            impersonate="chrome120",
            timeout=(3, 8),
            proxies=get_proxies_for_twitter_account(twitter_working_account)
        )

        twitter_working_account['session'] = s

        # отключение безопасного поиска для аккаунтов
        if disable_safe_search:
            with concurrent.futures.ThreadPoolExecutor(max_workers=accounts_count) as executor:
                executor.map(disable_safe_search_for_twitter_account, twitter_working_account)

    return twitter_working_accounts


def reload_acc_cook_and_sess(scraper_acc):
    # загрузка cookies для аккаунтов
    load_cookies_for_twitter_account(scraper_acc)

    s = requests.Session(
        impersonate="chrome120",
        timeout=(3, 10),
        proxies=get_proxies_for_twitter_account(scraper_acc)
    )

    scraper_acc['session'] = s


    return scraper_acc


##################################################################################################################################

def contains_ci(needle, haystack):
    return needle.lower() in haystack.lower()

def is_bl_in_text(tweet_text):
    for bl_text in twitter_text_bl:
        if bl_text.lower() in tweet_text.lower():
            return True
    return False

def contains_clear(needle, haystack):
    for word in haystack.lower():
        if word == needle.lower():
            return True
    return False

def split_list_into_chunks(items, chunk_size):
    return [items[i:i+chunk_size] for i in range(0, len(items), chunk_size)]

def json_to_str(json_object):
    return json.dumps(json_object, separators=(',', ':'))

def filter_entities_urls(entities_urls):
    filtered_urls = []
    for entities_url in entities_urls:
        expanded_url = entities_url["expanded_url"]
        domain = urllib.parse.urlparse(expanded_url).netloc
        url_not_in_exclude_list = all([exclude_string.lower() not in expanded_url.lower() for exclude_string in exclude_list])
        if expanded_url and url_not_in_exclude_list:
            filtered_urls.append(expanded_url)

    # только уникальные ссылки
    filtered_urls = list(set(filtered_urls))
    # все ссылки кроме телеграма
    filtered_urls_except_telegram = [url for url in filtered_urls if ("t.me/" not in url)]
    # все ссылки только на телеграм
    filtered_urls_only_telegram = [url for url in filtered_urls if ("t.me/" in url)]
    #
    if (len(filtered_urls_except_telegram) > 0):
        filtered_urls = filtered_urls_except_telegram
    else:
        filtered_urls = filtered_urls_only_telegram

    return filtered_urls


def parse_tweet(tweet_raw):
    tweet_user_raw = tweet_raw["core"]["user_results"]["result"]
    # print(f"tweet_user_raw: {tweet_user_raw}")
    try:
        tweet_legacy = tweet_raw["legacy"]
    except KeyError:
        return

    if ("retweeted_status_result" in tweet_legacy) and ("result" in tweet_legacy["retweeted_status_result"]) and (
            "legacy" in tweet_legacy["retweeted_status_result"]["result"]):
        retweeted_tweet_legacy = tweet_legacy["retweeted_status_result"]["result"]["legacy"]

    tweet_parsed = {
        'source': tweet_raw["source"],
        'created_at': tweet_legacy["created_at"],
        'created_at_timestamp': datetime.datetime.timestamp(
            datetime.datetime.strptime(tweet_legacy["created_at"], '%a %b %d %H:%M:%S %z %Y')),
        # Mon Sep 25 10:12:07 +0000 2023" --> datetime.datetime(2023, 9, 25, 10, 12, 7, tzinfo=datetime.timezone.utc) --> 1695636727.0
        'id': int(tweet_legacy["id_str"]),
        'user_id': int(tweet_legacy["user_id_str"]),
        'conversation_id': int(tweet_legacy["conversation_id_str"]),
        'full_text': tweet_legacy["full_text"],
        'retweeted_full_text': retweeted_tweet_legacy["full_text"] if "retweeted_tweet_legacy" in locals() else "",
        'url': f"https://twitter.com/{tweet_user_raw.get('core', {}).get('screen_name') or tweet_user_raw.get('legacy', {}).get('screen_name')}/status/{tweet_legacy['id_str']}",
        # 'lang': tweet_legacy["lang"],
        # 'quote_count': tweet_legacy["quote_count"],
        # 'reply_count': tweet_legacy["reply_count"],
        # 'retweet_count': tweet_legacy["retweet_count"],
        # 'favorite_count': tweet_legacy["favorite_count"],
        # 'bookmark_count': tweet_legacy["bookmark_count"],
        # 'views_count': int(tweet_raw["views"]["count"] if "count" in tweet_raw["views"] else "0"),
        # 'views_state': tweet_raw["views"]["state"],
        'entities_urls': tweet_legacy["entities"].get("urls", []) + (
            tweet_raw["note_tweet"]["note_tweet_results"]["result"]["entity_set"].get("urls", []) if (
                        ("note_tweet" in tweet_raw) and (
                            "entity_set" in tweet_raw["note_tweet"]["note_tweet_results"]["result"])) else []),
        'entities_media': next((m.get("media_url_https", '') for m in tweet_legacy.get("entities", {}).get("media", []) if "media_url_https" in m),''),
        'quoted_tweet_media': '',
        'is_reply': 'in_reply_to_screen_name' in tweet_legacy
        # 'entities_user_mentions': tweet_legacy["entities"].get("user_mentions", []),
    }

    if ("quoted_status_result" in tweet_raw) and ("result" in tweet_raw["quoted_status_result"]) and (
            "legacy" in tweet_raw["quoted_status_result"]["result"]):
        quoted_tweet_legacy = tweet_raw["quoted_status_result"]["result"]["legacy"]
        tweet_parsed['quoted_tweet_media'] = next((m.get("media_url_https", '') for m in quoted_tweet_legacy.get("entities", {}).get("media", []) if "media_url_https" in m),'')
    # filter tweet urls for blacklist domains
    # [{'display_url': 'dexscreener.com/ethereum/0x621…', 'expanded_url': 'https://dexscreener.com/ethereum/0x6213f40e00f4595aa038fa710e3f837b492d6757', 'url': 'https://t.co/HSz1qFVcje', 'indices': [103, 126]}]
    # [{'display_url': 't.me/anjimeme', 'expanded_url': 'https://t.me/anjimeme', 'url': 'https://t.co/upNMApzg7q', 'indices': [101, 124]}]
    # [{'display_url': 't.me/ThePondToken', 'expanded_url': 'https://t.me/ThePondToken', 'url': 'https://t.co/isQ3l2CMT3', 'indices': [85, 108]}, {'display_url': 'dexscreener.com/ethereum/0x40d…', 'expanded_url': 'https://dexscreener.com/ethereum/0x40dc67f57d71d592609e84603409137518445c74', 'url': 'https://t.co/XOZbv7JiI2', 'indices': [110, 133]}]
    # tweet_parsed['entities_filtered_urls'] = filter_entities_urls(tweet_parsed['entities_urls'])
    return tweet_parsed

def parse_user(user_raw):
    user_parsed = {
        'id': int(user_raw["rest_id"]),
        'name': user_raw.get("core", {}).get("name") or user_raw.get("legacy", {}).get("name"),
        'screen_name': user_raw.get("core", {}).get("screen_name") or user_raw.get("legacy", {}).get("screen_name"),
        'location': user_raw.get("location", {}).get("location") or user_raw.get("legacy", {}).get("location"),
        'profile_banner_url': user_raw["legacy"].get("profile_banner_url", ""),
        'profile_image_url_https': user_raw["legacy"].get("profile_image_url_https", ""),
        'notifications': user_raw["legacy"].get("notifications", None),
        'followers_count': user_raw["legacy"]["followers_count"],
        'normal_followers_count': user_raw["legacy"]["normal_followers_count"],
        'favourites_count': user_raw["legacy"]["favourites_count"],
        'friends_count': user_raw["legacy"]["friends_count"],
        'statuses_count': user_raw["legacy"]["statuses_count"],
        'description': user_raw["legacy"]["description"],
        'created_at': user_raw.get("core", {}).get("created_at") or user_raw.get("legacy", {}).get("created_at"),
        'verified': user_raw.get("verification", {}).get("verified") or user_raw.get("legacy", {}).get("verified"),
        'blue_verified': user_raw["is_blue_verified"],
        'entities_urls': ([{"expanded_url": user_raw["legacy"].get("url", "")}] or []) + user_raw["legacy"]["entities"].get("url", {}).get("urls", []) + user_raw["legacy"]["entities"].get("description", {}).get("urls", [])
    }
    user_parsed['created_at_timestamp'] = datetime.datetime.timestamp(datetime.datetime.strptime(user_parsed['created_at'], '%a %b %d %H:%M:%S %z %Y')) # Mon Sep 25 10:12:07 +0000 2023" --> datetime.datetime(2023, 9, 25, 10, 12, 7, tzinfo=datetime.timezone.utc) --> 1695636727.0
    # filter tweet urls for blacklist domains
    user_parsed['entities_filtered_urls'] = filter_entities_urls(user_parsed['entities_urls'])
    return user_parsed

def parse_tweet_entry(tweet_entry):
    tweet_entry_parsed = {}

    # excluding promoted tweets
    # print(tweet_entry["entryId"]) # possible values: "promoted-tweet-1698805334255529988-286948ce64a0ea25", "tweet-1703568195150336441",  "cursor-top-9223372036854775807", "cursor-bottom-0", "spelling-0"
    try:
        if ("tweet" in tweet_entry["entryId"]) and ("promoted-tweet" not in tweet_entry["entryId"]):
            tweet = tweet_entry["content"]["itemContent"]["tweet_results"]["result"]
        elif ("profile-conversation" in tweet_entry["entryId"]):
            tweet = tweet_entry["content"]["items"][-1]["item"]["itemContent"]["tweet_results"]["result"]
    except:
        pass

    if "tweet" in locals():
        if "tweet" in tweet:
            tweet = tweet["tweet"]
        elif "legacy" not in tweet:
            tweet = {}

        if tweet:
            tweet_user = tweet["core"]["user_results"]["result"]
            parsed_tweet = parse_tweet(tweet)
            if parsed_tweet:
                tweet_entry_parsed = {
                    'tweet': parsed_tweet,
                    'user': parse_user(tweet_user)
                }

    return tweet_entry_parsed

def parse_users_instructions(instructions):
    results = {
        "cursors": {},
        "users": []
    }

    for instruction in instructions:
        if instruction["type"] == "TimelineAddEntries":
            users_entries = instruction["entries"]
            # print(f"users_entries = {len(users_entries)}")
            for user_number, user_entry in enumerate(users_entries, 1):
                if user_entry["content"]["entryType"] == "TimelineTimelineCursor":
                    cursor_type = user_entry["content"]["cursorType"].lower()
                    cursor_value = user_entry["content"]["value"]
                    results["cursors"][cursor_type] = cursor_value
                    # print(">>>", cursor_type, cursor_value)
                elif user_entry["content"]["entryType"] == "TimelineTimelineItem":
                    # print(user_entry["entryId"])
                    user_raw = user_entry["content"]["itemContent"]["user_results"]["result"]
                    user_parsed = parse_user(user_raw)
                    results["users"].append(user_parsed)
    return results

def parse_tweets_instructions(instructions):
    results = {
        "cursors": {},
        "tweets": []
    }

    for instruction in instructions:
        # instruction["type"] possible values: "TimelineAddEntries", "TimelineReplaceEntry", "TimelinePinEntry", "TimelineClearCache"
        try:
            if instruction["type"] == "TimelineReplaceEntry":
                if instruction["entry"]["content"]["__typename"] == "TimelineTimelineCursor":
                    cursor_type = instruction["entry"]["content"]["cursorType"].lower()
                    cursor_value = instruction["entry"]["content"]["value"]
                    results["cursors"][cursor_type] = cursor_value
                    # print(">>>", cursor_type, cursor_value)
            elif instruction["type"] == "TimelinePinEntry":
                tweet_parsed = parse_tweet_entry(instruction["entry"])
                if tweet_parsed:
                    results["tweets"].append(tweet_parsed)
            elif instruction["type"] == "TimelineAddEntries":
                tweets_entries = instruction["entries"]
                # print(f"tweets_entries = {len(tweets_entries)}")
                for tweet_number, tweet_entry in enumerate(tweets_entries, 1):
                    # print(f"----- {tweet_number} -----")
                    # print(entry["content"]["entryType"]) # possible values: TimelineTimelineItem, TimelineTimelineModule, TimelineTimelineCursor
                    if tweet_entry["content"]["entryType"] == "TimelineTimelineCursor":
                        cursor_type = tweet_entry["content"]["cursorType"].lower()
                        cursor_value = tweet_entry["content"]["value"]
                        results["cursors"][cursor_type] = cursor_value
                        # print(">>>", cursor_type, cursor_value)
                    elif tweet_entry["content"]["entryType"] == "TimelineTimelineItem" or tweet_entry["content"]["entryType"] == "TimelineTimelineModule":
                        # print(tweet_entry["entryId"])
                        # print(tweet_entry)
                        tweet_parsed = parse_tweet_entry(tweet_entry)
                        if tweet_parsed:
                            tweet_parsed['tweet']['screen_name'] = tweet_parsed['user']['screen_name']
                            tweet_parsed['tweet']['followers_count'] = tweet_parsed['user']['followers_count']
                            tweet_parsed['tweet']['blue_verified'] = tweet_parsed['user']['blue_verified']
                            results["tweets"].append(tweet_parsed)
        except Exception as e:
            print(traceback.format_exc())

    if len(results["tweets"]) > 0:
        # results["tweets"] = sorted(results["tweets"], key=lambda x: x["tweet"]["created_at_timestamp"], reverse=True)
        if "top" in results["cursors"]:
            results["tweets"][0]["cursor_top"] = results["cursors"]["top"]
        if "bottom" in results["cursors"]:
            results["tweets"][-1]["cursor_bottom"] = results["cursors"]["bottom"]

    return results

##################################################################################################################################

class RateLimitExceededError(Exception):
    def __init__(self, message):
        super().__init__("Rate limit exceeded")

def twitter_api_call(api_endpoint, variables, features, twitter_working_account=None, use_current_acc=False, toggles=False):

    # time.sleep(random.uniform(0.1, 0.2))
    referer = 'https://x.com/'
    if api_endpoint == "SearchTimeline":
        base_url = "https://api.x.com/graphql/IOJ89SDQ9IrZ2t7hSD4Fdg/SearchTimeline"
        referer = f'https://x.com/search?q={variables["rawQuery"]}&src=recent_search_click&f=live'
    elif api_endpoint == 'membersSliceTimeline_Query':
        base_url = "https://x.com/i/api/graphql/gwNDrhzDr9kuoulEqgSQcQ/membersSliceTimeline_Query"
    elif api_endpoint == 'TweetDetail':
        base_url = "https://x.com/i/api/graphql/4Siu98E55GquhG52zHdY5w/TweetDetail"
    elif api_endpoint == "UserTweets":
        base_url = "https://api.x.com/graphql/Tfe3FqoVuZ0g38yddTX5XA/UserTweets"
    elif api_endpoint == "UserTweetsAndReplies":
        base_url = "https://api.x.com/graphql/2dNLofLWl-u8EQPURIAp9w/UserTweetsAndReplies"
    elif api_endpoint == "UsersByRestIds":
        base_url = "https://x.com/i/api/graphql/9UCmrCOmAn6TYy_Y13cSjA/UsersByRestIds"
    elif api_endpoint == "UserByScreenName":
        base_url = "https://x.com/i/api/graphql/xmU6X_CKVnQ5lSrCbAmJsg/UserByScreenName"
    elif api_endpoint == "Following":
        base_url = "https://x.com/i/api/graphql/FG7gWUco2ITV3KDa4_XUHQ/Following"
    elif api_endpoint == "FavoriteTweet":
        base_url = "https://x.com/i/api/graphql/lI07N6Otwv1PhnEgXILM7A/FavoriteTweet"
    elif api_endpoint == "CreateRetweet":
        base_url = "https://x.com/i/api/graphql/ojPdsZsimiJrUGLR1sjUtA/CreateRetweet"
    elif api_endpoint == "CreateBookmark":
        base_url = "https://x.com/i/api/graphql/aoDbu3RHznuiSkQ9aNM67Q/CreateBookmark"
    elif api_endpoint == 'View':
        base_url = "https://x.com/i/api/1.1/graphql/user_flow.json"
        referer = 'https://x.com/vladik_sol/status/1935709990523691058'
    elif api_endpoint == 'begin_email_verif':
        base_url = "https://api.x.com/1.1/onboarding/begin_verification.json"
    elif api_endpoint == 'complete_email_verif':
        base_url = "https://api.x.com/1.1/onboarding/task.json"
    elif api_endpoint == 'add_email':
        base_url = "https://api.x.com/1.1/onboarding/task.json?flow_name=add_email"
    elif api_endpoint == 'verify_pw':
        base_url = "https://api.x.com/1.1/account/verify_password.json"
    elif api_endpoint == 'get_mail_phone':
        base_url = "https://x.com/i/api/1.1/users/email_phone_info.json"
        referer = 'https://x.com/settings/your_twitter_data/account'
    # login flow
    elif api_endpoint == 'login_flow':
        base_url = "https://api.x.com/1.1/onboarding/task.json?flow_name=login"
    elif api_endpoint in ['login_js_flow', 'enter_login_flow', 'enter_pw_flow']:
        base_url = "https://api.x.com/1.1/onboarding/task.json"
    elif api_endpoint == 'sso_init':
        base_url = 'https://api.x.com/1.1/onboarding/sso_init.json'
    elif api_endpoint == "CreateTweet":
        base_url = "https://x.com/i/api/graphql/Q0m4wAWzUFfjoQY7CXIXrQ/CreateTweet"
    elif api_endpoint == "change_profile":
        base_url = "https://api.x.com/1.1/account/update_profile.json"
    elif api_endpoint == "change_pw":
        base_url = "https://x.com/i/api/i/account/change_password.json"
    elif api_endpoint == "HomeTimeline":
        base_url = "https://x.com/i/api/graphql/c2y7UsmgbMG6b5rbyJDbvA/HomeTimeline"
    elif api_endpoint == "TweetResultByRestId":
        base_url = "https://api.x.com/graphql/yPpn5PIbqek0bMkNb9ufOQ/TweetResultByRestId"

    params = None
    if api_endpoint not in ['FavoriteTweet', 'CreateRetweet', 'CreateBookmark', 'View', 'change_profile', 'change_pw',
                            'get_mail_phone', 'begin_email_verif', 'add_email', 'verify_pw', 'complete_email_verif',
                            'login_flow', 'login_js_flow', 'enter_login_flow', 'enter_pw_flow', 'sso_init']:
        # params
        params = {
            "variables": json_to_str(variables),
            "features": json_to_str(features)
            # "fieldToggles": json_to_str(toggles)
        }
        #params = urllib.parse.urlencode(params).encode('utf-8')
        #print(params)
        if toggles:
            params['fieldToggles'] = json_to_str(toggles)

    # request
    for i in range(4):

        # if api_endpoint != 'Following' and not use_current_acc and not twitter_working_account:
        #     twitter_working_account = get_next_acc2()
        # elif use_current_acc:
        #     twitter_working_account = get_next_acc2(get_current=True)

        # for i in range(15):
        try:

            if api_endpoint in ['Following']:
                twitter_cookies_dict = twitter_working_account["cookies_dict"]
                headers = get_headers_for_twitter_account(twitter_cookies_dict, referer)
                # proxies = get_proxies_for_twitter_account(twitter_working_account)

                response = twitter_working_account['session'].get(base_url, params=params, headers=headers)

                if (response.status_code == 429) or (response.text.strip("\n") == "Rate limit exceeded"):
                    raise RateLimitExceededError("Rate limit exceeded")


                js = response.json()  # json.decoder.JSONDecodeError
                if "errors" in js:
                    # "ct0" --> {"errors":[{"code":353,"message":"This request requires a matching csrf cookie and header."}]}
                    # "auth_token" --> {"errors":[{"message":"Could not authenticate you","code":32}]}
                    errors_messages = "; ".join([f"{error['code']}: {error['message']}" for error in js[
                        "errors"]])  # '{"errors":[{"code":353,"message":"This request requires a matching csrf cookie and header."}]}' --> '353: This request requires a matching csrf cookie and header.'
                    raise ValueError(errors_messages)

            else:

                # setting headers
                headers = {
                    'referer': referer,
                    'user-agent': twitter_working_account['ua']
                }

                if api_endpoint in ['View']:
                    headers['content-type'] = 'application/x-www-form-urlencoded'

                if api_endpoint in ['View', 'change_profile', 'change_pw', 'add_email', 'verify_pw']:
                    # print('base url', base_url)
                    # print('headers', headers)
                    # print('variables', variables)
                    response = twitter_working_account['session'].request_client.request(base_url, method='POST',
                                                                                         data=params if params else variables,
                                                                                         headers=headers)
                elif api_endpoint in ['FavoriteTweet', 'CreateRetweet', 'CreateBookmark', 'CreateTweet', 'begin_email_verif', 'complete_email_verif',
                                      'login_flow', 'login_js_flow', 'enter_login_flow', 'enter_pw_flow', 'sso_init']:
                    response = twitter_working_account['session'].request_client.request(base_url, method='POST',
                                                                                         json=params if params else variables,
                                                                                         headers=headers)
                else:
                    response = twitter_working_account['session'].request_client.request(base_url, params=params if params else None, headers=headers)

                if 'Authorization: Denied by access control' in str(response):
                    print(response)

        except (ReadTimeout, ProxyError, ConnectTimeout, OSError, SSLError, ConnectionError, ProxyError1):
            trace = traceback.format_exc()
            print(trace)
            time.sleep(5)
            if i == 3:
                return 'proxy_dead'

        except Exception as error:
            trace = traceback.format_exc()
            print(trace)
            time.sleep(1.5)
            # json.decoder.JSONDecodeError, ValueError ==> most likely problem with twitter account, need to use another account

            # if 'SearchQueryParsingException' in str(error):
            #     os.execv(sys.executable, [sys.executable] + sys.argv)
            # elif '32: Could not authenticate you' in str(error):
            #     admin_error(f'Twitter error: 32: Could not authenticate you !!!')
            # elif '326: Authorization' in str(error):
            #     admin_error(f'Twitter error: 326: Authorization !!!')
            # elif '407 Proxy Authentication' in str(error):
            #     print('proxy error')
            #     if i == 14:
            #         admin_signal(f'Proxy Error 15 раз подряд в функции twitter_api_call модуля twitter_search.py! Log: {traceback.format_exc()}')
            #         return
            #     continue
            # elif 'Not found' in str(error):
            #     print('not found error')
            #     if i == 14:
            #         admin_signal(f'Not Found Error 15 раз подряд в функции twitter_api_call модуля twitter_search.py! Log: {traceback.format_exc()}')
            #         return
            #     continue

        else:
            return response

    if 'Error code 131 - Internal error' in trace:
        return '131'

    elif 'Error code 139 - Authorization: Actor' in trace:
        return '139'

    elif 'Error code 34 - Sorry, that page does not exist' in trace:
        return 'ban'

    elif 'Error code 64 - Your account is suspended' in trace:
        return 'ban'

    elif 'Error code 32 - Could not authenticate you' in trace:
        return 'no_auth'

    elif 'Error code 326 - Authorization' in trace:
        return 'lock'

    elif 'Error code 141 - Authorization' in trace:
        return 'ban'

    elif 'Error code 398 - Due to new session' in trace:
        return '48h'

    elif 'Error code 114 - Incorrect current password' in trace:
        return 'incorrect_pw'

    elif '_Missing: Tweet record for tweetId' in trace:
        return 'deleted'

# поиск пользователей по ключевому слову
def search_people(search_query):
    variables = {
        "rawQuery": f"{search_query}",
        "count": 20,
        "querySource": "recent_search_click",
        "product": "People"
    }
    features = {
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "responsive_web_home_pinned_timelines_enabled": True,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "c9s_tweet_anatomy_moderator_badge_enabled": False,
        "tweetypie_unmention_optimization_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": False,
        "tweet_awards_web_tipping_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_media_download_video_enabled": False,
        "responsive_web_enhance_cards_enabled": False
    }
    response = twitter_api_call('SearchTimeline', variables, features)
    js = response.json()
    instructions = js["data"]["search_by_raw_query"]["search_timeline"]["timeline"]["instructions"]
    users_parsed_current_page = parse_users_instructions(instructions)
    users = users_parsed_current_page["users"]
    return users

# поиск твитов по списку ключевых слов
def search_recent_tweets(keyword_or_keywords, filter_reply=False, from_usernames=None, since_from=None, last_seen_tweet_id=None, last_seen_tweet_ts=None):
    # https://developer.twitter.com/en/docs/twitter-api/tweets/search/integrate/build-a-query#limits
    # Your queries will be limited depending on which access level you are using.
    # If you have Basic or Pro access, your query can be 512 characters long for recent search endpoint.
    # If you have Pro access, your query can be 1,024 characters long for full archive search endpoint.

    print("Starting search_recent_tweets")
    print(f"Input keywords: {keyword_or_keywords}")
    print(f"From usernames: {from_usernames}")
    print(f"Since from: {since_from}")
    print(f"Last seen tweet ID: {last_seen_tweet_id}")
    print(f"Last seen tweet TS: {last_seen_tweet_ts}")

    # формирование строки поискового запроса:
    # 1) ключевые слова
    if isinstance(keyword_or_keywords, list):
        # keyword_or_keywords = ['0x6213f40e00F4595AA038FA710e3f837b492d6757', '0x40166Be57700B57F591Ce5781da8EC36d31dC462', '0x1a0120eAB44157ba10D767e0F4A38a0A6452BCf9'] ==> '(0x6213f40e00F4595AA038FA710e3f837b492d6757 OR 0x40166Be57700B57F591Ce5781da8EC36d31dC462 OR 0x1a0120eAB44157ba10D767e0F4A38a0A6452BCf9)'
        search_text = f"({' OR '.join(keyword_or_keywords)})"
        # keyword_or_keywords = ['0x6213f40e00F4595AA038FA710e3f837b492d6757', '0x40166Be57700B57F591Ce5781da8EC36d31dC462', '0x1a0120eAB44157ba10D767e0F4A38a0A6452BCf9'] ==> "('0x6213f40e00F4595AA038FA710e3f837b492d6757' OR '0x40166Be57700B57F591Ce5781da8EC36d31dC462' OR '0x1a0120eAB44157ba10D767e0F4A38a0A6452BCf9')"
        # search_text = f"""('{"' OR '".join(keyword_or_keywords)}')"""
    elif isinstance(keyword_or_keywords, str):
        # keyword_or_keywords = '0x6213f40e00F4595AA038FA710e3f837b492d6757'
        search_text = keyword_or_keywords

    # 2) имена авторов
    if from_usernames:
        # from_usernames = ['elonmusk', 'matt_furie', 'cz_binance', 'binance', 'sbf_ftx', 'vitalikbuterin', 'beeple']
        search_text += f" ({' OR '.join(['from:' + username for username in from_usernames])})"

    # 3) начиная с даты
    if since_from:
        # since_from = "2023-11-09"
        search_text += f" since:{since_from}"

    if filter_reply:
        search_text += ' -filter:replies'

    print("===> Поисковый запрос: ", search_text)


    variables = {
        "rawQuery": search_text,
        "count": 50,
        "cursor": "",
        "querySource": "typed_query", # possible values: "typed_query", "recent_search_click"
        "product": "Latest" # possible values: "Top", "Latest", "People", "Media", "Lists"
    }
    features = {
        "rweb_video_screen_enabled": False,
        "profile_label_improvements_pcf_label_in_post_enabled": True,
        "rweb_tipjar_consumption_enabled": True,
        "verified_phone_label_enabled": False,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "premium_content_api_read_enabled": False,
        "communities_web_enable_tweet_community_results_fetch": True,
        "c9s_tweet_anatomy_moderator_badge_enabled": True,
        "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
        "responsive_web_grok_analyze_post_followups_enabled": True,
        "responsive_web_jetfuel_frame": False,
        "responsive_web_grok_share_attachment_enabled": True,
        "articles_preview_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": True,
        "tweet_awards_web_tipping_enabled": False,
        "responsive_web_grok_show_grok_translated_post": False,
        "responsive_web_grok_analysis_button_from_backend": True,
        "creator_subscriptions_quote_tweet_preview_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_grok_image_annotation_enabled": True,
        "responsive_web_enhance_cards_enabled": False,
        'responsive_web_graphql_exclude_directive_enabled': True,
        'rweb_lists_timeline_redesign_enabled': True,
        'tweetypie_unmention_optimization_enabled': True
    }
    # print(urllib.parse.urlencode(params))

    page = 1
    load_next_page = True
    tweets_parsed = []
    reached_last_seen = False
    most_recent_tweet_id = None  # this will be returned
    most_recent_tweet_ts = None  # this will be returned
    is_first_request = last_seen_tweet_id is None

    while load_next_page:
        print(f"Fetching page {page} with cursor: {variables['cursor']}")
        js = twitter_api_call('SearchTimeline', variables, features, use_current_acc=True if page > 1 else False)
        # js = response.json()

        instructions = js["data"]["search_by_raw_query"]["search_timeline"]["timeline"]["instructions"]
        tweets_parsed_current_page = parse_tweets_instructions(instructions)
        current_tweets = tweets_parsed_current_page["tweets"]

        print(f"Parsed {len(current_tweets)} tweets on page {page}")

        if not current_tweets:
            print("No more tweets found, stopping.")
            break

        for tweet_parsed in current_tweets:
            tweet_id = tweet_parsed["tweet"]["id"]
            tweet_timestamp = tweet_parsed["tweet"]["created_at_timestamp"]

            # save the first tweet's id (most recent) from the first page
            if page == 1 and most_recent_tweet_id is None:
                most_recent_tweet_id = tweet_id
                most_recent_tweet_ts = tweet_timestamp

                print(f"Most recent tweet ID set to: {most_recent_tweet_id} with ts creation in {most_recent_tweet_ts}")

            # if we've reached the tweet from the previous run, stop
            if not is_first_request and (tweet_id <= last_seen_tweet_id or tweet_timestamp < last_seen_tweet_ts):
                print(f"Reached last seen tweet ID: {tweet_id}, stopping.")
                reached_last_seen = True
                load_next_page = False
                break

            tweets_parsed.append(tweet_parsed)

        # If there are no more tweets or we reached the end or its first request after starting the script
        if is_first_request or reached_last_seen or not tweets_parsed_current_page["cursors"].get("bottom") or page >= 5:
            print("No bottom cursor or reached last seen tweet or its first req or got page limits, stopping pagination.")
            break

        page += 1
        variables["cursor"] = tweets_parsed_current_page["cursors"]["bottom"]
        print(f"Moving to next page, cursor: {variables['cursor']}")

    print(f"Total tweets parsed: {len(tweets_parsed)}")
    print(f"Returning most recent tweet ID: {most_recent_tweet_id}")

    return tweets_parsed, most_recent_tweet_id, most_recent_tweet_ts, js['twitter_working_account']

# поиск твитов от конкретных аккаунтов через search
def search_user_recent_tweets(from_usernames):
    # https://developer.twitter.com/en/docs/twitter-api/tweets/search/integrate/build-a-query#limits
    # Your queries will be limited depending on which access level you are using.
    # If you have Basic or Pro access, your query can be 512 characters long for recent search endpoint.
    # If you have Pro access, your query can be 1,024 characters long for full archive search endpoint.

    # 2) имена авторов
    if from_usernames:
        # from_usernames = ['elonmusk', 'matt_furie', 'cz_binance', 'binance', 'sbf_ftx', 'vitalikbuterin', 'beeple']
        search_text = f"({' OR '.join(['from:' + username for username in from_usernames])})"

    print("===> Поисковый запрос: ", search_text)

    variables = {
        "rawQuery": search_text,
        "count": 20,
        "cursor": "",
        "querySource": "typed_query", # possible values: "typed_query", "recent_search_click"
        "product": "Latest" # possible values: "Top", "Latest", "People", "Media", "Lists"
    }
    features = {
        "rweb_video_screen_enabled": False,
        "profile_label_improvements_pcf_label_in_post_enabled": True,
        "rweb_tipjar_consumption_enabled": True,
        "verified_phone_label_enabled": False,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "premium_content_api_read_enabled": False,
        "communities_web_enable_tweet_community_results_fetch": True,
        "c9s_tweet_anatomy_moderator_badge_enabled": True,
        "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
        "responsive_web_grok_analyze_post_followups_enabled": True,
        "responsive_web_jetfuel_frame": False,
        "responsive_web_grok_share_attachment_enabled": True,
        "articles_preview_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": True,
        "tweet_awards_web_tipping_enabled": False,
        "responsive_web_grok_show_grok_translated_post": False,
        "responsive_web_grok_analysis_button_from_backend": True,
        "creator_subscriptions_quote_tweet_preview_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_grok_image_annotation_enabled": True,
        "responsive_web_enhance_cards_enabled": False,
        'responsive_web_graphql_exclude_directive_enabled': True,
        'rweb_lists_timeline_redesign_enabled': True,
        'tweetypie_unmention_optimization_enabled': True
    }
    # print(urllib.parse.urlencode(params))

    # print(f"page = {page}")
    js = twitter_api_call('SearchTimeline', variables, features)

    try:
        users_recent_tweets = {}
        instructions = js["data"]["search_by_raw_query"]["search_timeline"]["timeline"]["instructions"]
        tweets_parsed_current_page = parse_tweets_instructions(instructions)
        # page = 1
        # tweets_parsed = []
        # for tweet_parsed in tweets_parsed_current_page["tweets"]:
        #     if (len(tweets_parsed) < recent_user_tweets_count_limit):  # and ((not remove_tweets_from_other_users) or (user_id == tweet_parsed["user"]["id"])):
        #         tweet_parsed["page"] = page
        #         tweet_parsed["num"] = len(tweets_parsed) + 1
        #         tweets_parsed.append(tweet_parsed)

        for tweet in tweets_parsed_current_page['tweets']:
            screen_name = tweet['user']['screen_name']
            if screen_name not in users_recent_tweets:
                users_recent_tweets[screen_name] = [[], js['twitter_working_account']]
            users_recent_tweets[screen_name][0].append(tweet)

        return users_recent_tweets
    except (TypeError, KeyError):
        print(traceback.format_exc())

# получение твитов конкретного пользователя через профиль
def get_user_recent_tweets(user_id, tweets_count=20, cursor="", with_replies=False):
    # user_id = 2483453401
    remove_tweets_from_other_users = True
    variables = {
        "userId": user_id,
        "count": tweets_count,
        "cursor": cursor,
        "includePromotedContent": True,
        "withQuickPromoteEligibilityTweetFields": True,
        "withVoice": True,
        "withV2Timeline": True
    }

    features = {
        "rweb_video_screen_enabled": False,
        "profile_label_improvements_pcf_label_in_post_enabled": True,
        "rweb_tipjar_consumption_enabled": True,
        "verified_phone_label_enabled": False,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "premium_content_api_read_enabled": False,
        "communities_web_enable_tweet_community_results_fetch": True,
        "c9s_tweet_anatomy_moderator_badge_enabled": True,
        "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
        "responsive_web_grok_analyze_post_followups_enabled": False,
        "responsive_web_jetfuel_frame": False,
        "responsive_web_grok_share_attachment_enabled": True,
        "articles_preview_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": True,
        "tweet_awards_web_tipping_enabled": False,
        "responsive_web_grok_show_grok_translated_post": False,
        "responsive_web_grok_analysis_button_from_backend": False,
        "creator_subscriptions_quote_tweet_preview_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_grok_image_annotation_enabled": True,
        "responsive_web_enhance_cards_enabled": False
    }

    js = twitter_api_call('UserTweetsAndReplies' if with_replies else 'UserTweets', variables, features)
    # print(js)
    # js = response.json()
    try:
        try:
            instructions = js["data"]["user"]["result"]["timeline_v2"]["timeline"]["instructions"]
        except KeyError:
            instructions = js["data"]["user"]["result"]["timeline"]["timeline"]["instructions"]
        tweets_parsed_current_page = parse_tweets_instructions(instructions)

        page = 1
        tweets_parsed = []
        for tweet_parsed in tweets_parsed_current_page["tweets"]:
            if (len(tweets_parsed) < recent_user_tweets_count_limit): # and ((not remove_tweets_from_other_users) or (user_id == tweet_parsed["user"]["id"])):
                tweet_parsed["page"] = page
                tweet_parsed["num"] = len(tweets_parsed) + 1
                tweets_parsed.append(tweet_parsed)

        user_recent_tweets = {user_id: [tweets_parsed, js['twitter_working_account']]}
        return user_recent_tweets
    except (TypeError, KeyError):
        print(traceback.format_exc())
        return {user_id: [[], js['twitter_working_account']]}

def get_user_by_user_id(user_id):
    # user_id = 2483453401
    variables = {
        "userIds":[
            user_id
        ]
    }
    features = {
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "responsive_web_graphql_timeline_navigation_enabled": True
    }
    response = twitter_api_call('UsersByRestIds', variables, features)
    js = response.json()
    user_raw = js["data"]["users"][0]["result"]
    user_parsed = parse_user(user_raw)
    return user_parsed

def get_user_screen_name_by_user_id(user_id):
    # user_id = 2483453401
    user = get_user_by_user_id(user_id)
    return user["screen_name"]

def get_user_by_user_screen_name(user_screen_name, twitter_working_account=None):
    # user_screen_name = "Dyna_anji"
    variables = {
        "screen_name": user_screen_name,
        "withSafetyModeUserFields": True
    }

    features = {
        "hidden_profile_subscriptions_enabled": True,
        "rweb_tipjar_consumption_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "subscriptions_verification_info_is_identity_verified_enabled": True,
        "subscriptions_verification_info_verified_since_enabled": True,
        "highlights_tweets_tab_ui_enabled": True,
        "responsive_web_twitter_article_notes_tab_enabled": True,
        "subscriptions_feature_can_gift_premium": True,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True
    }
    # fieldToggles = {"withAuxiliaryUserLabels": False}
    try:
        response = twitter_api_call('UserByScreenName', variables, features, twitter_working_account)
        js = response.json()
        user_raw = js["data"]["user"]["result"]
        user_parsed = parse_user(user_raw)
    except KeyError:
        print("ошибка при получении пользователя: ", user_screen_name)
        admin_error(f"ошибка при получении пользователя: {user_screen_name}")

    return user_parsed

def get_user_id_by_user_screen_name(user_screen_name, twitter_working_account=None):
    # user_screen_name = "Dyna_anji"
    user = get_user_by_user_screen_name(user_screen_name, twitter_working_account)
    return user["id"]


def get_community_members(com_id, dump=False, output_file="members.json"):

    variables = {
        'communityId': com_id,
        'cursor': None
    }

    features = {
        'responsive_web_graphql_timeline_navigation_enabled': True
    }

    page = 1
    load_next_page = True
    members_parsed = []

    while load_next_page:
        print(f"Fetching page {page} with cursor: {variables['cursor']}")
        js = twitter_api_call('membersSliceTimeline_Query', variables, features)

        members_slice = js["data"]["communityResults"]["result"]["members_slice"]
        items = members_slice["items_results"]

        print(f"Parsed {len(items)} members on page {page}")

        if not items:
            print("No more members found, stopping.")
            break

        page_members = []
        for member_parsed in items:
            member_id = member_parsed["result"]["rest_id"]
            member_username = member_parsed["result"]["core"]["screen_name"]

            page_members.append({
                "id": member_id,
                "username": member_username
            })

        # добавляем к общему списку
        members_parsed.extend(page_members)

        if dump:
            # пишем сразу после страницы
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(members_parsed, f, ensure_ascii=False, indent=2)

            print(f"Saved {len(members_parsed)} total members to {output_file}")

        # Проверяем, есть ли следующая страница
        if not members_slice["slice_info"].get("next_cursor"):
            print("No next cursor, stopping pagination.")
            break

        page += 1
        variables["cursor"] = members_slice["slice_info"]["next_cursor"]
        print(f"Moving to next page, cursor: {variables['cursor']}")

    print(f"Total members parsed: {len(members_parsed)}")
    return members_parsed


def like_tweet_by_tweet_id(working_acc, tweet_id):

    data = {"variables": {"tweet_id": tweet_id}}

    res = twitter_api_call('FavoriteTweet', variables=data, features={}, twitter_working_account=working_acc)

    if res in ['139', 'ban', 'proxy_dead', 'no_auth', 'lock', 'deleted']:
        return res

    if res and res['data']['favorite_tweet']:
        return True

    return False

def rt_tweet_by_tweet_id(working_acc, tweet_id):

    data = {"variables": {"tweet_id": tweet_id, "dark_request": False}}

    res = twitter_api_call('CreateRetweet', variables=data, features={}, twitter_working_account=working_acc)

    if res in ['139', 'ban', 'proxy_dead', 'no_auth', 'lock', 'deleted']:
        return res

    if res and res['data']['create_retweet']['retweet_results']['result']['rest_id']:
        return True

    return False

def bm_tweet_by_tweet_id(working_acc, tweet_id):

    data = {"variables":{"tweet_id":tweet_id}}

    res = twitter_api_call('CreateBookmark', variables=data, features={}, twitter_working_account=working_acc)

    if res in ['139', 'ban', 'proxy_dead', 'no_auth', 'lock', 'deleted']:
        return res

    if res and res['data']['tweet_bookmark_put']:
        return True

    return False

def reply_tweet_by_tweet_id(working_acc, reply_text, tweet_id):

    variables = {
        "tweet_text": reply_text,
        "reply": {
            "in_reply_to_tweet_id": tweet_id,
            "exclude_reply_user_ids": []
        },
        "dark_request": False,
        "media": {
            "media_entities": [],
            "possibly_sensitive": False
        },
        "semantic_annotation_ids": [],
        "disallowed_reply_options": None
    }

    features = {
        "premium_content_api_read_enabled": False,
        "communities_web_enable_tweet_community_results_fetch": True,
        "c9s_tweet_anatomy_moderator_badge_enabled": True,
        "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
        "responsive_web_grok_analyze_post_followups_enabled": True,
        "responsive_web_jetfuel_frame": True,
        "responsive_web_grok_share_attachment_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": True,
        "tweet_awards_web_tipping_enabled": False,
        "responsive_web_grok_show_grok_translated_post": True,
        "responsive_web_grok_analysis_button_from_backend": True,
        "creator_subscriptions_quote_tweet_preview_enabled": False,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "payments_enabled": False,
        "rweb_xchat_enabled": False,
        "profile_label_improvements_pcf_label_in_post_enabled": True,
        "rweb_tipjar_consumption_enabled": True,
        "verified_phone_label_enabled": False,
        "articles_preview_enabled": True,
        "responsive_web_grok_community_note_auto_translation_is_enabled": False,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "responsive_web_grok_image_annotation_enabled": True,
        "responsive_web_grok_imagine_annotation_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_enhance_cards_enabled": False
    }

    res = twitter_api_call('CreateTweet', variables=variables, features=features, twitter_working_account=working_acc)

    if res and res['data']['create_tweet']['tweet_results']['result']['rest_id']:
        return True

    if res in ['ban', 'proxy_dead', 'no_auth', 'lock', 'deleted']:
        return res

    return False

def view_tweet_by_tweet_id(working_acc, tweet_id, author_id, profile_click=False, duplicate=1):

    # maximum views per 1 account == 300

    # view_and_impression_data = 'debug=true&log=[{"_category_":"client_event","format_version":2,"triggered_on":1757401660004,"items":[{"item_type":0,"id":"1935709990523691058","position":0,"sort_index":"1965311119690039296","suggestion_details":{"controller_data":"DAACDAABDAABCgABAAAAAAAAAAAKAAkS2znq4FdgBQAAAAA=","suggestion_type":"RankedOrganicTweet"},"percent_screen_height_100k":155991,"author_id":"1358743393531289605","is_viewer_follows_tweet_author":false,"is_tweet_author_follows_viewer":false,"is_viewer_super_following_tweet_author":false,"is_viewer_super_followed_by_tweet_author":false,"is_tweet_author_super_followable":false,"engagement_metrics":{"reply_count":0,"retweet_count":0,"favorite_count":1,"quote_count":0}}],"event_namespace":{"page":"tweet","component":"stream","action":"results","client":"m5"},"client_event_sequence_start_timestamp":1757401657818,"client_event_sequence_number":4,"client_app_id":"3033300"}]'

    view_and_impression_data = make_payload_for_view(events=[{'id': tweet_id, 'author_id': author_id}], duplicate=duplicate)

    if profile_click:
        view_and_impression_data = view_and_impression_data[:-1]
        view_and_impression_data += ',{"_category_":"client_event","format_version":2,"triggered_on":1757406720198,"items":[{"item_type":0,"id":"1935709990523691058","author_id":"1358743393531289605","is_viewer_follows_tweet_author":false,"is_tweet_author_follows_viewer":false,"is_viewer_super_following_tweet_author":false,"is_viewer_super_followed_by_tweet_author":false,"is_tweet_author_super_followable":false,"engagement_metrics":{"reply_count":0,"retweet_count":0,"favorite_count":1,"quote_count":0},"position":0,"sort_index":"1965332019202228224","suggestion_details":{"controller_data":"DAACDAABDAABCgABAAAAAAAAAAAKAAkS2znq4FdgBQAAAAA=","suggestion_type":"RankedOrganicTweet"}},{"item_type":3,"id":"1358743393531289605","is_viewer_follows_user":false,"is_user_follows_viewer":false,"is_viewer_super_following_user":false,"is_viewer_super_followed_by_user":false,"is_user_super_followable":false}],"profile_id":"1358743393531289600","event_namespace":{"page":"tweet","component":"tweet","element":"user","action":"profile_click","client":"m5"},"client_event_sequence_start_timestamp":1757406640371,"client_event_sequence_number":55,"client_app_id":"3033300"}]'

    # data = 'debug=true&log=[{"_category_":"client_event","format_version":2,"triggered_on":1757401658960,"tweet_id":"1935709990523691058","items":[{"item_type":0,"id":"1935709990523691058"}],"event_namespace":{"page":"tweet","action":"show","client":"m5"},"client_event_sequence_start_timestamp":1757401657818,"client_event_sequence_number":2,"client_app_id":"3033300"},{"_category_":"client_event","format_version":2,"triggered_on":1757401659522,"tweet_id":"1935709990523691058","event_initiator":0,"new_entries":1,"new_tweets":1,"items":[{"item_type":0,"id":"1935709990523691058","author_id":"1358743393531289605","is_viewer_follows_tweet_author":false,"is_tweet_author_follows_viewer":false,"is_viewer_super_following_tweet_author":false,"is_viewer_super_followed_by_tweet_author":false,"is_tweet_author_super_followable":false,"engagement_metrics":{"reply_count":0,"retweet_count":0,"favorite_count":1,"quote_count":0}}],"event_namespace":{"page":"tweet","action":"get_initial","client":"m5"},"client_event_sequence_start_timestamp":1757401657818,"client_event_sequence_number":3,"client_app_id":"3033300"},{"_category_":"client_event","format_version":2,"triggered_on":1757401660004,"items":[{"item_type":0,"id":"1935709990523691058","position":0,"sort_index":"1965311119690039296","suggestion_details":{"controller_data":"DAACDAABDAABCgABAAAAAAAAAAAKAAkS2znq4FdgBQAAAAA=","suggestion_type":"RankedOrganicTweet"},"percent_screen_height_100k":155991,"author_id":"1358743393531289605","is_viewer_follows_tweet_author":false,"is_tweet_author_follows_viewer":false,"is_viewer_super_following_tweet_author":false,"is_viewer_super_followed_by_tweet_author":false,"is_tweet_author_super_followable":false,"engagement_metrics":{"reply_count":0,"retweet_count":0,"favorite_count":1,"quote_count":0}}],"event_namespace":{"page":"tweet","component":"stream","action":"results","client":"m5"},"client_event_sequence_start_timestamp":1757401657818,"client_event_sequence_number":4,"client_app_id":"3033300"}]' #,{"_category_":"client_event","format_version":2,"triggered_on":1757401660110,"event_namespace":{"page":"app","section":"permissions","component":"install_banner","action":"impression","client":"m5"},"client_event_sequence_start_timestamp":1757401657818,"client_event_sequence_number":5,"client_app_id":"3033300"},{"_category_":"client_event","format_version":2,"triggered_on":1757401660286,"tweet_id":"1935709990523691058","event_initiator":0,"new_entries":1,"new_tweets":0,"items":[{"item_type":0,"id":"1935709990523691058","author_id":"1358743393531289605","is_viewer_follows_tweet_author":false,"is_tweet_author_follows_viewer":false,"is_viewer_super_following_tweet_author":false,"is_viewer_super_followed_by_tweet_author":false,"is_tweet_author_super_followable":false,"engagement_metrics":{"reply_count":0,"retweet_count":0,"favorite_count":1,"quote_count":0}}],"event_namespace":{"page":"tweet","section":"sidebar","action":"get_initial","client":"m5"},"client_event_sequence_start_timestamp":1757401657818,"client_event_sequence_number":6,"client_app_id":"3033300"},{"_category_":"client_event","format_version":2,"triggered_on":1757401660397,"tweet_id":"1935709990523691058","position":0,"items":[{"item_type":0,"id":"1935709990523691058","author_id":"1358743393531289605","is_viewer_follows_tweet_author":false,"is_tweet_author_follows_viewer":false,"is_viewer_super_following_tweet_author":false,"is_viewer_super_followed_by_tweet_author":false,"is_tweet_author_super_followable":false,"engagement_metrics":{"reply_count":0,"retweet_count":0,"favorite_count":1,"quote_count":0}}],"event_namespace":{"page":"tweet","section":"sidebar","component":"unified_events","action":"impression","client":"m5"},"client_event_sequence_start_timestamp":1757401657818,"client_event_sequence_number":7,"client_app_id":"3033300"},{"_category_":"client_event","format_version":2,"triggered_on":1757401660397,"tweet_id":"1935709990523691058","items":[{"item_type":0,"id":"1935709990523691058","author_id":"1358743393531289605","is_viewer_follows_tweet_author":false,"is_tweet_author_follows_viewer":false,"is_viewer_super_following_tweet_author":false,"is_viewer_super_followed_by_tweet_author":false,"is_tweet_author_super_followable":false,"engagement_metrics":{"reply_count":0,"retweet_count":0,"favorite_count":1,"quote_count":0}},{"item_type":8,"item_query":"Dankje","name":"Dankje","suggestion_details":{"controller_data":"DAACDAAQDAABCgABvB2I06BQCLcAAAAA"}}],"event_namespace":{"page":"tweet","section":"sidebar","component":"unified_events","element":"trend","action":"impression","client":"m5"},"client_event_sequence_start_timestamp":1757401657818,"client_event_sequence_number":8,"client_app_id":"3033300"},{"_category_":"client_event","format_version":2,"triggered_on":1757401660397,"tweet_id":"1935709990523691058","items":[{"item_type":0,"id":"1935709990523691058","author_id":"1358743393531289605","is_viewer_follows_tweet_author":false,"is_tweet_author_follows_viewer":false,"is_viewer_super_following_tweet_author":false,"is_viewer_super_followed_by_tweet_author":false,"is_tweet_author_super_followable":false,"engagement_metrics":{"reply_count":0,"retweet_count":0,"favorite_count":1,"quote_count":0}},{"item_type":8,"item_query":"oostende","name":"oostende","suggestion_details":{"controller_data":"DAACDAAQDAABCgABvB2I06BQCLcAAAAA"}}],"event_namespace":{"page":"tweet","section":"sidebar","component":"unified_events","element":"trend","action":"impression","client":"m5"},"client_event_sequence_start_timestamp":1757401657818,"client_event_sequence_number":9,"client_app_id":"3033300"},{"_category_":"client_event","format_version":2,"triggered_on":1757401660397,"tweet_id":"1935709990523691058","items":[{"item_type":0,"id":"1935709990523691058","author_id":"1358743393531289605","is_viewer_follows_tweet_author":false,"is_tweet_author_follows_viewer":false,"is_viewer_super_following_tweet_author":false,"is_viewer_super_followed_by_tweet_author":false,"is_tweet_author_super_followable":false,"engagement_metrics":{"reply_count":0,"retweet_count":0,"favorite_count":1,"quote_count":0}},{"item_type":8,"item_query":"#hypotheekrenteaftrek","name":"#hypotheekrenteaftrek","suggestion_details":{"controller_data":"DAACDAAQDAABCgABvB2I06BQCLcAAAAA"}}],"event_namespace":{"page":"tweet","section":"sidebar","component":"unified_events","element":"trend","action":"impression","client":"m5"},"client_event_sequence_start_timestamp":1757401657818,"client_event_sequence_number":10,"client_app_id":"3033300"},{"_category_":"client_event","format_version":2,"triggered_on":1757401660397,"tweet_id":"1935709990523691058","items":[{"item_type":0,"id":"1935709990523691058","author_id":"1358743393531289605","is_viewer_follows_tweet_author":false,"is_tweet_author_follows_viewer":false,"is_viewer_super_following_tweet_author":false,"is_viewer_super_followed_by_tweet_author":false,"is_tweet_author_super_followable":false,"engagement_metrics":{"reply_count":0,"retweet_count":0,"favorite_count":1,"quote_count":0}},{"item_type":8,"item_query":"PvdD","name":"PvdD","suggestion_details":{"controller_data":"DAACDAAQDAABCgABvB2I06BQCLcAAAAA"}}],"event_namespace":{"page":"tweet","section":"sidebar","component":"unified_events","element":"trend","action":"impression","client":"m5"},"client_event_sequence_start_timestamp":1757401657818,"client_event_sequence_number":11,"client_app_id":"3033300"},{"_category_":"client_event","format_version":2,"triggered_on":1757401660397,"tweet_id":"1935709990523691058","items":[{"item_type":0,"id":"1935709990523691058","author_id":"1358743393531289605","is_viewer_follows_tweet_author":false,"is_tweet_author_follows_viewer":false,"is_viewer_super_following_tweet_author":false,"is_viewer_super_followed_by_tweet_author":false,"is_tweet_author_super_followable":false,"engagement_metrics":{"reply_count":0,"retweet_count":0,"favorite_count":1,"quote_count":0}}],"event_namespace":{"page":"tweet","section":"sidebar","component":"unified_events","element":"footer","action":"impression","client":"m5"},"client_event_sequence_start_timestamp":1757401657818,"client_event_sequence_number":12,"client_app_id":"3033300"}]'

    res = twitter_api_call('View', variables=view_and_impression_data, features={}, twitter_working_account=working_acc)

    if res in ['ban', 'proxy_dead', 'no_auth', 'lock', 'deleted']:
        return res

    if res:
        return True

    return False

def make_payload_for_view(events, duplicate=1):
    """
    events: список словарей с нужными полями:
        - id (tweet id)
        - author_id
    duplicate: сколько раз повторить event
    """
    log_items = []
    for e in events:
        event = {
            "_category_": "client_event",
            "format_version": 2,
            "triggered_on": int(time.time() * 1000),
            "items": [{
                "item_type": 0,
                "id": str(e["id"]),
                "position": 0,
                "sort_index": "1965311119690039296",
                "suggestion_details": {
                    "controller_data": "DAACDAABDAABCgABAAAAAAAAAAAKAAkS2znq4FdgBQAAAAA=",
                    "suggestion_type": "RankedOrganicTweet"
                },
                "percent_screen_height_100k": 155991,
                "author_id": str(e["author_id"]),
                "is_viewer_follows_tweet_author": False,
                "is_tweet_author_follows_viewer": False,
                "is_viewer_super_following_tweet_author": False,
                "is_viewer_super_followed_by_tweet_author": False,
                "is_tweet_author_super_followable": False,
                "engagement_metrics": {
                    "reply_count": 0,
                    "retweet_count": 0,
                    "favorite_count": 1,
                    "quote_count": 0
                }
            }],
            "event_namespace": {
                "page": "tweet",
                "component": "stream",
                "action": "results",
                "client": "m5"
            },
            "client_event_sequence_start_timestamp": int(time.time() * 1000),
            "client_event_sequence_number": 4,
            "client_app_id": "3033300"
        }
        # добавляем несколько копий (если нужно)
        log_items.extend([event] * duplicate)

    # собираем payload
    log_json = json.dumps(log_items, separators=(",", ":"))
    return f"debug=true&log={log_json}"


def change_profile_info(working_acc, description, name=None):

    profile_data = {
        # "birthdate_day": 18,
        # "birthdate_month": 7,
        # "birthdate_year": 1998,
        # "birthdate_visibility": "self",
        # "birthdate_year_visibility": "self",
        # "displayNameMaxLength": 50,
        # "url": "http://t.me/ChadMarketing",
        # "name": name,
        "description": description,
        # "location": "Singapore"
    }

    if name:
        profile_data['name'] = name

    res = twitter_api_call('change_profile', variables=profile_data, features={}, twitter_working_account=working_acc)

    if res == '131':  # невозможно сменить аву (неизвестная ошибка)
        return res

    if res in ['ban', 'proxy_dead', 'no_auth', 'lock']:
        return res

    if res:
        return True

    return False


def get_phone_mail_data(working_acc):

    res = twitter_api_call('get_mail_phone', variables={}, features={}, twitter_working_account=working_acc)

    if res == '131':
        return res

    if res in ['ban', 'proxy_dead', 'no_auth', 'lock']:
        return res

    if res:
        return res

    return False


def change_email(working_acc: dict, new_email_data: dict):

    # verify_pw = f'password={working_acc["pass"]}'
    pw_data = {
        'password': working_acc["pass"]
    }
    res = twitter_api_call('verify_pw', variables=pw_data, features={}, twitter_working_account=working_acc)

    if res in ['ban', 'proxy_dead', 'no_auth', 'lock', 'incorrect_pw']:
        return res

    time.sleep(3)

    add_email_data = {"input_flow_data":{"flow_context":{"debug_overrides":{},"start_location":{"location":"settings"}}},"subtask_versions":{"action_list":2,"alert_dialog":1,"app_download_cta":1,"check_logged_in_account":1,"choice_selection":3,"contacts_live_sync_permission_prompt":0,"cta":7,"email_verification":2,"end_flow":1,"enter_date":1,"enter_email":2,"enter_password":5,"enter_phone":2,"enter_recaptcha":1,"enter_text":5,"enter_username":2,"generic_urt":3,"in_app_notification":1,"interest_picker":3,"js_instrumentation":1,"menu_dialog":1,"notifications_permission_prompt":2,"open_account":2,"open_home_timeline":1,"open_link":1,"phone_verification":4,"privacy_options":1,"security_key":3,"select_avatar":4,"select_banner":2,"settings_list":7,"show_code":1,"sign_up":2,"sign_up_review":4,"tweet_selection_urt":1,"update_users":1,"upload_media":1,"user_recommendations_list":4,"user_recommendations_urt":1,"wait_spinner":3,"web_modal":1}}
    res = twitter_api_call('add_email', variables=add_email_data, features={}, twitter_working_account=working_acc)

    if res in ['ban', 'proxy_dead', 'no_auth', 'lock', '48h']:
        return res

    elif res['flow_token'] and res['status'] == 'success':

        time.sleep(3)

        castle_token = 'undefined'
        flow_token = res['flow_token']

        begin_data = {
            'email': new_email_data['email'],
            'flow_token': flow_token,
            'castle_token': castle_token
        }
        res = twitter_api_call('begin_email_verif', variables=begin_data, features={}, twitter_working_account=working_acc)

        if res in ['ban', 'proxy_dead', 'no_auth', 'lock']:
            return res

        code = get_code_from_email(new_email_data['email'], new_email_data['proxy'])
        email_verif_data = {"flow_token":flow_token,"subtask_inputs":[{"subtask_id":"EmailAssocEnterEmail","enter_email":{"setting_responses":[{"key":"email_discoverability_setting","response_data":{"boolean_data":{"result":False}}}],"email":new_email_data['email'],"link":"next_link"}},{"subtask_id":"EmailAssocVerifyEmail","email_verification":{"code":code,"email":new_email_data['email'],"link":"next_link"}}]}
        res = twitter_api_call('complete_email_verif', variables=email_verif_data, features={}, twitter_working_account=working_acc)

        if res in ['ban', 'proxy_dead', 'no_auth', 'lock']:
            return res

        elif res['flow_token'] and res['status'] == 'success':
            return True

        else:
            return False

# def flow_login(working_acc):
#     login_flow_data = {
#         "input_flow_data": {
#             "flow_context": {
#                 "debug_overrides": {},
#                 "start_location": {"location": "splash_screen"},
#             }
#         },
#         "subtask_versions": {
#             "action_list": 2,
#             "alert_dialog": 1,
#             "app_download_cta": 1,
#             "check_logged_in_account": 1,
#             "choice_selection": 3,
#             "contacts_live_sync_permission_prompt": 0,
#             "cta": 7,
#             "email_verification": 2,
#             "end_flow": 1,
#             "enter_date": 1,
#             "enter_email": 2,
#             "enter_password": 5,
#             "enter_phone": 2,
#             "enter_recaptcha": 1,
#             "enter_text": 5,
#             "enter_username": 2,
#             "generic_urt": 3,
#             "in_app_notification": 1,
#             "interest_picker": 3,
#             "js_instrumentation": 1,
#             "menu_dialog": 1,
#             "notifications_permission_prompt": 2,
#             "open_account": 2,
#             "open_home_timeline": 1,
#             "open_link": 1,
#             "phone_verification": 4,
#             "privacy_options": 1,
#             "security_key": 3,
#             "select_avatar": 4,
#             "select_banner": 2,
#             "settings_list": 7,
#             "show_code": 1,
#             "sign_up": 2,
#             "sign_up_review": 4,
#             "tweet_selection_urt": 1,
#             "update_users": 1,
#             "upload_media": 1,
#             "user_recommendations_list": 4,
#             "user_recommendations_urt": 1,
#             "wait_spinner": 3,
#             "web_modal": 1,
#         },
#     }
#     res = twitter_api_call('login_flow', variables=login_flow_data, features={}, twitter_working_account=working_acc)
#
#     print(res)
#
#     if res in ['ban', 'proxy_dead', 'no_auth', 'lock']:
#         return res
#
#     elif res['flow_token'] and res['status'] == 'success':
#
#         login_js_data = {
#             "flow_token": res['flow_token'],
#             "subtask_inputs": [
#                 {
#                     "subtask_id": "LoginJsInstrumentationSubtask",
#                     "js_instrumentation": {
#                         "response": json.dumps(
#                             {
#                                 "rf": {
#                                     "f1124914e5e3470f91a59730862dd33246015b938972172c4cfc1e2b590f97d9": -182,
#                                     "a47601d00f7d388e1911fb9fde69897f06bbf7c6ab6871e8a95a922aa1138438": -42,
#                                     "e0e5510b2d08c4872bc27e8754576f6d996af62e51af15c64f133c8689c89071": 182,
#                                     "a3aacd25d4770567805a6d1b9be7bbe8db0cfd74cb66c61f1324584e6c9332e1": 181,
#                                 },
#                                 "s": "fRAFAWgc5BWcGViIG-jmRlt-xURC6SN98wNtTkI-Z_tscC-2V_8Mlb_rDSq2LQTK8QXPraY5dBA8vjlctfbRKBCqnlHtnWOKzL3_FwKg6hu2G9wFLaG-MhUZeBizkdqJRXrxkvaBUl9gQ4IulXPRtW1LYvbMuIhJxTIpFdj2JyXH7Dwy6MTxOEl_XQvJmpWlQ8q2gJq85N9mArw0XMPeTYCm0-ZFw_mgarbdyEBXG7G5180VEje53CBEBfrF6F2reHvtyY2KSmPaGbzqAhqe-jjW5bvgveYhcLC85wemsSIeNDWqwdq9BeiuoRkFbXBlIUUnIWS_qYdzp25noMpklQAAAZvvRksj",
#                             }
#                         ),
#                         "link": "next_link",
#                     },
#                 }
#             ],
#         }
#
#         res = twitter_api_call('login_js_flow', variables=login_js_data, features={}, twitter_working_account=working_acc)
#
#         print(res)
#
#         if res in ['ban', 'proxy_dead', 'no_auth', 'lock']:
#             return res
#
#         elif res['flow_token'] and res['status'] == 'success':
#
#             sso_init_data = {"provider": "apple"}
#             sso_res = twitter_api_call('sso_init', variables=sso_init_data, features={}, twitter_working_account=working_acc)
#             print(sso_res)
#
#             # sniffer_res = asyncio.run(sniff_headers(
#             #     url="https://x.com/i/flow/login",
#             #     watch={"castle_token"},
#             #     search_mode="payload",
#             #     only_types={"xhr", "fetch"},
#             #     stop_on_first=True,
#             # ))
#             #
#             # if sniffer_res.get('castle_token'):
#             #     castle_token = sniffer_res['castle_token']
#             # else:
#             #     return
#             castle_token = "Njs0U4FJyCbxziPL3FoNynqBTl-Fz2nf8EkmTFoB2PVOKkeonV4cZLJQghubtsbaeIRN6PDYXE_GPemo7gzc-hBk7YWYPheGiMKQeT0r9cH0a-bl0bL7LTFNqU-OgNyDkdaBKnc6mSMoYzEs_GWN-hhpxai9KnxKcKyuNfPoUBj8GCFDnHA7uznawaQhyYTt2jJKlVaATOQzvdvQQaPQXYga1keFaaAZcuQxAWhFauULDwesrheAjiwkexsJ2Emgeg9P3_Iv92OMZuqvs44jtILGcl9Vg7BTqV-2wryrbd0drdLBMIXfKCZ2p-Uc8Agtkw1lL1pXpnfxGmyPRXUTWsFYAGaX02HGm5H1zmc0NsGJhW7txdnBxtaN2DLoDnFMHeFLMt5xIxEsCZTXUoD35V9n31ntM8-1idXnnQj5ehdlWPXhiaYwadr9rpCO1NvsJsBsAeNVK8K_WtxCF1_K_jQULrywkCKwInlSLHgauOnXk_atZ08yfE_dK7oPJqUWlJDXnFMR75In21F84w-Wndwla1Ly6lM2_iadcrdMamrziWutd-wOks3u8q-3E_oW4r295Of3KOJPhcXqi2JG68KTxXfAseVW-rEJWGl7YEB_DN-GpXw4n0BObX6M5Wv1CMoyCVqMEBxY6lpbTMFjn7iCZ1OAWIMFF2NpJldp249grgifJm9qJt3C7oXEQx-t9y1PfwqjYqUR9W0XqThYObUTwLROMEDZfyQKov1LPRaW3TyYeUY4OpePpBxH-upATyNLn-XXAz9pV7sET8_tey-haCWAUtVf1A410pc5Q8urEBaHfoEOzVuFgP3BPd2x_AW2ZuxN6js2Hp7Dz7JAzy-EdlfP4MfcrCQaO7m0FRyzou3WGurAkpANsy7BuROAZEFx9Gh62hB37XckoNQZipFlZpKxz2KhJksMKsQgiuM2GVsjtoIxkgY6Laoum7NI2EeyB-wKtwmZsaVyfl0AWczFNW3L_MhLcEro8Bq-ApZpTfwZ-Hr0DAJYyaCpWBW80lDBPaAGqRhh-QtEHZTG9iRaU-0ZIiHyHwSIDcSK42pcJ_JwOQS05WCAlT5UkI7Y6ycJRHX4275p09VncAVxzCoEjejZyEH_C_Tf_6Fay2LUAjTvckGDuaVIwtKrOdhVxHRPK1fevf8bl2WxGgHW3ou8ckP4IEbxoLgE4DVZWZ9SqD0rbQWRHGzP1wngL5X0uIkllnjMMP2XaoZXnshBfhFcNq6dboAmoqlLgI2UF30lERuFqQrxS-57V9ES1ewq_DaKjlm37oA_XcREcK0_hyzD27t5Nj6DB_f6L3pBz-B50a02nN7DkGVz9VkcKQOLWUq6fTGHyC_3PdUBa6St81iIBhNSy2HO10Ev77JvxAOKX7QUF3ZPo1SuMegWmEaGV0xIAgUg1NQm08mXVXbYWsz7JJBpk4tIDZMUu04RciNygdTooFSBd7KAxZONfQEuCZhEs8un6ke78H88SkbotQ1eX2xyc86ANApuUayjnnt_AGdCz63hRcbh4W09Yv00sXWSR34BWD1wBKa1X5PYyMkUkVhOQTyfOD13_TSdY9ubjhhnzzYDiBEypS1NN63NJYYlEGoLSmxLGUTm4DgLqKddsnKjtt5t6LAuvpxFQWMKmXIx8168didC_qIDTg0wLvx26MsVptm5bXWYhg7XRqLUE6Bgo7sL-x8CTx-7zAUbIAQ41q4rKM9WlGVVdUSOqHX9kKrabKNfV1SSkwmwxePBJ-1YS4OEiIPzUA0ZzsTKHVSmZTPxuzcpxsK9MdhBDbYJDd_83TVZ6xUIjLvKd2oCPxNhHsXYD4LYfsx384RKb0LQ6WjqzIMiVQj9re00zuEt1dkBLs5Ump0wppxKbjF0qDkS44ohSf0XbqlXTq4G9WWarX6hgza2hU_RYKQLEeKyd9GrgAOJtF_AfKduAau7t-LfCYP6goJ8uLsyYAlj_cSIpES_9dlgvL86F82b0ZvQdidJsoxJsY3kl8kbskd1Fk-7c3YrIpYqlAnTTwdycF2818ID_mlgPwRwQEilnDJ-bLX5p4BxA6yrfQJwRoibDv2-gU1qeTtxf2n8uSRIhrXuS6F7EIZ4TlGylxxqVWFDMZkux6g2x5PpwIYW5WpxzlLbtS30FCVSDQL8ZkqkUzs-oCGMjhft_u48Ss-O3bhHEfYaidVukwN_4gTndhDZabJNEo4qMGbuEWnHckVwT31uQJ_AULoy_0rmyiwOHlkhruIHbv5PFcVH2dHYa5GCLxE6nPQrLZRsoqeBAIGVUddFHhMT-DHDO_ot36I0mNTEJy4WWyhx3uiRNEynOguKd47WNcLIgTIGGgZ7tqV5ni2Il78rA0rK-WeDuQinQob0QtHauAz0Hkr_NJR5gxbzGRrvokJn5xSVFYjhDaffiPyZD-crYMUi3QlD7LbqTmADIjIVzTPQvnGLZlZzCHf8_T8IgMTb6URDnKWZaFwVUbHA0OC1iA_oFruKxOXhV4m732q0choO05vaM7LP9C-2rayvPgJmTkYh2s5wi6g0mBvLbhwcV68I1g2F592j4pHbUmwnnv8UASPKp3B-EHaM6gSSSUuHnY-Dlo7mBQhvZz9fVjtlLsvvXJbrJhulo8MOuFUZcNSOCWh-MFkNv16QBVk1QjXplgKCTS5KYLN-o-a91viPWEgjqpiMbew1mP3XiEChSyTA1QZtXtvTIGDhe-o6oQOyv49_nIUolKw6Bd0tLRY3N0ZCOHZ4QXJcpSMC-rqltNTm69vB3ZsJqBBtpXjEi_OhEMNSBtQn5ESQECXCEbY1gj4nyNhPPd0jbrMgau67GLo"
#             time.sleep(10)
#
#             flow_token = res['flow_token']
#
#             enter_login_data = {
#                 "flow_token": flow_token,
#                 "subtask_inputs": [
#                     {
#                         "subtask_id": "LoginEnterUserIdentifierSSO",
#                         "settings_list": {
#                             "setting_responses": [
#                                 {
#                                     "key": "user_identifier",
#                                     "response_data": {"text_data": {"result": working_acc['screen_name']}},
#                                 }
#                             ],
#                             "link": "next_link",
#                             "castle_token": castle_token
#                         },
#                     }
#                 ],
#             }
#             res = twitter_api_call('enter_login_flow', variables=enter_login_data, features={}, twitter_working_account=working_acc)
#
#             print(res)
#
#             if res in ['ban', 'proxy_dead', 'no_auth', 'lock']:
#                 return res
#
#             elif res['flow_token'] and res['status'] == 'success':
#
#                 time.sleep(5)
#
#                 enter_pw_data = {
#                     "flow_token": res['flow_token'],
#                     "subtask_inputs": [
#                         {
#                             "subtask_id": "LoginEnterPassword",
#                             "enter_password": {
#                                 "password": working_acc['password'],
#                                 "link": "next_link",
#                                 "castle_token": castle_token
#                             },
#                         }
#                     ],
#                 }
#
#                 res = twitter_api_call('enter_pw_flow', variables=enter_pw_data, features={}, twitter_working_account=working_acc)
#
#                 print(res)
#
#                 if res in ['ban', 'proxy_dead', 'no_auth', 'lock']:
#                     return res
#
#                 elif res['flow_token'] and res['status'] == 'success':
#                     cookies = working_acc['session'].get_cookies()
#                     print(cookies)
#                     auth_token = next(c['value'] for c in cookies if c['name'] == 'auth_token')
#                     print(auth_token)
#                     return auth_token
#                 else:
#                     return False


# добавь логи в эту функцию и обработку возможных ошибок

##################################################################################################################################


def get_latest_timeline(working_acc, cursor=""):
    variables = {
        "count": 40,
        "cursor": cursor,
        "includePromotedContent": True,
        "latestControlAvailable": True,
        "withCommunity": True
    }

    features = {
        "rweb_video_screen_enabled": False,
        "payments_enabled": False,
        "profile_label_improvements_pcf_label_in_post_enabled": True,
        "rweb_tipjar_consumption_enabled": True,
        "verified_phone_label_enabled": False,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "premium_content_api_read_enabled": False,
        "communities_web_enable_tweet_community_results_fetch": True,
        "c9s_tweet_anatomy_moderator_badge_enabled": True,
        "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
        "responsive_web_grok_analyze_post_followups_enabled": True,
        "responsive_web_jetfuel_frame": True,
        "responsive_web_grok_share_attachment_enabled": True,
        "articles_preview_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": True,
        "tweet_awards_web_tipping_enabled": False,
        "responsive_web_grok_show_grok_translated_post": True,
        "responsive_web_grok_analysis_button_from_backend": True,
        "creator_subscriptions_quote_tweet_preview_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_grok_image_annotation_enabled": True,
        "responsive_web_grok_imagine_annotation_enabled": True,
        "responsive_web_grok_community_note_auto_translation_is_enabled": False,
        "responsive_web_enhance_cards_enabled": False
    }

    res = twitter_api_call('HomeTimeline', variables, features, twitter_working_account=working_acc)

    if res:
        if res in ['ban', 'proxy_dead', 'no_auth', 'lock']:
            return res
        instructions = res["data"]["home"]["home_timeline_urt"]["instructions"]
        timeline = parse_tweets_instructions(instructions)

        return [x for x in timeline["tweets"]]


#
def get_user_following(twitter_working_account, user_id):
    variables = {
        "userId": str(user_id),
        "includePromotedContent": False
    }

    features = {
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "c9s_tweet_anatomy_moderator_badge_enabled": True,
        "tweetypie_unmention_optimization_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": True,
        "tweet_awards_web_tipping_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "rweb_video_timestamps_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_media_download_video_enabled": False,
        "responsive_web_enhance_cards_enabled": False,
        "creator_subscriptions_quote_tweet_preview_enabled": False,
        "articles_preview_enabled": False,
        "communities_web_enable_tweet_community_results_fetch": False,
        "rweb_tipjar_consumption_enabled": True
    }

    page = 1
    load_next_page = True
    users = []
    while load_next_page:
        # print(f"page = {page}")
        response = twitter_api_call('Following', variables, features, twitter_working_account)

        if response in ['139', 'ban', 'proxy_dead', 'no_auth', 'lock', 'deleted']:
            return response

        js = response.json()

        instructions = js["data"]["user"]["result"]["timeline"]["timeline"]["instructions"]
        users_current_page = parse_users_instructions(instructions)
        users.extend(users_current_page["users"])

        if (load_next_page) and ("bottom" in users_current_page["cursors"]) and (
                len(users_current_page["users"]) >= 20):
            page += 1
            variables["cursor"] = users_current_page["cursors"]["bottom"]
        else:
            load_next_page = False

    return users


def twitter_api_v1_1_call(twitter_working_account, method, url, params={}, payload={}):

    # if not twitter_working_account:
    #     account_number = 0
    #     twitter_working_account = twitter_working_accounts[account_number]

    update_ua = False
    if 'cookies_dict' not in twitter_working_account:
        twitter_working_account['cookies_dict'] = load_cookies_for_twitter_account_from_file(f'x_accs_cookies/{twitter_working_account["screen_name"]}.json')
        update_ua = True


    twitter_cookies_dict = twitter_working_account["cookies_dict"]
    headers = get_headers_for_twitter_account(twitter_cookies_dict)
    # proxies = get_proxies_for_twitter_account(twitter_working_account)

    if update_ua:
        headers['user-agent'] = twitter_working_account['ua']

    attempts = 0
    loaded_successfully = False
    while not loaded_successfully:
        try:
            if method == "post":
                response = twitter_working_account['session'].post(url, params=params, json=payload, headers=headers)
            elif method == "get":
                response = twitter_working_account['session'].get(url, params=params, headers=headers)

            elif method == "upload_file":
                # print(twitter_working_account)
                # twitter_working_account['session'].request_client.request(url, method="POST", files=params)
                response = twitter_working_account['session'].post(url, files=params, headers=headers)

            if (response.status_code == 429) or (response.text.strip("\n") == "Rate limit exceeded"):
                # лимит 180 запросов за 15 минут
                # {'last-modified': 'Wed, 07 Feb 2024 20:03:37 GMT', 'x-rate-limit-reset': 'Wed, 07 Feb 2024 20:18:37 UTC', 'x-rate-limit-limit': '180', 'x-rate-limit-remaining': '179', 'x_response_time': '114', 'status_code': 200}
                print({
                    'url': url,
                    'status_code': response.status_code,
                    'last_modified': response.headers.get('last-modified', ''),
                    'x-rate-limit-reset': datetime.datetime.strftime(
                        datetime.datetime.utcfromtimestamp(int(response.headers.get('x-rate-limit-reset', ''))).replace(
                            tzinfo=pytz.utc), "%a, %d %b %Y %H:%M:%S %Z") if response.headers.get('x-rate-limit-reset',
                                                                                                  '').isdigit() else '',
                    'x-rate-limit-limit': response.headers.get('x-rate-limit-limit', ''),
                    'x-rate-limit-remaining': response.headers.get('x-rate-limit-remaining', ''),
                    'x_response_time': response.headers.get('x-response-time', ''),
                    'content_length': response.headers.get('content-length', '')
                })
                raise RateLimitExceededError("Rate limit exceeded")

            js = response.json()

        except (ConnectTimeout, ReadTimeout, ProxyError, SSLError, ConnectionError, OSError) as e:
            print(e)
            attempts += 1
            if attempts >=3:
                print(f'Error while sending request to X api! Acc name: {twitter_working_account["screen_name"]}')
                time.sleep(1.5)

                if '503 Service Unavailable' in str(e):
                    return 'proxy_dead'

                elif 'Operation timed out' in str(e) or 'Connection timed out' in str(e):
                    return 'timeout'

        except Exception as error:
            print(error)
            attempts += 1
            if isinstance(error, RateLimitExceededError):
                time.sleep(attempts * random.uniform(30, 60))
            else:
                time.sleep(attempts * random.uniform(0, 1))
        else:
            loaded_successfully = True
            return response

def user_friendship(twitter_working_account, action, user_id="", screen_name=""):
    if (user_id == "" and screen_name == "") or ((user_id != "" and screen_name != "")):
        raise ValueError("need to specify user_id OR screen_name")

    if action == "check":
        # https://developer.twitter.com/en/docs/twitter-api/v1/accounts-and-users/follow-search-get-users/api-reference/get-friendships-show
        method = "get"
        url = "https://twitter.com/i/api/1.1/friendships/show.json"
    elif action == "follow":
        # https://developer.twitter.com/en/docs/twitter-api/v1/accounts-and-users/follow-search-get-users/api-reference/post-friendships-create
        method = "post"
        url = "https://twitter.com/i/api/1.1/friendships/create.json"
    elif action == "unfollow":
        # https://developer.twitter.com/en/docs/twitter-api/v1/accounts-and-users/follow-search-get-users/api-reference/post-friendships-destroy
        method = "post"
        url = "https://twitter.com/i/api/1.1/friendships/destroy.json"
    elif action in ["notify", "unnotify"]:
        # https://developer.twitter.com/en/docs/twitter-api/v1/accounts-and-users/follow-search-get-users/api-reference/post-friendships-update
        method = "post"
        url = "https://twitter.com/i/api/1.1/friendships/update.json"
    else:
        raise ValueError("unknown action")

    if action == "check":
        if user_id:
            params = {
                "target_id": user_id,
            }
        elif screen_name:
            params = {
                "target_screen_name": screen_name
            }
    elif action in ["follow", "unfollow", "notify", "unnotify"]:
        params = {
            "include_profile_interstitial_type": 1,
            "include_blocking": 1,
            "include_blocked_by": 1,
            "include_followed_by": 1,
            "include_want_retweets": 1,
            "include_mute_edge": 1,
            "include_can_dm": 1,
            "include_can_media_tag": 1,
            "include_ext_is_blue_verified": 1,
            "include_ext_verified_type": 1,
            "include_ext_profile_image_shape": 1,
            "skip_status": 1,
            "cursor": -1,
        }
        if user_id:
            params["user_id"] = user_id
        elif screen_name:
            params["screen_name"] = screen_name
        if action in ["notify", "unnotify"]:
            params["device"] = (action == "notify")  # True => подписка на уведомления, False => отписка от уведомлений

    response = twitter_api_v1_1_call(twitter_working_account, method, url, params=params)

    if response in ['139', 'ban', 'proxy_dead', 'no_auth', 'lock', 'deleted']:
        return

    try:
        if 'errors' in response.json():
            error_code = response.json()['errors'][0]['code']
            if error_code == 64:
                return 'ban'
            elif error_code == 32:
                return 'no_auth'
        return response.json()
    except AttributeError:
        return None


def change_password(twitter_working_account):
    new_pass = generate_password()

    params = {
        'current_password': twitter_working_account['pass'],
        'password': new_pass,
        'password_confirmation': new_pass
    }

    # response = twitter_api_v1_1_call(twitter_working_account, method, url, params=params)
    res = twitter_api_call('change_pw', twitter_working_account=twitter_working_account, variables=params, features={})

    return res, new_pass


def account_notifications(twitter_working_account, action, settings={}):
    device_info = {
        "os_version": "Windows/Chrome",
        "udid": "Windows/Chrome",
        "checksum": "5f22f2016642335a033a48ede69406ff",
        "env": 3,
        "locale": "en",
        "protocol_version": 1,
        "token": " ",
        "encryption_key1": "",
        "encryption_key2": ""
    }

    if action == "save":
        url = "https://twitter.com/i/api/1.1/notifications/settings/save.json"
        device_info["settings"] = settings
        payload = {
            "push_device_info": device_info
        }
    if action == "check":
        url = "https://twitter.com/i/api/1.1/notifications/settings/checkin.json"
        payload = {
            "push_device_info": device_info
        }
    elif action == "enable":
        url = "https://twitter.com/i/api/1.1/notifications/settings/login.json"
        payload = {
            "push_device_info": device_info
        }
    elif action == "disable":
        url = "https://twitter.com/i/api/1.1/notifications/settings/logout.json"
        payload = device_info
    else:
        raise ValueError("unknown action")

    response = twitter_api_v1_1_call(twitter_working_account, "post", url, payload=payload)

    if response in ['139', 'ban', 'proxy_dead', 'no_auth', 'lock', 'deleted']:
        return

    try:
        if 'errors' in response.json():
            error_code = response.json()['errors'][0]['code']
            if error_code == 64:
                return 'ban'
            elif error_code == 32:
                return 'no_auth'
        return response.json()
    except AttributeError:
        return None


def account_check_notifications_all(twitter_working_account, cursor=""):
    url = "https://twitter.com/i/api/2/notifications/all.json"
    params = {
        "include_profile_interstitial_type": "1",
        "include_blocking": "1",
        "include_blocked_by": "1",
        "include_followed_by": "1",
        "include_want_retweets": "1",
        "include_mute_edge": "1",
        "include_can_dm": "1",
        "include_can_media_tag": "1",
        "include_ext_is_blue_verified": "1",
        "include_ext_verified_type": "1",
        "include_ext_profile_image_shape": "1",
        "skip_status": "1",
        "cards_platform": "Web-12",
        "include_cards": "1",
        "include_ext_alt_text": True,
        "include_ext_limited_action_results": True,
        "include_quote_count": True,
        "include_reply_count": "1",
        "tweet_mode": "extended",
        "include_ext_views": True,
        "include_entities": True,
        "include_user_entities": True,
        "include_ext_media_color": True,
        "include_ext_media_availability": True,
        "include_ext_sensitive_media_warning": True,
        "include_ext_trusted_friends_metadata": True,
        "send_error_codes": True,
        "simple_quoted_tweet": True,
        "count": 40,
        "cursor": "",
        "ext": "mediaStats,highlightedLabel,voiceInfo,birdwatchPivot,superFollowMetadata,unmentionInfo,editControl"
    }
    response = twitter_api_v1_1_call(twitter_working_account, "get", url, params=params)
    js = response.json()

    results = {
        "cursors": {},
        "tweet_notifications": False
    }
    for instruction in js["timeline"]["instructions"]:
        if "addEntries" in instruction:
            for entry in instruction["addEntries"]["entries"]:
                sort_index = entry["sortIndex"]
                if "notification-" in entry["entryId"] and "notification" in entry["content"]["item"]["content"]:
                    notification = entry["content"]["item"]["content"]["notification"]
                    if notification["url"]["urlType"] == "UrtEndpoint" and notification["url"]["urtEndpointOptions"][
                        "cacheId"] == "tweet_notifications":
                        results["tweet_notifications"] = True
                elif ("cursor-top-" in entry["entryId"]) or ("cursor-bottom-" in entry["entryId"]):
                    cursor_type = entry["content"]["operation"]["cursor"]["cursorType"].lower()
                    cursor_value = entry["content"]["operation"]["cursor"]["value"]
                    results["cursors"][cursor_type] = cursor_value

    return results


def account_check_notifications_device_follow(twitter_working_account, cursor=""):
    url = "https://twitter.com/i/api/2/notifications/device_follow.json"
    params = {
        "include_profile_interstitial_type": 1,
        "include_blocking": 1,
        "include_blocked_by": 1,
        "include_followed_by": 1,
        "include_want_retweets": 1,
        "include_mute_edge": 1,
        "include_can_dm": 1,
        "include_can_media_tag": 1,
        "include_ext_is_blue_verified": 1,
        "include_ext_verified_type": 1,
        "include_ext_profile_image_shape": 1,
        "skip_status": 1,
        "cards_platform": "Web-12",
        "include_cards": 1,
        "include_ext_alt_text": True,
        "include_ext_limited_action_results": True,
        "include_quote_count": True,
        "include_reply_count": 1,
        "tweet_mode": "extended",
        "include_ext_views": True,
        "include_entities": True,
        "include_user_entities": True,
        "include_ext_media_color": True,
        "include_ext_media_availability": True,
        "include_ext_sensitive_media_warning": True,
        "include_ext_trusted_friends_metadata": True,
        "send_error_codes": True,
        "simple_quoted_tweet": True,
        "count": 20,
        "cursor": cursor,
        "ext": "mediaStats,highlightedLabel,voiceInfo,birdwatchPivot,superFollowMetadata,unmentionInfo,editControl"
    }
    response = twitter_api_v1_1_call(twitter_working_account, "get", url, params=params)

    if response in ['139', 'ban', 'proxy_dead', 'no_auth', 'lock', 'deleted', 'timeout']:
        return response

    js = response.json()

    # with open("notifications_device_follow_03.json", "r", encoding="utf8") as f:
    #    js = json.load(f)
    with open("notifications_device_follow_03.json", "w", encoding="utf8") as f:
        json.dump(js, f)

    results = {
        "cursors": {},
        "tweets": [],
        "users": js["globalObjects"].get("users")
    }
    for instruction in js["timeline"]["instructions"]:
        if "addEntries" in instruction:
            for entry in instruction["addEntries"]["entries"]:
                sort_index = entry["sortIndex"]
                if "tweet-" in entry["entryId"]:
                    tweet_id = entry["content"]["item"]["content"]["tweet"]["id"]
                    tweet = js["globalObjects"]["tweets"][tweet_id]
                    results["tweets"].append(tweet)
                elif ("cursor-top-" in entry["entryId"]) or ("cursor-bottom-" in entry["entryId"]):
                    cursor_type = entry["content"]["operation"]["cursor"]["cursorType"].lower()
                    cursor_value = entry["content"]["operation"]["cursor"]["value"]
                    results["cursors"][cursor_type] = cursor_value

    return results

##################################################################################################################################


def get_info_about_tweet(twitter_working_account, tweet_id):
    # user_screen_name = "Dyna_anji"
    variables = {
        "focalTweetId": tweet_id,
        "with_rux_injections": False,
        "rankingMode": "Relevance",
        "includePromotedContent": True,
        "withCommunity": True,
        "withQuickPromoteEligibilityTweetFields": True,
        "withBirdwatchNotes": True,
        "withVoice": True
    }

    features = {
        "rweb_video_screen_enabled": False,
        "payments_enabled": False,
        "rweb_xchat_enabled": False,
        "profile_label_improvements_pcf_label_in_post_enabled": True,
        "rweb_tipjar_consumption_enabled": True,
        "verified_phone_label_enabled": False,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "premium_content_api_read_enabled": False,
        "communities_web_enable_tweet_community_results_fetch": True,
        "c9s_tweet_anatomy_moderator_badge_enabled": True,
        "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
        "responsive_web_grok_analyze_post_followups_enabled": True,
        "responsive_web_jetfuel_frame": True,
        "responsive_web_grok_share_attachment_enabled": True,
        "articles_preview_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": True,
        "tweet_awards_web_tipping_enabled": False,
        "responsive_web_grok_show_grok_translated_post": True,
        "responsive_web_grok_analysis_button_from_backend": True,
        "creator_subscriptions_quote_tweet_preview_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_grok_image_annotation_enabled": True,
        "responsive_web_grok_imagine_annotation_enabled": True,
        "responsive_web_grok_community_note_auto_translation_is_enabled": False,
        "responsive_web_enhance_cards_enabled": False
    }
    fieldToggles = {"withArticleRichContentState":True,"withArticlePlainText":False,"withGrokAnalyze":False,"withDisallowedReplyControls":False}
    try:
        response = twitter_api_call('TweetDetail', variables, features, twitter_working_account, toggles=fieldToggles)
        print(response)
        # js = response.json()
        # user_raw = response["data"]["user"]["result"]
        # user_parsed = parse_user(user_raw)
    except KeyError:
        print("ошибка при получении твита: ", tweet_id)


def get_info_about_tweet_anon(twitter_working_account, tweet_id):
    variables = {
        "tweetId": tweet_id,
        "includePromotedContent": True,
        "withCommunity": True,
        "withVoice": True,
        "withBirdwatchNotes": True
    }

    features = {
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "premium_content_api_read_enabled": False,
        "communities_web_enable_tweet_community_results_fetch": True,
        "c9s_tweet_anatomy_moderator_badge_enabled": True,
        "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
        "responsive_web_grok_analyze_post_followups_enabled": True,
        "responsive_web_jetfuel_frame": True,
        "responsive_web_grok_share_attachment_enabled": True,
        "articles_preview_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": True,
        "tweet_awards_web_tipping_enabled": False,
        "responsive_web_grok_show_grok_translated_post": True,
        "responsive_web_grok_analysis_button_from_backend": True,
        "creator_subscriptions_quote_tweet_preview_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "payments_enabled": False,
        "rweb_xchat_enabled": True,
        "profile_label_improvements_pcf_label_in_post_enabled": True,
        "rweb_tipjar_consumption_enabled": True,
        "verified_phone_label_enabled": False,
        "responsive_web_grok_image_annotation_enabled": True,
        "responsive_web_grok_imagine_annotation_enabled": True,
        "responsive_web_grok_community_note_auto_translation_is_enabled": False,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_enhance_cards_enabled": False
    }
    fieldToggles = {"withArticleRichContentState": True, "withArticlePlainText": True}
    try:
        response = twitter_api_call('TweetResultByRestId', variables, features, twitter_working_account, toggles=fieldToggles)
        print(response)
        # js = response.json()
        # user_raw = js["data"]["user"]["result"]
        # user_parsed = parse_user(user_raw)
    except KeyError:
        print("ошибка при получении твита: ", tweet_id)


def save_accounts_and_proxies_statistics(twitter_working_accounts):
    statistics = {
        'total_requests': requests_count.value,
        'accounts': [{
            'screen_name': twitter_working_account['screen_name'],
            'requests': twitter_working_account['requests'].value,
            'requests_successful': twitter_working_account['requests_successful'].value,
            'requests_errors': twitter_working_account['requests_errors'].value
        } for twitter_working_account in twitter_working_accounts]
    }
    with open("search_statistics.json", "w") as f:
        json.dump(statistics, f, indent=2)


# if __name__ == "__main__":
#     prox = 'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-ba0ce33d7cdc1-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080'
#     proxies = {
#         "http": f"http://{prox}",
#         "https": f"http://{prox}"
#     }
#     tw_cl = initialize_client()
#     t_w_a = {
#         'screen_name': 'SunitaY78668883',
#         'password': 'Ry4Xdnz570',
#         'session': tw_cl,
#         'ua': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36'
#     }
#     flow_login(t_w_a)