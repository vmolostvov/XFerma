import time, json, random, os, emoji, math, logging, tempfile
import traceback
import zoneinfo
import twitter_search
# from twitter_search import load_accounts_cookies_login
# from typing import Tuple, List
from x_media_uploader import upload_and_update_pfp
from tweeterpyapi import load_accounts_tweeterpy, get_user_data, initialize_client, save_cookies_and_sess_with_timeout, get_user_id_by_sn
from config import nodemaven_proxy_rotating, get_random_mob_proxy, parse_accounts_to_list, parse_cid
# from concurrent.futures import ThreadPoolExecutor, as_completed
from database import Database
from datetime import datetime
from alarm_bot import admin_error
from typing import Callable, Optional

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
            # save_cookies_and_sess_with_timeout()
            self.x_accounts_data = load_accounts_tweeterpy(mode=self.mode, load_cookies=True)
            self.x_banned_accounts_data = db.get_banned_accounts()
            logger.info("INIT: mode=set_up, загружаю аккаунты и запускаю set_up_new_accounts()")
            self.set_up_new_accounts()

        elif self.mode == 'work':
            self.x_accounts_data = load_accounts_tweeterpy(mode=self.mode)
            logger.info("INIT: mode=work, загружаю аккаунты и запускаю ferma_lifecycle()")
            self.ferma_lifecycle()

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
            try:
                self.clear_acc_info_if_banned(x_banned_acc_data, delete=True)
                delete_session(x_banned_acc_data['screen_name'])
            except Exception as e:
                logger.exception('Ошибка при очистке файлов сессии забаненого аккаунта!')

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
                    parse_cid(x_account_data.get("proxy")),
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

    # def follow_influencers_for_new_accounts(
    #     self,
    #     influencers_file: str = "influencers.txt",
    #     max_workers: int = 10
    # ):
    #     """
    #     Берёт все новые аккаунты (is_new=TRUE) и подписывает каждый на инфлюенсеров из файла.
    #     Обрабатывает до max_workers аккаунтов одновременно. Порядок инфлюенсеров
    #     для каждого аккаунта перемешивается отдельно.
    #     """
    #     # 1) загрузим usernames инфлюенсеров
    #     influencers = read_influencers(influencers_file)
    #     if not influencers:
    #         logger.warning("[INFLU] Список инфлюенсеров пуст")
    #         return
    #
    #     # 2) берём новые аккаунты
    #     try:
    #         new_accounts = db.fetch_new_accounts()  # [{'uid':..., 'screen_name':...}, ...]
    #     except Exception as e:
    #         logger.exception(f"[INFLU] Ошибка db.fetch_new_accounts: {e}")
    #         return
    #
    #     if not new_accounts:
    #         logger.info("[INFLU] Новых аккаунтов нет")
    #         return
    #
    #     logger.info(f"[INFLU] Новых аккаунтов: {len(new_accounts)}")
    #
    #     skip_users = {'iyannorth', 'khallid1993', 'siscazora'}
    #     total_actions = 0
    #
    #     def worker(acc: dict) -> int:
    #         """Обрабатывает одного аккаунта: подписывает на всех инфлюенсеров в рандомном порядке."""
    #         uid = acc["uid"]
    #         sn  = acc["screen_name"]
    #
    #         if sn in skip_users:
    #             logger.info(f"[INFLU][SKIP] @{sn} пропущен")
    #             return 0
    #
    #         local_actions = 0
    #         infl_order = _shuffle_copy(influencers)  # у каждого аккаунта свой порядок
    #         logger.info(f"[INFLU] Обрабатываю @{sn} (uid={uid}), инфлюенсеров: {len(infl_order)}")
    #
    #         for infl_sn in infl_order:
    #             try:
    #                 self.follow(acc, dst_screen_name=infl_sn)
    #                 logger.info(f"[INFLU] @{sn} → follow @{infl_sn}")
    #                 local_actions += 1
    #             except Exception as e:
    #                 logger.exception(f"[INFLU] Ошибка follow @{sn} → @{infl_sn}: {e}")
    #
    #             time.sleep(random.randint(1, 8))  # лёгкий троттлинг внутри потока
    #
    #         return local_actions
    #
    #     # 3) параллельный запуск
    #     with ThreadPoolExecutor(max_workers=max_workers) as ex:
    #         futures = [ex.submit(worker, acc) for acc in new_accounts]
    #         for fut in as_completed(futures):
    #             try:
    #                 total_actions += fut.result()
    #             except Exception as e:
    #                 logger.exception(f"[INFLU] Ошибка в потоке: {e}")
    #
    #     logger.info(f"[INFLU] Готово. Всего попыток подписки: {total_actions}")


        # def enqueue_edges_for_new_accounts(new_ids: List[str]):
        #     logger.info(f"[ENQUEUE] Генерация задач для {len(new_ids)} новых аккаунтов")
        #
        #     all_accounts = db.fetch_all_accounts()
        #     all_ids = {a["uid"] for a in all_accounts}
        #     new_ids_set = set(new_ids)
        #     old_ids = all_ids - new_ids_set
        #     logger.info(f"[ENQUEUE] Всего={len(all_ids)} | новых={len(new_ids_set)} | старых={len(old_ids)}")
        #
        #     pairs: List[Tuple[str, str]] = []
        #
        #     # 1) new -> new
        #     for i in range(len(new_ids)):
        #         for j in range(len(new_ids)):
        #             if i == j:
        #                 continue
        #             pairs.append((new_ids[i], new_ids[j]))
        #
        #     # 2) new -> old
        #     for n in new_ids_set:
        #         for o in old_ids:
        #             pairs.append((n, o))
        #
        #     # 3) old -> new
        #     for o in old_ids:
        #         for n in new_ids_set:
        #             pairs.append((o, n))
        #
        #     try:
        #         db.bulk_upsert_follow_edges(pairs)
        #         logger.info(f"[ENQUEUE] Добавлено задач: {len(pairs)}")
        #     except Exception as e:
        #         logger.exception(f"[ENQUEUE] Ошибка bulk_upsert_follow_edges: {e}")

    def process_follow_edges(self, batch_size: int = 200, sleep_sec: float = 1.0) -> int:
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

    def finalize_new_flags(self):
        try:
            ready_ids = db.fetch_ready_to_unset_new_strict()
        except Exception as e:
            logger.exception(f"[FINALIZE] Ошибка fetch_ready_to_unset_new_strict: {e}")
            return

        if ready_ids:
            try:
                db.set_is_new_false(ready_ids)
                logger.info(f"[FINALIZE] Снял is_new для {len(ready_ids)}: {ready_ids}")
            except Exception as e:
                logger.exception(f"[FINALIZE] Ошибка set_is_new_false: {e}")
        else:
            logger.info("[FINALIZE] Нет аккаунтов для обновления")

        # def mutual_follow_maintainer():
        #     while True:
        #         n = process_follow_edges(batch_size=200, sleep_sec=1.0)
        #         if n == -1:
        #             logger.info(f"[MAINTAINER] Все задачи выполнены!")
        #             return
        #         finalize_new_flags()
        #         pause = 5 if n else 30
        #         logger.info(f"[MAINTAINER] Пауза: {pause}s")
        #         time.sleep(pause)
        #
        # # ---- Главная логика ----
        # try:
        #     new_accounts = db.fetch_new_accounts()
        #     logger.info(f"[MAIN] Получено новых аккаунтов: {len(new_accounts)}")
        #     enqueue_edges_for_new_accounts([a["uid"] for a in new_accounts])
        #     mutual_follow_maintainer()
        # except Exception as e:
        #     logger.exception(f"[MAIN] Ошибка mutual_follow: {e}")

    def schedule_follows_tick(
            self,
            influencers_file="influencers.jsonl",
            per_tick=2,  # максимум подписок на аккаунт за один тик
            quota_min=3, quota_max=10  # дневная квота на аккаунт
    ):
        """
        Планирует небольшую порцию подписок для каждого аккаунта в текущий момент.
        Вызывать регулярно в дневные часы (NY), например, каждые 5–10 минут.
        """
        exclude_list = ['iyannorth', 'khallid1993']
        influencers = db.fetch_influencers_with_uid(influencers_file)
        db.ensure_influencers_present(influencers)

        accounts = db.fetch_all_accounts()
        if not accounts:
            logger.info("[SCHED] нет аккаунтов")
            return 0

        today_ny = datetime.now(NY_TZ).date()
        total_added = 0

        for acc in accounts:
            src_id = acc["id"]
            sn = acc["screen_name"]

            # получаем/создаём дневную квоту
            quota = db.get_daily_quota(src_id, today_ny, quota_min, quota_max)

            done_today = db.count_done_today(src_id)
            pending = db.count_pending_today(src_id)
            remaining = max(quota - (done_today + pending), 0)

            if remaining <= 0:
                logger.info(
                    f"[SCHED] @{sn}: лимит на сегодня исчерпан (quota={quota}, done={done_today}, pending={pending})")
                continue

            # ограничим текущий тик
            to_schedule = min(per_tick, remaining)

            already = db.fetch_followed_or_pending_dst_ids(src_id)

            pairs = []

            # 1) инфлюенсеры
            if influencers and sn not in exclude_list:
                for influencer in influencers:
                    dst = influencer["uid"]
                    if not dst or dst == src_id or dst in already:
                        continue
                    pairs.append((src_id, dst))
                    if len(pairs) >= to_schedule:
                        break

            # 2) база аккаунтов
            if len(pairs) < to_schedule:
                for a in accounts:
                    dst = a["id"]
                    if dst == src_id or dst in already:
                        continue
                    pairs.append((src_id, dst))
                    if len(pairs) >= to_schedule:
                        break

            added = db.bulk_upsert_follow_edges(pairs)
            total_added += added
            logger.info(
                f"[SCHED] @{sn}: добавлено {added}/{to_schedule} (remaining={remaining}, quota={quota}, done={done_today}, pending={pending})")

        logger.info(f"[SCHED] тик планировщика завершён, всего добавлено задач: {total_added}")
        return total_added

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

                    # планируем немного задач
                    try:
                        self.schedule_follows_tick(
                            influencers_file="influencers.jsonl",
                            per_tick=2,  # 1–2 задачи за тик на аккаунт
                            quota_min=3,
                            quota_max=10
                        )
                    except Exception:
                        logger.exception("[LIFE] ошибка schedule_follows_tick")

                    # обрабатываем очередь фоллов (можно в отдельном воркере)
                    try:
                        processed = self.process_follow_edges(batch_size=200, sleep_sec=1.0)
                        if processed:
                            self.finalize_new_flags()
                    except Exception:
                        logger.exception("[LIFE] ошибка process_follow_edges")

                    # жизнь аккаунтов
                    for x_working_acc in self.x_accounts_data.copy():
                        logger.info(f"[ACC-LIFE] Работаю с аккаунтом ({x_working_acc['screen_name']}) !")
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
                pause_readable = format_duration(pause)
                logger.info(f"[LIFE] Пауза {pause_readable}")
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
            logger.info(f"[FOLLOW] Аккаунт {src['screen_name']} выполняет подписку на {dst_uid['screen_name'] or dst_screen_name} !")
            if dst_uid:
                res = twitter_search.user_friendship(src, "follow", user_id=dst_uid["uid"])
                print(res)
            elif dst_screen_name:
                res = twitter_search.user_friendship(src, "follow", screen_name=dst_screen_name)
                print(res)

            if res == 'ban':
                logger.info(f"[FOLLOW] Аккаунт {src['screen_name']} вероятно забанен!")
                admin_error(f"[FOLLOW] Аккаунт {src['screen_name']} вероятно забанен!")
                try:
                    db.update_is_banned_by_sn(src['screen_name'])
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
            for i in range(3):
                timeline = twitter_search.get_latest_timeline(x_working_acc)
                if timeline:
                    return timeline
                else:
                    time.sleep(10)

        except Exception as e:
            logger.exception(f"[TIMELINE] Критическая ошибка в get_timeline: {e}")

        logger.warning(f'[TIMELINE] Невозможно получить timeline для аккаунта {x_working_acc["screen_name"]}!')

    def clear_acc_info_if_banned(self, acc_data, delete=False):
        if acc_data["avatar"]:
            mark_unmark_used_image(acc_data["avatar"], instruction=False)
        if acc_data["description_id"]:
            mark_unmark_used_desc(acc_data["description_id"], instruction=False)
        if delete:
            db.delete_banned_by_uid(acc_data["uid"])


    def accounts_health_test(self, accs):
        for acc in accs:
            self.view(acc,1976324634992636355, 44196397)

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


