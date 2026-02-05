import requests, datetime, time, sys, random, json, pytz, alarm_bot, re
import twitter_search
import concurrent.futures
from threading import Event, Thread
from multiprocessing.managers import BaseManager, SyncManager
from database import Database

##################################################################################################################################
        
def save_last_tweet():
    with open("last_tweet.txt", "w", encoding="utf8") as f:
        json.dump(last_tweet.copy(), f)
        
def save_last_profile():
    with open("last_profile.txt", "w", encoding="utf8") as f:
        json.dump(last_profile.copy(), f)
                
##################################################################################################################################

def check_user_recent_tweets(users_ids):
    global last_tweet

    cursors = {}
    requests_datetimes = []
    started_at = datetime.datetime.now(datetime.timezone.utc)
    print(f"[{started_at}] === started monitoring via recent tweets requests ===")
    
    while not stopped.wait(interval_tweets1):
        # getting users_recent_tweets
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            users_recent_tweets = {user_id: user_recent_tweets for users_recent_tweets in executor.map(lambda args: twitter_search.get_user_recent_tweets(*args), ((user_id, 1, cursors[user_id] if user_id in cursors else "") for user_id in users_ids)) for user_id, user_recent_tweets in users_recent_tweets.items()}
        #with open("a.json", "w", encoding="utf8") as f:
        #    json.dump(users_recent_tweets, f)
        #with open("b.json", "w", encoding="utf8") as f:
        #    json.dump(cursors, f)

        request_datetime = datetime.datetime.now()
        requests_datetimes.append(request_datetime)
        for user_id, user_recent_tweets in users_recent_tweets.items():
            if len(user_recent_tweets) > 0:
                cursors[user_id] = user_recent_tweets[0].get("cursor_top", "")

                user_recent_tweets = sorted(user_recent_tweets, key=lambda x: x["tweet"]["id"], reverse=True)
                screen_name = user_recent_tweets[0]["user"]["screen_name"]
                last_tweet_from_api = user_recent_tweets[0]["tweet"]
                # is_reply = last_tweet_from_api['full_text'].startswith('@')

                if (screen_name not in last_tweet) or (last_tweet[screen_name]["id"] < last_tweet_from_api["id"]):
                    # найден новый твит
                    discovered_at = datetime.datetime.now(datetime.timezone.utc)
                    created_at = datetime.datetime.strptime(last_tweet_from_api["created_at"], "%a %b %d %H:%M:%S %z %Y") # 'Wed May 25 10:48:02 +0000 2022'
                    
                    with lock:
                        last_tweet[screen_name] = {
                            "discovered_by": "user_recent_tweets",
                            "discovered_at": discovered_at.isoformat(),
                            "created_at": created_at.isoformat(),
                            "id": last_tweet_from_api['id'],
                            "text": last_tweet_from_api['full_text']
                        }

                        if created_at > started_at:
                            # выводим и сохраняем информацию об обнаруженном твите
                            # только если он был опубликован после запуска скрипта

                            alarm_bot.new_tweet_signal(f'Новый твит от {screen_name}\nДата создания: {created_at}\nВремя распознавания: {discovered_at}\nТекст: {last_tweet_from_api["full_text"]}')

                            if screen_name.lower() in infl_list:
                                for word in last_tweet[screen_name]["text"]:
                                    for token_name, ca in token_and_key_words.items():
                                        if word == token_name:
                                            # result_ok, result_text = send_command_banana(command="buy_order",
                                            #                                              token_address=ca,
                                            #                                              token_value=0.2)
                                            alarm_bot.admin_signal_th(
                                                f'{screen_name} JUST TWEETED ABOUT {token_name} !!!')
                                            break

                            delta_between_requests_ms = (requests_datetimes[-1] - requests_datetimes[-2]) / datetime.timedelta(milliseconds=1) if len(requests_datetimes) > 1 else '?'
                            delay_discover_ms = round((discovered_at - created_at).total_seconds() * 1000)
                            print(f"[{discovered_at}] delta_between_requests_ms={delta_between_requests_ms}, delay_discover_ms={delay_discover_ms} screen_name={screen_name}, tweet={last_tweet[screen_name]}")

                            # сохраняем последние твиты всех отслеживаемых пользователей
                            save_last_tweet()

        #
        if display_log:
            delta_between_requests_ms = (requests_datetimes[-1] - requests_datetimes[-2]) / datetime.timedelta(milliseconds=1) if len(requests_datetimes) > 1 else '?'
            avg_requests_per_second = round(10/(requests_datetimes[-1] - requests_datetimes[-11]).total_seconds(), 3) if len(requests_datetimes) > 10 else '?'
            if len(requests_datetimes) > 10:
                requests_datetimes.pop(0)            
            print(f"[{request_datetime}] [твиты через последние твиты] account={twitter_working_account['screen_name']}, delta_between_requests={delta_between_requests_ms} ms, avg_requests_per_second={avg_requests_per_second}")

        # сохранение статистики работы аккаунтов и прокси
        twitter_search.save_accounts_and_proxies_statistics()
    
