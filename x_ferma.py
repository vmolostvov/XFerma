import time, json, random, os, emoji, math, logging
import traceback
import zoneinfo
import twitter_search
# from twitter_search import load_accounts_cookies_login
from typing import Tuple, List
from x_media_uploader import upload_and_update_pfp
from tweeterpyapi import load_accounts_tweeterpy, get_user_data, initialize_client
from config import nodemaven_proxy_rotating, get_random_mob_proxy, parse_accounts_to_list
from concurrent.futures import ThreadPoolExecutor, as_completed
from database import Database
from datetime import datetime
from alarm_bot import admin_error

NY_TZ = zoneinfo.ZoneInfo("America/New_York")
MOS_TZ = zoneinfo.ZoneInfo("Europe/Moscow")
db = Database()
profile_desc_fn = "profile_descriptions.jsonl"

# ----------------------------
# ЛОГГЕР (консоль + файл)
# ----------------------------
logger = logging.getLogger("xFerma")
logger.setLevel(logging.INFO)

if not logger.handlers:
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    fh = logging.FileHandler("xferma.log", encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)

    logger.addHandler(ch)
    logger.addHandler(fh)


class xFerma:

    def __init__(self, mode):
        self.mode = mode

        if self.mode == 'set_up':
            self.x_accounts_data = load_accounts_tweeterpy(mode=self.mode, load_cookies=True)
            self.x_banned_accounts_data = db.get_banned_accounts()
            logger.info("INIT: mode=set_up, загружаю аккаунты и запускаю set_up_new_accounts()")
            self.set_up_new_accounts()

        elif self.mode == 'work':
            self.x_accounts_data = load_accounts_tweeterpy(mode=self.mode)
            logger.info("INIT: mode=work, загружаю аккаунты и запускаю ferma_lifecycle()")
            self.ferma_lifecycle()

        elif self.mode == 'mutual_follow':
            logger.info("INIT: mode=mutual_follow, запускаю mutual_follow()")
            self.mutual_follow()

        elif self.mode == 'influ_follow':
            logger.info("INIT: mode=influ_follow, запускаю follow_influencers_for_new_accounts()")
            self.follow_influencers_for_new_accounts()

        elif self.mode == 'test':
            logger.info("INIT: TEST MODE ACTIVATED")

        else:
            logger.warning(f"INIT: неизвестный mode={self.mode}")

    # ----------------------------
    # SET-UP
    # ----------------------------
    def set_up_new_accounts(self):
        # clear banned accounts data (desc, ava) and delete
        for x_banned_acc_data in self.x_banned_accounts_data:
            self.clear_acc_info_if_banned(x_banned_acc_data, delete=True)
            delete_session(x_banned_acc_data['screen_name'])

        # start set-up for new accounts
        for x_account_data in self.x_accounts_data:
            logger.info(f"[SETUP] Работаю с @{x_account_data['screen_name']}")
            try:
                user_data = get_user_data(
                    x_account_data['screen_name'],
                    tw_cl=x_account_data['session']
                )
            except KeyError:
                logger.warning(f"[SETUP] @{x_account_data['screen_name']} вероятно забанен")
                admin_error(f"[SETUP] Аккаунт {x_account_data['screen_name']} вероятно забанен!")
                try:
                    db.update_is_banned(x_account_data["uid"])
                except Exception as e:
                    logger.exception(f"[SETUP] Ошибка при update_is_banned: {e}")
                continue
            except Exception as e:
                logger.exception(f"[SETUP] Ошибка при get_user_data для @{x_account_data['screen_name']}: {e}")
                continue

            if not user_data:
                logger.warning(f"[SETUP] Нет user_data для @{x_account_data['screen_name']}, пропускаю")
                continue

            try:
                ok = db.insert_new_acc(
                    user_data['uid'],
                    x_account_data['screen_name'],
                    None,
                    None,
                    x_account_data.get("password"),
                    x_account_data.get("auth_token"),
                    x_account_data.get("ua"),
                    x_account_data.get("proxy"),
                )
                logger.info(f"[SETUP] insert_new_acc ok={ok} uid={user_data['uid']}")
            except Exception as e:
                logger.exception(f"[SETUP] insert_new_acc ошибка: {e}")

            self.change_profile_info_logic(user_data, x_account_data)

    def change_profile_info_logic(self, user_data, twitter_working_account):
        # --- смена описания ---
        if (user_data.get('description') or '') == '':
            logger.info("[DESC] Обнаружено пустое описание")
            unused_desc_data = pick_unused_desc()
            if not unused_desc_data:
                logger.warning("[DESC] Нет неиспользованных описаний")
                return

            logger.info(f"[DESC] Выбрано описание: {unused_desc_data['desc']} (от {unused_desc_data['un']})")

            new_user_name = None
            try:
                if not is_emoji_in_name(user_data.get('name', '')):
                    if random.random() < 0.2:
                        new_user_name = user_data.get('name', '') + ' ' + get_filtered_emojis()
            except Exception as e:
                logger.exception(f"[DESC] Ошибка при генерации эмодзи для имени: {e}")

            change_profile_res = False
            for _ in range(2):
                try:
                    change_profile_res = twitter_search.change_profile_info(
                        twitter_working_account,
                        unused_desc_data["desc"],
                        new_user_name
                    )
                except Exception as e:
                    logger.exception(f"[DESC] Ошибка change_profile_info: {e}")
                    change_profile_res = False

                if change_profile_res == '131':
                    new_user_name = None  # retry без имени
                else:
                    break

            if change_profile_res:
                try:
                    mark_unmark_used_desc(unused_desc_data["un"], True)
                    db.update_desc_id(user_data['uid'], unused_desc_data["un"])
                    logger.info(f"[DESC] Успешно сменил описание → {unused_desc_data['desc']}")
                except Exception as e:
                    logger.exception(f"[DESC] Ошибка при фиксации описания: {e}")
            else:
                logger.exception("[DESC] Ошибка при смене описания")
        else:
            logger.info(f"[DESC] Уже есть описание: {user_data.get('description')}, пропускаю")

        # --- смена аватарки ---
        if user_data.get('is_def_ava'):
            logger.info("[AVA] Обнаружена дефолтная аватарка")
            unused_pfp_path = pick_unused_image('nft_ava_pack')
            logger.info(f"[AVA] Выбрана новая аватарка: {unused_pfp_path}")

            change_pfp_res = self.change_pfp(twitter_working_account, unused_pfp_path)
            if change_pfp_res:
                try:
                    used_pfp_path = mark_unmark_used_image(unused_pfp_path)
                    db.update_avatar(user_data['uid'], used_pfp_path)
                    logger.info(f"[AVA] Успешно сменил аватарку → {used_pfp_path}")
                except Exception as e:
                    logger.exception(f"[AVA] Ошибка при пометке/апдейте: {e}")
            else:
                logger.exception("[AVA] Ошибка при смене аватарки")
        else:
            logger.info("[AVA] У аккаунта уже есть аватарка, пропускаю")

        logger.info(f"[DONE] Обработка @{twitter_working_account['screen_name']} завершена")

    def change_pfp(self, twitter_working_account, pfp_filename):
        try:
            twitter_cookies_dict = twitter_working_account["cookies_dict"]
            headers = twitter_search.get_headers_for_twitter_account(twitter_cookies_dict)
            proxies = twitter_search.get_proxies_for_twitter_account(twitter_working_account)
            return upload_and_update_pfp(pfp_filename, headers, proxies)
        except Exception as e:
            logger.exception(f"[AVA] change_pfp ошибка: {e}")
            return False

    # ----------------------------
    # FOLLOWING (очередь)
    # ----------------------------
    def follow_influencers_for_new_accounts(
        self,
        influencers_file: str = "influencers.txt",
        max_workers: int = 10
    ):
        """
        Берёт все новые аккаунты (is_new=TRUE) и подписывает каждый на инфлюенсеров из файла.
        Обрабатывает до max_workers аккаунтов одновременно. Порядок инфлюенсеров
        для каждого аккаунта перемешивается отдельно.
        """
        # 1) загрузим usernames инфлюенсеров
        influencers = read_influencers(influencers_file)
        if not influencers:
            logger.warning("[INFLU] Список инфлюенсеров пуст")
            return

        # 2) берём новые аккаунты
        try:
            new_accounts = db.fetch_new_accounts()  # [{'uid':..., 'screen_name':...}, ...]
        except Exception as e:
            logger.exception(f"[INFLU] Ошибка db.fetch_new_accounts: {e}")
            return

        if not new_accounts:
            logger.info("[INFLU] Новых аккаунтов нет")
            return

        logger.info(f"[INFLU] Новых аккаунтов: {len(new_accounts)}")

        skip_users = {'iyannorth', 'khallid1993', 'siscazora'}
        total_actions = 0

        def worker(acc: dict) -> int:
            """Обрабатывает одного аккаунта: подписывает на всех инфлюенсеров в рандомном порядке."""
            uid = acc["uid"]
            sn  = acc["screen_name"]

            if sn in skip_users:
                logger.info(f"[INFLU][SKIP] @{sn} пропущен")
                return 0

            local_actions = 0
            infl_order = _shuffle_copy(influencers)  # у каждого аккаунта свой порядок
            logger.info(f"[INFLU] Обрабатываю @{sn} (uid={uid}), инфлюенсеров: {len(infl_order)}")

            for infl_sn in infl_order:
                try:
                    self.follow(acc, dst_screen_name=infl_sn)
                    logger.info(f"[INFLU] @{sn} → follow @{infl_sn}")
                    local_actions += 1
                except Exception as e:
                    logger.exception(f"[INFLU] Ошибка follow @{sn} → @{infl_sn}: {e}")

                time.sleep(random.randint(1, 8))  # лёгкий троттлинг внутри потока

            return local_actions

        # 3) параллельный запуск
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(worker, acc) for acc in new_accounts]
            for fut in as_completed(futures):
                try:
                    total_actions += fut.result()
                except Exception as e:
                    logger.exception(f"[INFLU] Ошибка в потоке: {e}")

        logger.info(f"[INFLU] Готово. Всего попыток подписки: {total_actions}")

    def mutual_follow(self):

        def enqueue_edges_for_new_accounts(new_ids: List[str]):
            logger.info(f"[ENQUEUE] Генерация задач для {len(new_ids)} новых аккаунтов")

            all_accounts = db.fetch_all_accounts()
            all_ids = {a["uid"] for a in all_accounts}
            new_ids_set = set(new_ids)
            old_ids = all_ids - new_ids_set
            logger.info(f"[ENQUEUE] Всего={len(all_ids)} | новых={len(new_ids_set)} | старых={len(old_ids)}")

            pairs: List[Tuple[str, str]] = []

            # 1) new -> new
            for i in range(len(new_ids)):
                for j in range(len(new_ids)):
                    if i == j:
                        continue
                    pairs.append((new_ids[i], new_ids[j]))

            # 2) new -> old
            for n in new_ids_set:
                for o in old_ids:
                    pairs.append((n, o))

            # 3) old -> new
            for o in old_ids:
                for n in new_ids_set:
                    pairs.append((o, n))

            try:
                db.bulk_upsert_follow_edges(pairs)
                logger.info(f"[ENQUEUE] Добавлено задач: {len(pairs)}")
            except Exception as e:
                logger.exception(f"[ENQUEUE] Ошибка bulk_upsert_follow_edges: {e}")

        def process_follow_edges(batch_size: int = 200, sleep_sec: float = 1.0) -> int:
            try:
                edges = db.fetch_pending_edges(limit=batch_size)
            except Exception as e:
                logger.exception(f"[PROCESS] Ошибка fetch_pending_edges: {e}")
                return 0

            if not edges:
                logger.info("[PROCESS] Нет задач")
                return -1

            logger.info(f"[PROCESS] Взято задач: {len(edges)}")
            ids_needed = {sid for sid, _ in edges} | {did for _, did in edges}
            try:
                accs = db.fetch_accounts_by_ids(ids_needed)
            except Exception as e:
                logger.exception(f"[PROCESS] Ошибка fetch_accounts_by_ids: {e}")
                return 0

            acc_map = {a["uid"]: a for a in accs}
            processed = 0

            for src_id, dst_id in edges:
                src = acc_map.get(src_id)
                dst = acc_map.get(dst_id)
                if not src or not dst:
                    try:
                        db.mark_edge_failed(src_id, dst_id, "src/dst not found")
                    except Exception as e:
                        logger.exception(f"[PROCESS] Ошибка mark_edge_failed: {e}")
                    logger.exception(f"[PROCESS] src={src_id} или dst={dst_id} не найдены")
                    continue

                try:
                    self.follow(src, dst_uid=dst)
                    db.mark_edge_done(src_id, dst_id)
                    processed += 1
                    logger.info(f"[PROCESS] ✅ {src['screen_name']} → {dst['screen_name']}")
                except Exception as e:
                    try:
                        db.mark_edge_failed(src_id, dst_id, str(e))
                    except Exception as e2:
                        logger.exception(f"[PROCESS] Ошибка mark_edge_failed: {e2}")
                    logger.exception(f"[PROCESS] Ошибка подписки {src_id}→{dst_id}: {e}")

                time.sleep(sleep_sec)

            logger.info(f"[PROCESS] Успешно выполнено: {processed}")
            return processed

        def finalize_new_flags():
            try:
                ready_ids = db.fetch_ready_to_unset_new()
            except Exception as e:
                logger.exception(f"[FINALIZE] Ошибка fetch_ready_to_unset_new: {e}")
                return

            if ready_ids:
                try:
                    db.set_is_new_false(ready_ids)
                    logger.info(f"[FINALIZE] Снял is_new для {len(ready_ids)}: {ready_ids}")
                except Exception as e:
                    logger.exception(f"[FINALIZE] Ошибка set_is_new_false: {e}")
            else:
                logger.info("[FINALIZE] Нет аккаунтов для обновления")

        def mutual_follow_maintainer():
            while True:
                n = process_follow_edges(batch_size=200, sleep_sec=1.0)
                if n == -1:
                    logger.info(f"[MAINTAINER] Все задачи выполнены!")
                    return
                finalize_new_flags()
                pause = 5 if n else 30
                logger.info(f"[MAINTAINER] Пауза: {pause}s")
                time.sleep(pause)

        # ---- Главная логика ----
        try:
            new_accounts = db.fetch_new_accounts()
            logger.info(f"[MAIN] Получено новых аккаунтов: {len(new_accounts)}")
            enqueue_edges_for_new_accounts([a["uid"] for a in new_accounts])
            mutual_follow_maintainer()
        except Exception as e:
            logger.exception(f"[MAIN] Ошибка mutual_follow: {e}")

    # ----------------------------
    # DAILY LIFECYCLE
    # ----------------------------
    def ferma_lifecycle(self):
        while True:
            try:
                now = datetime.now(MOS_TZ)
                hour = now.hour

                if 9 <= hour < 23:
                # if 0 <= hour < 23:
                    logger.info(f"[LIFE] Активный режим MOSCOW {now:%Y-%m-%d %H:%M:%S}")
                    for x_working_acc in self.x_accounts_data:
                        timeline = self.get_timeline(x_working_acc)
                        if timeline:
                            res = self.view_all_tweets(timeline, x_working_acc)
                            if res != 'ban':
                                if self.random_like_timeline(timeline, x_working_acc) == 'ban':
                                    self.x_accounts_data.remove(x_working_acc)
                            else:
                                self.x_accounts_data.remove(x_working_acc)
                        time.sleep(1)
                else:
                    logger.info(f"[SLEEP] Ночь в MOSCOW ({now}), ферма отдыхает")

                pause = random.randint(1000, 10000)
                logger.info(f"[LIFE] Пауза {pause}s")
                time.sleep(pause)
            except Exception as e:
                logger.exception(f"[LIFE] Критическая ошибка цикла: {e}")
                admin_error(f"[LIFE] Критическая ошибка цикла: {e}")
                time.sleep(10)

    def random_like_timeline(self, timeline, twitter_working_account, count_range=(2, 5)):
        try:
            count = random.randint(*count_range)
            if len(timeline) < count:
                logger.warning("[LIKE] В ленте меньше твитов, чем нужно для выборки")
                count = max(0, len(timeline))
            chosen_tweets = random.sample(timeline, count) if count > 0 else []

            for t in chosen_tweets:
                tid = t["tweet"]["id"]
                uid = t["tweet"]["user_id"]

                if self.view(twitter_working_account, tid, uid) == 'ban':
                    return 'ban'
                if self.like(twitter_working_account, tid) == 'ban':
                    return 'ban'

                if random.random() < 0.4:
                    if self.retweet(twitter_working_account, tid) == 'ban':
                        return 'ban'
                if random.random() < 0.15:
                    if self.bookmark(twitter_working_account, tid) == 'ban':
                        return 'ban'

            logger.info(f"[LIKE] Обработано твитов: {len(chosen_tweets)} для @{twitter_working_account.get('screen_name')}")
        except Exception as e:
            logger.exception(f"[LIKE] Ошибка random_like_timeline: {e}")

    def view_all_tweets(self, timeline, twitter_working_account, sleep_range=(0.2, 1.0)):
        """
        Просматривает (self.view) ВСЕ твиты из timeline.
        :param timeline: список твитов (как в твоей random_like_timeline)
        :param twitter_working_account: аккаунт, от имени которого смотрим
        :param sleep_range: (min_sec, max_sec) пауза между просмотрами
        """
        try:
            if not timeline:
                logger.info(f"[VIEW-ALL] Пустой timeline для @{twitter_working_account.get('screen_name')}")
                return

            viewed = 0
            for i, t in enumerate(timeline, start=1):
                try:
                    tid = t["tweet"]["id"]
                    uid = t["tweet"]["user_id"]
                except KeyError:
                    logger.exception(f"[VIEW-ALL] Некорректный формат твита на позиции {i}: {t}")
                    continue

                try:
                    res = self.view(twitter_working_account, tid, uid)
                    if res == 'ban':
                        return res
                    viewed += 1
                except Exception:
                    logger.exception(f"[VIEW-ALL] Ошибка просмотра tweetId={tid} (user_id={uid})")
                    # продолжаем со следующим твитом

                # лёгкий троттлинг
                if sleep_range and sleep_range[0] >= 0:
                    time.sleep(random.uniform(*sleep_range))

            logger.info(
                f"[VIEW-ALL] Просмотрено твитов: {viewed} из {len(timeline)} для @{twitter_working_account.get('screen_name')}")
        except Exception:
            logger.exception("[VIEW-ALL] Критическая ошибка в view_all_tweets")

    # ----------------------------
    # TWITTER ACTIONS
    # ----------------------------
    def follow(self, src, dst_uid=None, dst_screen_name=None):
        try:
            if dst_uid:
                res = twitter_search.user_friendship(src, "follow", user_id=dst_uid["uid"])
                print(res)
            elif dst_screen_name:
                res = twitter_search.user_friendship(src, "follow", screen_name=dst_screen_name)
                print(res)

            if res == 'ban':
                logger.info(f"[VIEW] Аккаунт {dst_uid or dst_screen_name} вероятно забанен!")
                admin_error(f"[VIEW] Аккаунт {dst_uid or dst_screen_name} вероятно забанен!")
                try:
                    if dst_uid:
                        db.update_is_banned(dst_uid["uid"])
                    elif dst_screen_name:
                        db.update_is_banned_by_sn(dst_screen_name)
                except Exception as e:
                    logger.exception(f"[SETUP] Ошибка при update_is_banned: {e}")
                return 'ban'
        except Exception as e:
            print(traceback.format_exc())
            logger.exception(f"[FOLLOW] Ошибка follow: {e}")
            raise

    def like(self, twitter_working_account, tweet_id):
        try:
            res = twitter_search.like_tweet_by_tweet_id(twitter_working_account, tweet_id)
            if res == '139':
                logger.info(f"[LIKE] Уже лайкнуто (tweetId={tweet_id})")
            elif res == 'ban':
                logger.info(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно забанен!")
                admin_error(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно забанен!")
                try:
                    db.update_is_banned(twitter_working_account["uid"])
                except Exception as e:
                    logger.exception(f"[SETUP] Ошибка при update_is_banned: {e}")
                return 'ban'
        except Exception as e:
            logger.exception(f"[LIKE] Ошибка like: {e}")

    def retweet(self, twitter_working_account, tweet_id):
        try:
            res = twitter_search.rt_tweet_by_tweet_id(twitter_working_account, tweet_id)
            if res == '139':
                logger.info(f"[RT] Уже ретвитнуто (tweetId={tweet_id})")
            elif res == 'ban':
                logger.info(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно забанен!")
                admin_error(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно забанен!")
                try:
                    db.update_is_banned(twitter_working_account["uid"])
                except Exception as e:
                    logger.exception(f"[SETUP] Ошибка при update_is_banned: {e}")
                return 'ban'
        except Exception as e:
            logger.exception(f"[RT] Ошибка retweet: {e}")

    def bookmark(self, twitter_working_account, tweet_id):
        try:
            res = twitter_search.bm_tweet_by_tweet_id(twitter_working_account, tweet_id)
            if res == '139':
                logger.info(f"[BM] Уже в закладках (tweetId={tweet_id})")
            elif res == 'ban':
                logger.info(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно забанен!")
                admin_error(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно забанен!")
                try:
                    db.update_is_banned(twitter_working_account["uid"])
                except Exception as e:
                    logger.exception(f"[SETUP] Ошибка при update_is_banned: {e}")
                return 'ban'
        except Exception as e:
            logger.exception(f"[BM] Ошибка bookmark: {e}")

    def reply(self, twitter_working_account, tweet_text, tweet_id):
        try:
            res = twitter_search.reply_tweet_by_tweet_id(twitter_working_account, tweet_text, tweet_id)
            if res == 'ban':
                logger.info(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно забанен!")
                admin_error(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно забанен!")
                try:
                    db.update_is_banned(twitter_working_account["uid"])
                except Exception as e:
                    logger.exception(f"[SETUP] Ошибка при update_is_banned: {e}")
                return 'ban'
        except Exception as e:
            logger.exception(f"[REPLY] Ошибка reply: {e}")

    def view(self, twitter_working_account, tweet_id, author_id):
        try:
            res = twitter_search.view_tweet_by_tweet_id(twitter_working_account, tweet_id, author_id=author_id)
            if res == 'ban':
                logger.info(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно забанен!")
                admin_error(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно забанен!")
                try:
                    db.update_is_banned(twitter_working_account["uid"])
                except Exception as e:
                    logger.exception(f"[SETUP] Ошибка при update_is_banned: {e}")
                return 'ban'
        except Exception as e:
            logger.exception(f"[VIEW] Ошибка view: {e}")

    # def multiple_views(self, views_count, tweet_id, author_id):
    #     try:
    #         # логика взята из твоего кода; поправь по нужде
    #         db.get_working_accounts(count=1 if views_count <= 300 else math.ceil(views_count/300))
    #         for _ in range(1):
    #             twitter_search.view_tweet_by_tweet_id(twitter_working_account, tweet_id, author_id=author_id)
    #             time.sleep(0.5)
    #     except Exception as e:
    #         logger.exception(f"[VIEW] Ошибка multiple_views: {e}")

    def get_timeline(self, x_working_acc):
        try:
            return twitter_search.get_latest_timeline(x_working_acc)
        except Exception as e:
            logger.exception(f"[VIEW] Критическая ошибка в multiple_views: {e}")

    def clear_acc_info_if_banned(self, acc_data, delete=False):
        if acc_data["avatar"]:
            mark_unmark_used_image(acc_data["avatar"], instruction=False)
        if acc_data["description_id"]:
            mark_unmark_used_desc(acc_data["description_id"], instruction=False)
        if delete:
            db.delete_banned_by_uid(acc_data["uid"])


# ----------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (logging вместо print)
# ----------------------------
def dump_descriptions(uns, client, output_file=profile_desc_fn):
    logger.info(f"[DESC-DUMP] Начинаю для {len(uns)} пользователей")
    for i, un in enumerate(uns, start=1):
        if i % 50 == 0:
            logger.info(f"[DESC-DUMP] Reinit client на итерации {i}")
            client = initialize_client(proxy=get_random_mob_proxy())
        logger.info(f"[DESC-DUMP] ({i}/{len(uns)}) @{un}")
        try:
            ava, desc, uid = get_user_data(un, client)
        except Exception as e:
            logger.exception(f"[DESC-DUMP] Ошибка get_user_data @{un}: {e}")
            continue

        if desc:
            try:
                member = {"un": un, "desc": desc}
                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(member, ensure_ascii=False) + "\n")
                logger.info(f"[DESC-DUMP] Сохранено @{un}")
            except Exception as e:
                logger.exception(f"[DESC-DUMP] Ошибка записи @{un}: {e}")
        else:
            logger.warning(f"[DESC-DUMP] Нет описания @{un}")

    logger.info(f"[DESC-DUMP] Готово → {output_file}")


def load_usernames(file_path="members.json"):
    logger.info(f"[LOAD] usernames из {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    usernames = [member["username"] for member in data]
    logger.info(f"[LOAD] Загружено usernames: {len(usernames)}")
    return usernames


def pick_unused_desc(filename=profile_desc_fn):
    """Выбирает случайное неиспользованное описание"""
    with open(filename, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]
    unused = [entry for entry in lines if not entry.get("used", False)]
    if not unused:
        logger.warning("[DESC] Все описания уже использованы")
        return None
    chosen = random.choice(unused)
    logger.info(f"[DESC] Выбрано описание от '{chosen['un']}'")
    return chosen


def mark_unmark_used_desc(desc_id, instruction, filename=profile_desc_fn):
    """Помечает/снимает used у описания"""
    with open(filename, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f]

    for entry in lines:
        if entry["un"] == desc_id:
            entry["used"] = instruction
            break

    with open(filename, "w", encoding="utf-8") as f:
        for entry in lines:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    logger.info(f"[DESC] {'MARK' if instruction else 'UNMARK'} used для {desc_id}")


def pick_unused_image(folder):
    """
    Выбирает случайное изображение из папки, у которого в имени нет [used].
    """
    files = [
        f for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f)) and "[used]" not in f
    ]
    if not files:
        logger.warning("[IMG] Все картинки уже использованы")
        return None
    chosen = random.choice(files)
    path = os.path.join(folder, chosen)
    logger.info(f"[IMG] Выбрано изображение: {path}")
    return path


def mark_unmark_used_image(chosen_path, instruction=True):
    """
    Помечает выбранное изображение как использованное (instruction=True)
    или снимает пометку (instruction=False).
    """
    folder, filename = os.path.split(chosen_path)
    name, ext = os.path.splitext(filename)

    if instruction:
        if "[used]" not in name:
            new_name = f"{name}[used]{ext}"
            new_path = os.path.join(folder, new_name)
            os.rename(chosen_path, new_path)
            logger.info(f"[IMG] MARK used: {new_path}")
            return new_path
        else:
            logger.info(f"[IMG] Уже помечено: {chosen_path}")
            return chosen_path
    else:
        if "[used]" in name:
            new_name = name.replace("[used]", "") + ext
            new_path = os.path.join(folder, new_name)
            os.rename(chosen_path, new_path)
            logger.info(f"[IMG] UNMARK used: {new_path}")
            return new_path
        else:
            logger.info(f"[IMG] Не было помечено: {chosen_path}")
            return chosen_path


def is_emoji_in_name(acc_name: str) -> bool:
    for ch in acc_name:
        if ch in emoji.EMOJI_DATA:
            return True
    return False


def get_random_emojis(count_range=(1, 3)):
    all_emojis = list(emoji.EMOJI_DATA.keys())
    count = random.randint(*count_range)
    chosen = random.sample(all_emojis, count)
    return "".join(chosen)


def get_filtered_emojis():
    blacklist = {"☑️", "✅", "✔️", "🇷🇺", "🇺🇦", "🖕"}
    s = get_random_emojis()
    return "".join(ch for ch in s if ch not in blacklist)


def read_influencers(file_path='influencers.txt') -> list[str]:
    """Читает usernames инфлюенсеров из файла (по одному на строке)."""
    usernames = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            u = line.strip().lstrip("@")
            if u:
                usernames.append(u)
    return list(dict.fromkeys(usernames))  # убираем дубли, сохраняя порядо

def _shuffle_copy(seq):
    lst = list(seq)
    random.shuffle(lst)
    return lst

def delete_session(screen_name: str):
    files = [
        f"x_accs_pkl_sessions/{screen_name}.pkl",
        f"x_accs_cookies/{screen_name}.pkl"
    ]

    deleted = []
    for file_path in files:
        try:
            os.remove(file_path)
            deleted.append(file_path)
        except FileNotFoundError:
            # If the file doesn't exist, just skip
            pass
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")

    return deleted

if __name__ == '__main__':
    # set_up_new_accounts()
    from tweeterpyapi import process_account
    ferma = xFerma(mode='work')
    # ferma = xFerma(mode='test')
    # banned_acc = {
    #     'uid': 527403566,
    #     'avatar': 'nft_ava_Zards #18_18[used].png',
    #     'description_id': 'prsnfx',
    # }
    # ferma.clear_acc_info_if_banned(banned_acc)
    # for acc in db.get_working_accounts():
    #     ferma.like(acc, 1817467635707043968)
    #     time.sleep(3)
    # accs = load_accounts_tweeterpy(mode='work', how_many_accounts=1)
    # for acc in accs:
    #     print(ferma.like(acc, 1972376013297586551))
    #     time.sleep(1)
    # print(ferma.like(one_time_acc[1], 1972376013297586551))
    # one_time_acc = db.fetch_accounts_by_ids({'472720290'})
    # one_time_acc = {
    #     'screen_name': 'siscazora',
    #     'ua': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
    #     'proxy': 'xZ1GLj:unTrU4@138.59.206.38:9491'
    # }
    # one_time_acc['cookies_dict'] = twitter_search.load_cookies_for_twitter_account_from_file(f'x_accs_cookies/{one_time_acc["screen_name"]}.json')
    # acc = process_account(one_time_acc)
    # print(ferma.get_timeline(acc))
    # print(ferma.view(acc, 1972376013297586551, 1972376013297586551))
    # print(ferma.follow(one_time_acc[0], {'uid': '3278906401'}))
    # TODO: CHECK IP (1st check 16.09)!!!! 138.59.206.77 (usa ip mobile proxy) gate.nodemaven.com:8080:vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-412b573343e14-filter-medium:e3ibl6cpq4