def update_influencers_jsonl_resilient(
    txt_path: str = "influencers.txt",
    jsonl_path: str = "influencers.jsonl",
    get_id_fn: Optional[Callable[[str], str]] = None,
) -> dict:
    """
    Синхронизирует influencers.txt -> influencers.jsonl с повторными попытками.
    - Для каждого screen_name из txt пытается получить uid (get_id_fn).
    - Если раньше uid не удалось (или был пустым), при следующем запуске пробует снова.
    - jsonl перезаписывается атомарно (без дублей): одна строка на каждый screen_name.
    Возвращает статистику: {'total':..., 'resolved_now':..., 'still_unresolved':..., 'written':...}
    """
    if get_id_fn is None:
        raise ValueError("Нужна функция get_id_fn(screen_name) -> uid")

    if not os.path.exists(txt_path):
        raise FileNotFoundError(f"Не найден файл {txt_path}")

    # 1) читаем TXT: убираем пустые, '@', дубли, сохраняем порядок
    uniq_txt = []
    seen = set()
    with open(txt_path, "r", encoding="utf-8") as f:
        for line in f:
            sn = line.strip().lstrip("@")
            if not sn:
                continue
            if sn not in seen:
                uniq_txt.append(sn)
                seen.add(sn)

    # 2) читаем существующий JSONL -> словарь sn -> uid (может быть "", None)
    existing = {}
    if os.path.exists(jsonl_path):
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    obj = json.loads(ln)
                    sn = (obj.get("screen_name") or "").strip()
                    uid = obj.get("uid")
                    if sn:
                        existing[sn] = uid
                except json.JSONDecodeError:
                    # битую строку пропускаем
                    continue

    total = len(uniq_txt)
    resolved_now = 0
    still_unresolved = 0

    # 3) формируем итоговый порядок и значения uid
    result_rows = []
    for sn in uniq_txt:
        current_uid = existing.get(sn)

        # решаем, нужно ли пробовать получать uid заново:
        need_resolve = (current_uid is None) or (str(current_uid).strip() == "")

        if need_resolve:
            try:
                new_uid = get_id_fn(sn)
                # нормализуем к строке
                new_uid = "" if new_uid is None else str(new_uid)
                if new_uid:
                    current_uid = new_uid
                    resolved_now += 1
                else:
                    # всё ещё не получилось
                    current_uid = ""
                    still_unresolved += 1
            except Exception:
                # не удалось на этом запуске
                current_uid = ""
                still_unresolved += 1

        # если uid уже был в файле — оставим его как есть
        result_rows.append({"screen_name": sn, "uid": str(current_uid or "")})

    # 4) атомарно перезаписываем JSONL (без дублей)
    os.makedirs(os.path.dirname(jsonl_path) or ".", exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="influ_", suffix=".jsonl", dir=os.path.dirname(jsonl_path) or ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            for row in result_rows:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
        os.replace(tmp_path, jsonl_path)  # атомарная замена
    except Exception:
        # при сбое удалим временный файл
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        raise

    return {
        "total": total,
        "resolved_now": resolved_now,
        "still_unresolved": still_unresolved,
        "written": len(result_rows),
    }

# Функция форматирования паузы в читаемый вид
def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {sec}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m {sec}s"

if __name__ == '__main__':
    if __name__ == '__main__':
        print("\n🚀  Добро пожаловать в xFerma!")
        print("Выберите режим работы:")
        print("  1 — Работа фермы (work)")
        print("  2 — Настройка новых аккаунтов (set_up)")
        print("  3 — Тестовый режим (testing)")
        print("  0 — Выход\n")

        choice = input("👉 Введите номер режима: ").strip()

        if choice == '1':
            print("\n▶ Запуск фермы в рабочем режиме...\n")
            xFerma(mode='work')

        elif choice == '2':
            print("\n⚙ Настройка новых аккаунтов...\n")
            xFerma(mode='set_up')


        elif choice == '3':
            print("\n🧪 Тестовый режим...\n")
            print("  1 — Health-test аккаунта (load & view tweet)")
            print("  2 — Регенерация сессии аккаунта (save_cookies_and_sess)\n")

            choice = input("👉 Введите номер режима: ").strip()
            ferma = xFerma(mode='test')

            if choice == '1':
                print("\n▶ Запуск режима проверки аккаунтов...\n")
                acc_un = input("🔹 Введите username тестового аккаунта (без @): ").strip()
                if not acc_un:
                    print("❌ Вы не ввели username. Завершение работы.")
                else:
                    acc = load_accounts_tweeterpy(mode='test', acc_un=acc_un)
                    ferma.accounts_health_test(acc)

            elif choice == '2':
                print("\n⚙ Запуск режима регенерации сессии аккаунта...\n")
                acc_un = input("🔹 Введите username тестового аккаунта (без @): ").strip()
                if not acc_un:
                    print("❌ Вы не ввели username. Завершение работы.")
                else:
                    accs = db.get_working_accounts(screen_name=acc_un)
                    save_cookies_and_sess_with_timeout(outdated_session=accs[0])


        elif choice == '0':
            print("\n👋 Выход из программы. До встречи!")
            exit(0)

        else:
            print("\n❌ Неверный выбор. Перезапустите программу и выберите правильный режим.")

    """OSError: Tunnel connection failed: 503 Service Unavailable"""