##################################################################################################################################

def check_notifications_loop(scraper_accounts, screen_names, use_first_n_accounts):
    global last_tweet

    cursors = {}
    requests_count = 0
    requests_datetimes = []
    screen_names_lower = [screen_name.lower() for screen_name in screen_names]
    started_at = datetime.datetime.now(datetime.timezone.utc)
    print(f"[{started_at}] === started monitoring net tweets via push notifications requests ===")
    
    while not stopped.wait(interval_tweets2):
        requests_count += 1
        request_datetime = datetime.datetime.now()
        requests_datetimes.append(request_datetime)
        twitter_working_account = scraper_accounts[(requests_count-1) % min(len(scraper_accounts), use_first_n_accounts)]
        
        # getting notifications for recent tweets
        # print(f"[{request_datetime}] account={twitter_working_account['screen_name']}, cursor={cursor}")
        results = twitter_search.account_check_notifications_device_follow(twitter_working_account, cursor=cursors.get(twitter_working_account["screen_name"], ""))
                
        if len(results["tweets"]) > 0:
            cursors[twitter_working_account["screen_name"]] = results["cursors"].get("top", "")
            tweets_users_ids_str = [tweet["user_id_str"] for tweet in results["tweets"]]
            tweets_by_user = {user_id_str: [tweet for tweet in results["tweets"] if tweet["user_id_str"] == user_id_str] for user_id_str in tweets_users_ids_str}
                
            for user_ids_str in tweets_users_ids_str:
                user_recent_tweets = sorted(tweets_by_user[user_ids_str], key=lambda x: x["id"], reverse=False) # sort from oldest first to newest
                for user_recent_tweet in user_recent_tweets:
                    screen_name = results["users"][user_recent_tweet["user_id_str"]]["screen_name"]

                    if (screen_name.lower() in screen_names_lower) and ((screen_name not in last_tweet) or (last_tweet[screen_name]["id"] < user_recent_tweet["id"])):
                        # найден новый твит
                        is_it_first_discovered_tweet = screen_name not in last_tweet
                        discovered_at = datetime.datetime.now(datetime.timezone.utc)
                        created_at = datetime.datetime.strptime(user_recent_tweet["created_at"], "%a %b %d %H:%M:%S %z %Y") # 'Wed May 25 10:48:02 +0000 2022'
                        
                        with lock:
                            last_tweet[screen_name] = {
                                "discovered_by": "notifications",
                                "discovered_at": discovered_at.isoformat(),
                                "created_at": created_at.isoformat(),
                                "id": user_recent_tweet['id'],
                                "text": user_recent_tweet['full_text']
                            }

                            if created_at > started_at:
                                # выводим и сохраняем информацию об обнаруженном твите
                                # только если он был опубликован после запуска скрипта

                                print(f'Detected New Tweet!')
                                print(f'{screen_name}: {last_tweet[screen_name]["text"]}\n\nДата создания: {created_at}\nВремя распознавания: {discovered_at}')
                                # Thread(target=alarm_bot.new_tweet_signal, args=(f'{screen_name}: {last_tweet[screen_name]["text"]}\n\nДата создания: {created_at}\nВремя распознавания: {discovered_at}',)).start()

                                delta_between_requests_ms = (requests_datetimes[-1] - requests_datetimes[-2]) / datetime.timedelta(milliseconds=1) if len(requests_datetimes) > 1 else '?'
                                delay_discover_ms = round((discovered_at - created_at).total_seconds() * 1000)
                                print(f"[{discovered_at}] delta_between_requests_ms={delta_between_requests_ms}, delay_discover_ms={delay_discover_ms} screen_name={screen_name}, tweet={last_tweet[screen_name]}")

                                # сохраняем последние твиты всех отслеживаемых пользователей
                                save_last_tweet()

        #
        if display_log:
            delta_between_requests_ms = (requests_datetimes[-1] - requests_datetimes[-2]) / datetime.timedelta(milliseconds=1) if len(requests_datetimes) > 1 else '?'
            avg_requests_per_second = round(10/(requests_datetimes[-1] - requests_datetimes[-11]).total_seconds(), 3) if len(requests_datetimes) > 10 else '?'
            if len(requests_datetimes) > 10:
                requests_datetimes.pop(0)
            print(f"[{request_datetime}] [твиты через уведомления] account={twitter_working_account['screen_name']}, delta_between_requests={delta_between_requests_ms} ms, avg_requests_per_second={avg_requests_per_second}")

        # сохранение статистики работы аккаунтов и прокси
        twitter_search.save_accounts_and_proxies_statistics(scraper_accounts)
    
##################################################################################################################################
    
def check_timeline_loop(screen_names, use_first_n_accounts):
    global last_tweet

    cursors = {}
    requests_count = 0
    requests_datetimes = []
    screen_names_lower = [screen_name.lower() for screen_name in screen_names]
    started_at = datetime.datetime.now(datetime.timezone.utc)
    print(f"[{started_at}] === started monitoring net tweets via latest home timeline requests ===")
    
    while not stopped.wait(interval_tweets2):
        requests_count += 1
        request_datetime = datetime.datetime.now()
        requests_datetimes.append(request_datetime)
        twitter_working_account = twitter_search.twitter_working_accounts[(requests_count-1) % min(len(twitter_search.twitter_working_accounts), use_first_n_accounts)]
        
        # getting latest home timeline
        # print(f"[{request_datetime}] account={twitter_working_account['screen_name']}, cursor={cursor}")
        results = twitter_search.get_latest_timeline(twitter_working_account, cursor=cursors.get(twitter_working_account["screen_name"], ""))
        cursors[twitter_working_account["screen_name"]] = results["cursors"].get("top", "")
                
        if len(results["tweets"]) > 0:
            tweets_users_ids_str = [str(tweet["user"]["id"]) for tweet in results["tweets"]]
            tweets_by_user = {user_id_str: [{**tweet["tweet"], "screen_name": tweet["user"]["screen_name"]} for tweet in results["tweets"] if str(tweet["tweet"]["user_id"]) == user_id_str] for user_id_str in tweets_users_ids_str}
            
            for user_ids_str in tweets_users_ids_str:
                user_recent_tweets = sorted(tweets_by_user[user_ids_str], key=lambda x: x["id"], reverse=False) # sort from oldest first to newest
                for user_recent_tweet in user_recent_tweets:
                    screen_name = user_recent_tweet["screen_name"]

                    if (screen_name.lower() in screen_names_lower) and ((screen_name not in last_tweet) or (last_tweet[screen_name]["id"] < user_recent_tweet["id"])):
                        # найден новый твит
                        is_it_first_discovered_tweet = screen_name not in last_tweet
                        discovered_at = datetime.datetime.now(datetime.timezone.utc)
                        created_at = datetime.datetime.strptime(user_recent_tweet["created_at"], "%a %b %d %H:%M:%S %z %Y") # 'Wed May 25 10:48:02 +0000 2022'
                        
                        with lock:
                            last_tweet[screen_name] = {
                                "discovered_by": "timeline",
                                "discovered_at": discovered_at.isoformat(),
                                "created_at": created_at.isoformat(),
                                "id": user_recent_tweet['id'],
                                "text": user_recent_tweet['full_text']
                            }

                            if created_at > started_at:
                                # выводим и сохраняем информацию об обнаруженном твите
                                # только если он был опубликован после запуска скрипта
                                delta_between_requests_ms = (requests_datetimes[-1] - requests_datetimes[-2]) / datetime.timedelta(milliseconds=1) if len(requests_datetimes) > 1 else '?'
                                delay_discover_ms = round((discovered_at - created_at).total_seconds() * 1000)
                                print(f"[{discovered_at}] delta_between_requests_ms={delta_between_requests_ms}, delay_discover_ms={delay_discover_ms} screen_name={screen_name}, tweet={last_tweet[screen_name]}")

                                # сохраняем последние твиты всех отслеживаемых пользователей
                                save_last_tweet()

        #
        if display_log:
            delta_between_requests_ms = (requests_datetimes[-1] - requests_datetimes[-2]) / datetime.timedelta(milliseconds=1) if len(requests_datetimes) > 1 else '?'
            avg_requests_per_second = round(10/(requests_datetimes[-1] - requests_datetimes[-11]).total_seconds(), 3) if len(requests_datetimes) > 10 else '?'
            if len(requests_datetimes) > 10:
                requests_datetimes.pop(0)
            print(f"[{request_datetime}] [твиты через ленту] account={twitter_working_account['screen_name']}, delta_between_requests={delta_between_requests_ms} ms, avg_requests_per_second={avg_requests_per_second}")

        # сохранение статистики работы аккаунтов и прокси
        twitter_search.save_accounts_and_proxies_statistics()
    
def check_profiles_loop(screen_names, use_first_n_accounts):
    global last_profile

    requests_count = 0
    requests_datetimes = []
    screen_names_lower = [screen_name.lower() for screen_name in screen_names]
    started_at = datetime.datetime.now(datetime.timezone.utc)
    print(f"[{started_at}] === started monitoring changing in friends (following) users profiles ===")
    
    while not stopped.wait(interval_profiles):
        requests_count += 1
        request_datetime = datetime.datetime.now()
        requests_datetimes.append(request_datetime)
        twitter_working_account = twitter_search.twitter_working_accounts[(requests_count-1) % min(len(twitter_search.twitter_working_accounts), use_first_n_accounts)]
        
        # getting following users profiles
        # print(f"[{request_datetime}] account={twitter_working_account['screen_name']}")
        user_following_users = twitter_search.get_user_following(twitter_working_account, twitter_working_account["user_id"])

        # отслеживаемые поля
        fields = ["name", "location", "profile_banner_url", "profile_image_url_https", "description"]
        
        for following_user in user_following_users:
            if following_user["screen_name"].lower() in screen_names_lower:
                profile_just_discovered = following_user["screen_name"] not in last_profile
                
                with lock:
                    if profile_just_discovered:
                        last_profile[following_user["screen_name"]] = {
                            **{field: following_user[field] for field in fields},
                            "discovered_initially_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        }
                    else:
                        updated_fields = []
                        for field in fields:
                            if following_user[field] != last_profile[following_user["screen_name"]][field]:
                                print(f"[{datetime.datetime.now()}] у отслеживаемого пользователя {following_user['screen_name']} обнаружено изменение поля {field}, было '{last_profile[following_user['screen_name']][field]}', стало '{following_user[field]}'")

                                alarm_bot.admin_signal_th(f'{following_user["screen_name"]} CHANGED {field} ! NEW: {following_user[field]} !')

                                # if 'url' not in field and following_user['screen_name'].lower() in infl_list:
                                #     for token_name, ca in token_and_key_words.items():
                                        # if token_name in following_user[field]:
                                            # result_ok, result_text = send_command_banana(command="buy_order",
                                            #                                              token_address=ca,
                                            #                                              token_value=0.2)

                                last_profile[following_user["screen_name"]][field] = following_user[field]
                                last_profile[following_user["screen_name"]]["discovered_update_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                                updated_fields.append(field)
                                
                        profile_just_updated = len(updated_fields) > 0
                        
                        if profile_just_updated:
                            last_profile[following_user["screen_name"]]["updated_fields"] = updated_fields
                           
                    if profile_just_discovered or profile_just_updated:
                        # если профиля ещё нет в файле или в нём обнаружены изменения, то сохранение профилей в файл
                        save_last_profile()

        #
        if display_log:
            delta_between_requests_ms = (requests_datetimes[-1] - requests_datetimes[-2]) / datetime.timedelta(milliseconds=1) if len(requests_datetimes) > 1 else '?'
            avg_requests_per_second = round(10/(requests_datetimes[-1] - requests_datetimes[-11]).total_seconds(), 3) if len(requests_datetimes) > 10 else '?'
            if len(requests_datetimes) > 10:
                requests_datetimes.pop(0)
            print(f"[{request_datetime}] [профили] account={twitter_working_account['screen_name']}, delta_between_requests={delta_between_requests_ms} ms, avg_requests_per_second={avg_requests_per_second}")

        # сохранение статистики работы аккаунтов и прокси
        twitter_search.save_accounts_and_proxies_statistics()

##################################################################################################################################


if __name__ == '__main__':
    # === (1) список страничек для отслеживания последнего твита ===
    # нужно ли отслеживать новые твиты
    check_tweets = True
    
    # аккаунты для отслеживания методом 1 (через последние твиты) (аккаунты с большим количеством подписчиков)
    screen_names1 = []
    
    # аккаунты для отслеживания методом 2 (через уведомления (notifications)) (аккаунты с небольшим количеством подписчиков)
    # (можно добавить сюда и аккаунты с большим количеством подписчиков, тогда они будут отслеживаться двумя методами одновременно)
    screen_names2 = ['Rainmaker1973']
    
    # аккаунты для отслеживания методом 3 (через новостную ленту (timeline)) (аккаунты с небольшим количеством подписчиков)
    # (можно добавить сюда и все другие аккаунты, тогда они также будут отслеживаться одновременно разными методами)
    screen_names3 = []
    
    # === (2) список страничек для отслеживания изменений в профиле ===
    # нужно ли отслеживать изменения в профилях
    check_profiles = False
    
    # аккаунты для отслеживания изменений в профилях
    infl_list = []
    screen_names4 = infl_list
    
    # === (3) настройки для метода 1 (через последние твиты пользователей) === 
    # периодичность проверок новых твитов в секундах
    interval_tweets1 = 2.75
    
    # лимиты для отслеживания через последние твиты (method = 1), на каждого из отслеживаемых пользователей тратится по одному запросу:
    # * при использовании одного рабочего аккаунта лимит 95 запросов за 15 минут (1 запрос не чаще чем каждые 9.5 секунд)
    # * при использовании двух рабочих аккаунтов лимит 180 запросов за 15 минут (1 запрос не чаще чем каждые 4.75 секунды)
    # * при использовании пяти рабочих аккаунтов лимит 475 запросов за 15 минут (1 запрос не чаще чем каждые 1.9 секунды)
    # * при использовании десяти рабочих аккаунтов лимит 950 запросов за 15 минут (1 запрос не чаще чем каждые 0.95 секунды)
    
    # === (4) настройки для методов 2 и 3 (через уведомления и новостную ленту) ===
    # нужно ли отписываться от каналов, которые не указаны в списке отслеживаемых screen_names2 или screen_names3
    unsubscribe_from_other_accounts = False
    
    # количество используемых рабочих аккаунтов из списка twitter_working_accounts2 
    use_first_n_accounts2 = 10000

    # периодичность проверок новых твитов в секундах
    interval_tweets2 = 5
    
    # лимиты для отслеживания через notifications (method = 2), сразу на всех отслеживаемых пользователей тратится только один запрос:
    # * при использовании одного рабочего аккаунта лимит 180 запросов за 15 минут (1 запрос не чаще чем каждые 5 секунд)
    # * при использовании двух рабочих аккаунтов лимит 360 запросов за 15 минут (1 запрос не чаще чем каждые 2.5 секунды)
    # * при использовании пяти рабочих аккаунтов лимит 900 запросов за 15 минут (1 запрос не чаще чем каждую 1 секунду)
    
    # лимиты для отслеживания через timeline (method = 3), сразу на всех отслеживаемых пользователей тратится только один запрос:
    # * при использовании одного рабочего аккаунта лимит 500 запросов за 15 минут (1 запрос не чаще чем каждые 1.80 секунд)
    # * при использовании двух рабочих аккаунтов лимит 1000 запросов за 15 минут (1 запрос не чаще чем каждые 0.90 секунд)
    # * при использовании пяти рабочих аккаунтов лимит 2500 запросов за 15 минут (1 запрос не чаще чем каждую 0.36 секунд)
    
    # === (5) настройки для отслеживания профилей ===
    # периодичность проверок профилей в секундах
    interval_profiles = 30.25
    
    # === (6) прочие настройки ===
    # выводить ли на экран лог о запросах без новых твитов
    display_log = True
    
    ##################################################################################################################################
    
    # загрузка аккаунтов из БД
    db = Database()

    scraper_accs = db.get_scraper_accounts()
    scraper_accs = twitter_search.load_accounts_cookies_login(scraper_accs)
        
    if check_tweets and len(screen_names1) > 0:
        # способ #1 [декабрь 2023]
        print(f"{datetime.datetime.now()} Usernames для отслеживания новых твитов через последние твиты: {screen_names1}")

        # getting users_ids
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
           users_ids1 = [user_id for user_id in executor.map(twitter_search.get_user_id_by_user_screen_name, screen_names1)]
        
        # постоянная проверка последних твитов отслеживаемых пользователей через разные аккаунты
        thread1 = Thread(target=check_user_recent_tweets, args=(users_ids1,))
        
    if (check_tweets or check_profiles) and len(list(set(screen_names2 + screen_names3 + screen_names4))) > 0:
        # способ #2 [февраль 2024]        
        # for twitter_working_account in scraper_accs[:use_first_n_accounts2]:
        #     twitter_working_account["user_id"] = twitter_search.get_user_id_by_user_screen_name(twitter_working_account["screen_name"], twitter_working_account)

        if check_tweets and len(list(set(screen_names2 + screen_names3))) > 0:            
            for twitter_working_account in scraper_accs[:use_first_n_accounts2]:
                # (1) проверка, включены ли уведомления о новых твитах в данном аккаунте
                print(f"[{datetime.datetime.now()}] === Аккаунт {twitter_working_account['screen_name']} ===")
                js = twitter_search.account_notifications(twitter_working_account, "check")
                if js == 'ban':
                    print(f"[SCRAPER] Аккаунт {twitter_working_account['screen_name']} вероятно забанен!")
                    try:
                        db.update_is_banned(twitter_working_account["uid"])
                    except Exception as e:
                        print(f"[SCRAPER] Ошибка при update_is_banned: {e}")
                    continue
                elif js == 'no_auth':
                    print(
                        f"[SCRAPER] Аккаунт {twitter_working_account['screen_name']} вероятно нуждается в обновлении сессии!")
                    try:
                        db.update_regen_session(twitter_working_account["uid"], True)
                    except Exception as e:
                        print(f"[SCRAPER] Ошибка при update_regen_session: {e}")
                    continue
                print(f"[{datetime.datetime.now()}] Уведомления о новых твитах для аккаунта {twitter_working_account['screen_name']}: TweetsSetting={js['push_settings']['TweetsSetting']}")
                if js["push_settings"]["TweetsSetting"] == "off":
                    # если они не включены, то включение уведомлений о новых твитах для аккаунта
                    js = twitter_search.account_notifications(twitter_working_account, "set", settings={"TweetsSetting": "on"})
                    print(f"[{datetime.datetime.now()}] Уведомления о новых твитах для аккаунта {twitter_working_account['screen_name']}: TweetsSetting={js['push_settings']['TweetsSetting']}")
                
                # (2) проверка, подписан ли данный аккаунт на все аккаунты, в которых нужно отслеживать новые твиты
                user_following_users = twitter_search.get_user_following(twitter_working_account, twitter_working_account["uid"])
                following_notifications = {user['screen_name'].lower(): user['notifications'] for user in user_following_users}
                
                # рандомизируем подписки на пользователей
                screen_names = list(set(screen_names2 + screen_names3))
                random.shuffle(screen_names)
                for screen_name in screen_names:
                    if screen_name.lower() not in following_notifications:
                        print(f"[{datetime.datetime.now()}] У аккаунта {twitter_working_account['screen_name']} нет подписки на пользователя {screen_name}")
                        js = twitter_search.user_friendship(twitter_working_account, "follow", screen_name=screen_name)
                        if js == 'ban':
                            print(f"[SCRAPER] Аккаунт {twitter_working_account['screen_name']} вероятно забанен!")
                            try:
                                db.update_is_banned(twitter_working_account["uid"])
                            except Exception as e:
                                print(f"[SCRAPER] Ошибка при update_is_banned: {e}")
                            continue
                        elif js == 'no_auth':
                            print(f"[SCRAPER] Аккаунт {twitter_working_account['screen_name']} вероятно нуждается в обновлении сессии!")
                            try:
                                db.update_regen_session(twitter_working_account["uid"], True)
                            except Exception as e:
                                print(f"[SCRAPER] Ошибка при update_regen_session: {e}")
                            continue
                        js = twitter_search.user_friendship(twitter_working_account, "notify", screen_name=screen_name)
                        if js == 'ban':
                            print(f"[SCRAPER] Аккаунт {twitter_working_account['screen_name']} вероятно забанен!")
                            try:
                                db.update_is_banned(twitter_working_account["uid"])
                            except Exception as e:
                                print(f"[SCRAPER] Ошибка при update_is_banned: {e}")
                            continue
                        elif js == 'no_auth':
                            print(f"[SCRAPER] Аккаунт {twitter_working_account['screen_name']} вероятно нуждается в обновлении сессии!")
                            try:
                                db.update_regen_session(twitter_working_account["uid"], True)
                            except Exception as e:
                                print(f"[SCRAPER] Ошибка при update_regen_session: {e}")
                            continue
                        time.sleep(random.uniform(10, 20))
                    elif not following_notifications[screen_name.lower()]:
                        print(f"[{datetime.datetime.now()}] У аккаунта {twitter_working_account['screen_name']} есть подписка на пользователя {screen_name}, но нет подписки на уведомления об его/её новых твитах")
                        js = twitter_search.user_friendship(twitter_working_account, "notify", screen_name=screen_name)
                        if js == 'ban':
                            print(f"[SCRAPER] Аккаунт {twitter_working_account['screen_name']} вероятно забанен!")
                            try:
                                db.update_is_banned(twitter_working_account["uid"])
                            except Exception as e:
                                print(f"[SCRAPER] Ошибка при update_is_banned: {e}")
                            continue
                        elif js == 'no_auth':
                            print(f"[SCRAPER] Аккаунт {twitter_working_account['screen_name']} вероятно нуждается в обновлении сессии!")
                            try:
                                db.update_regen_session(twitter_working_account["uid"], True)
                            except Exception as e:
                                print(f"[SCRAPER] Ошибка при update_regen_session: {e}")
                            continue
                        time.sleep(random.uniform(10, 20))
                    else:
                        print(f"[{datetime.datetime.now()}] У аккаунта {twitter_working_account['screen_name']} есть подписка на пользователя {screen_name}, есть подписка на уведомления об его/её новых твитах")
                        
                    if screen_name.lower() not in following_notifications or not following_notifications[screen_name.lower()]:
                        js = twitter_search.user_friendship(twitter_working_account, "check", screen_name=screen_name)
                        following = js["relationship"]["source"]["following"]
                        notifications_enabled = js["relationship"]["source"]["notifications_enabled"]
                        print(f"[{datetime.datetime.now()}] Результат подписки аккаунта {twitter_working_account['screen_name']} на пользователя {screen_name}: following={following}, notifications_enabled={notifications_enabled}") 
                
                # (3) (при необходимости) отписка от ненужных аккаунтов, которых нет в списке screen_names
                if unsubscribe_from_other_accounts:
                    screen_names_lower = [screen_name.lower() for screen_name in screen_names]
                    for following_screen_name in following_notifications:
                        if following_screen_name.lower() not in screen_names_lower:                
                            print(f"[{datetime.datetime.now()}] У аккаунта {twitter_working_account['screen_name']} есть подписка на пользователя {following_screen_name}, но этот пользователь не нужен для отслеживания новых твитов, сейчас произойдёт отписка от него/неё")
                            js = twitter_search.user_friendship(twitter_working_account, "unfollow", screen_name=following_screen_name)
                            time.sleep(random.uniform(10, 20))
                             
            if len(screen_names2) > 0:
                # постоянная проверка уведомлений о новых твитах через разные аккаунты
                print(f"{datetime.datetime.now()} Usernames для отслеживания новых твитов через уведомления (notifications): {screen_names2}")
                thread2 = Thread(target=check_notifications_loop, args=(scraper_accs,screen_names2,use_first_n_accounts2,))
                
            if len(screen_names3) > 0:
                # постоянная проверка ленты с новыми твитами через разные аккаунты
                print(f"{datetime.datetime.now()} Usernames для отслеживания новых твитов через новостную ленту (timeline): {screen_names3}")
                thread3 = Thread(target=check_timeline_loop, args=(screen_names3,use_first_n_accounts2,))
            
        if check_profiles and len(screen_names4) > 0:
            # постоянная проверка изменений в профилях отслеживаемых пользователей
            print(f"{datetime.datetime.now()} Usernames для отслеживания изменений в профиле: {screen_names4}")            
            thread4 = Thread(target=check_profiles_loop, args=(screen_names4,use_first_n_accounts2,))
          
    if (check_tweets or check_profiles) and len(list(set(screen_names1 + screen_names2 + screen_names3 + screen_names4))) > 0:
        mp = SyncManager()
        mp.start()
        lock = mp.Lock()
        last_tweet = mp.dict()
        last_profile = mp.dict()
        
        # инициализируем json-файл для хранения последних твитов нескольких пользователей
        save_last_tweet()
            
        # инициализируем json-файл для хранения профилей нескольких пользователей
        # save_last_profile()
    
        stopped = Event()
        
        for i in range(1, 5):
            if f"thread{i}" in globals():
                print(f"{datetime.datetime.now()} starting thread{i}")
                globals()[f"thread{i}"].start()

        for i in range(1, 5):
            if f"thread{i}" in globals():
                globals()[f"thread{i}"].join()