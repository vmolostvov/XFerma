import time, json, random, os, emoji, logging, tempfile
import zoneinfo
import twitter_search
# from twitter_search import load_accounts_cookies_login
# from typing import Tuple, List
from multiprocessing import Process
from x_media_uploader import upload_and_update_pfp
from tweeterpyapi import load_accounts_tweeterpy, get_user_data, initialize_client, save_cookies_and_sess_with_timeout, process_account, load_accounts_cookies
from config import get_random_mob_proxy, parse_cid
from pixelscan_checker import get_proxy_by_sid, generate_valid_sid_nodemaven_proxy
# from concurrent.futures import ThreadPoolExecutor, as_completed
from database import Database
from datetime import datetime
from alarm_bot import admin_error
from typing import Callable, Optional
from selen import regen_auth, create_new_acc

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

    fh = logging.FileHandler("loggers/xferma.log", encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)

    logger.addHandler(ch)
    logger.addHandler(fh)


class xFerma:

    def __init__(self, mode):
        self.mode = mode

        if self.mode == 'set_up':
            save_cookies_and_sess_with_timeout()
            self.x_accounts_data = load_accounts_tweeterpy(mode=self.mode, load_cookies=True)
            self.x_banned_accounts_data = db.get_banned_accounts()
            logger.info("INIT: mode=set_up, загружаю аккаунты и запускаю set_up_new_accounts()")
            self.set_up_new_accounts()

        elif self.mode == 'work':
            self.x_accounts_data = load_accounts_tweeterpy(mode=self.mode)
            random.shuffle(self.x_accounts_data)
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
                elif change_profile_res == 'ban':
                    logger.info(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно забанен!")
                    try:
                        db.update_is_banned(twitter_working_account["uid"])
                    except Exception as e:
                        logger.exception(f"[SETUP] Ошибка при update_is_banned: {e}")
                    return
                elif change_profile_res == 'proxy_dead':
                    logger.info(f"[VIEW] У аккаунта {twitter_working_account['screen_name']} умер прокси!")
                    if _ == 1:
                        return
                    twitter_working_account = self.regenerate_acc_object(twitter_working_account, new_proxy=True)
                    if twitter_working_account:
                        continue
                elif change_profile_res == 'no_auth':
                    logger.info(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно нуждается в обновлении сессии!")
                    try:
                        db.update_regen_session(twitter_working_account["uid"], True)
                    except Exception as e:
                        logger.exception(f"[SETUP] Ошибка при update_regen_session: {e}")
                    return
                elif change_profile_res == 'lock':
                    logger.info(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно временно заблокирован!")
                    try:
                        db.update_is_locked(twitter_working_account["uid"])
                    except Exception as e:
                        logger.exception(f"[SETUP] Ошибка при update_is_locked: {e}")
                    return
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

    def change_email_and_save(self, twitter_working_account):
        new_email_data = db.get_random_mail()[0]
        # new_email_data = [{
        #     'email': 'a.ballast280@outlook.com',
        #     'pass': '3)q(vbEC7MHZf72CcBgw',
        #     'proxy': 'vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-49ddd6de7aeaa-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080'
        # }][0]
        new_email = new_email_data['email']

        un = twitter_working_account['screen_name']

        logger.info(f"[MAIL_VERIF] Выбрана почта: {new_email} для аккаунта @{un}")

        for i in range(2):
            try:
                change_email_res = twitter_search.change_email(twitter_working_account, new_email_data)
            except Exception as e:
                logger.exception(f"[MAIL_VERIF] change_email ошибка: {e}")
                return False

            if change_email_res == '131':
                logger.info(f"[MAIL_VERIF] Аккаунт {un} неизвестная ошибка!")
            elif change_email_res == 'ban':
                logger.info(f"[MAIL_VERIF] Аккаунт {un} вероятно забанен!")
                try:
                    db.update_is_banned(twitter_working_account["uid"])
                except Exception as e:
                    logger.exception(f"[MAIL_VERIF] Ошибка при update_is_banned: {e}")
                return
            elif change_email_res == 'proxy_dead':
                logger.info(f"[MAIL_VERIF] У аккаунта {un} умер прокси!")
                break
            elif change_email_res == 'no_auth':
                logger.info(
                    f"[MAIL_VERIF] Аккаунт {un} вероятно нуждается в обновлении сессии!")
                try:
                    db.update_regen_session(twitter_working_account["uid"], True)
                except Exception as e:
                    logger.exception(f"[MAIL_VERIF] Ошибка при update_regen_session: {e}")
                return
            elif change_email_res == 'lock':
                logger.info(f"[MAIL_VERIF] Аккаунт {un} вероятно временно заблокирован!")
                try:
                    db.update_is_locked(twitter_working_account["uid"])
                except Exception as e:
                    logger.exception(f"[MAIL_VERIF] Ошибка при update_is_locked: {e}")
                return
            elif change_email_res in ['incorrect_pw', '48h']:
                break
            elif change_email_res:
                acc_new_data = twitter_search.get_phone_mail_data(twitter_working_account)
                if acc_new_data['emails'][0]['email'] == new_email.lower() and acc_new_data['emails'][0]['email_verified']:
                    logger.info(f"[MAIL_VERIF] @{un} успешно верефицирована новая почта {new_email}")
                    db.update_x_linked(new_email)
                    db.update_email(un, new_email, new_email_data['pass'])
                    if acc_new_data['phone_numbers'][0]['phone_number']:
                        db.update_phone(un, acc_new_data['phone_numbers'][0]['phone_number'].replace('+', ''))
                    break
                else:
                    logger.warning(f"[MAIL_VERIF] @{un} не удалось привязать новую почту!")

    def change_pw_and_save(self, acc):
        res, new_pw = twitter_search.change_password(acc)
        if res.get('status') == 'ok':
            logger.info(f'✅ Пароль аккаунта {acc["screen_name"]} успешно изменен!')
            db.update_pw(acc['uid'], new_pw)

            auth_token_update = False
            cookies = list(acc['session'].get_cookies())
            print(cookies)
            for cookie in cookies:
                print(cookie)
                if 'auth_token' in cookie.name and cookie.value != acc['auth_token']:
                    logger.debug(f'New auth token: {cookie.value}')
                    db.update_auth(acc['uid'], cookie.value)
                    acc['auth_token'] = cookie.value
                    auth_token_update = True
                    break

            if auth_token_update:
                logger.info(f'✅ Auth-token аккаунта {acc["screen_name"]} успешно изменен!')
                save_cookies_and_sess_with_timeout(acc)

            else:
                logger.error(f"❌ Ошибка при попытке обновить auth-token на аккаунте {acc['screen_name']}")

        else:
            logger.error(f"❌ Ошибка при попытке изменить пароль на аккаунте {acc['screen_name']}")

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

                    # жизнь аккаунтов
                    for x_working_acc in list(self.x_accounts_data):
                        logger.info(f"[ACC-LIFE] Работаю с аккаунтом ({x_working_acc['screen_name']}) !")

                        if x_working_acc.get('regen_sess'):
                            logger.info(f"[ACC-LIFE] Аккаунту ({x_working_acc['screen_name']}) требуется регенерация!")
                            x_working_acc = self.regenerate_acc_object(x_working_acc, new_auth=True)
                            if not x_working_acc:
                                continue
                            x_working_acc['regen_sess'] = False

                        timeline = self.get_timeline(x_working_acc)
                        if timeline in ['ban', 'lock']:
                            self.x_accounts_data.remove(x_working_acc)
                        elif timeline == 'no_auth':
                            x_working_acc["regen_sess"] = True

                        elif timeline:
                            viewed_timeline = self.view_all_tweets(timeline, x_working_acc)

                            if viewed_timeline in ['ban', 'lock']:
                                self.x_accounts_data.remove(x_working_acc)
                            elif viewed_timeline == 'no_auth':
                                x_working_acc["regen_sess"] = True
                            elif viewed_timeline:
                                res = self.random_like_timeline(viewed_timeline, x_working_acc)
                                if res in ['ban', 'lock']:
                                    self.x_accounts_data.remove(x_working_acc)
                                elif res == 'no_auth':
                                    x_working_acc["regen_sess"] = True

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

                else:
                    logger.info(f"[SLEEP] Ночь в MOSCOW ({now}), ферма отдыхает")

                pause = random.randint(1000, 3000)
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

                view_res = self.view(twitter_working_account, tid, uid)
                if view_res in ['ban', 'no_auth', 'lock']:
                    return view_res

                like_res = self.like(twitter_working_account, tid)
                if like_res in ['ban', 'no_auth', 'lock']:
                    return like_res

                if random.random() < 0.4:
                    rt_res = self.retweet(twitter_working_account, tid)
                    if rt_res in ['ban', 'no_auth', 'lock']:
                        return rt_res
                if random.random() < 0.15:
                    bm_res = self.bookmark(twitter_working_account, tid)
                    if bm_res in ['ban', 'no_auth', 'lock']:
                        return bm_res

            logger.info(f"[LIKE] Обработано твитов: {len(chosen_tweets)} для @{twitter_working_account.get('screen_name')}")
        except Exception as e:
            logger.exception(f"[LIKE] Ошибка random_like_timeline: {e}")

    def view_all_tweets(self, timeline, twitter_working_account, sleep_range=(0.2, 1.0)):
        """
        Просматривает верхнюю (первую) часть timeline — от 50% до 100% твитов.
        Порядок сохраняется.
        Возвращает:
          - 'ban' / 'no_auth' / etc -> если self.view вернул один из этих статусов
          - list[tweet_dict]   -> список твитов, которые были УСПЕШНО просмотрены
        """
        try:
            if not timeline:
                logger.info(f"[VIEW-ALL] Пустой timeline для @{twitter_working_account.get('screen_name')}")
                return []

            total = len(timeline)

            # 1) Выбираем процент просмотра (50%–100%)
            percent = random.uniform(0.50, 1.00)
            to_view = max(1, int(total * percent))

            # 2) Берём первые N твитов (без shuffle!)
            timeline_slice = timeline[:to_view]

            logger.info(
                f"[VIEW-ALL] Просмотрим первые {to_view}/{total} твитов "
                f"({percent * 100:.1f}%) для @{twitter_working_account.get('screen_name')}"
            )

            viewed = 0
            viewed_tweets = []  # сюда складываем только успешно просмотренные твиты

            for i, t in enumerate(timeline_slice, start=1):
                try:
                    tid = t["tweet"]["id"]
                    uid = t["tweet"]["user_id"]
                except KeyError:
                    logger.exception(f"[VIEW-ALL] Некорректный твит в позиции {i}: {t}")
                    continue

                try:
                    res = self.view(twitter_working_account, tid, uid)

                    if res in ("ban", "no_auth", "lock", "proxy_dead"):
                        # При бане/неавторизованности возвращаем статус как раньше
                        logger.warning(
                            f"[VIEW-ALL] @{twitter_working_account.get('screen_name')} -> {res} во время просмотра")
                        return res

                    # если ошибок нет и бана нет — считаем твит успешно просмотренным
                    viewed += 1
                    viewed_tweets.append(t)

                except Exception:
                    logger.exception(f"[VIEW-ALL] Ошибка просмотра tweetId={tid}")
                    # не добавляем твит в viewed_tweets, идём дальше

                # Throttling
                if sleep_range and sleep_range[0] >= 0:
                    time.sleep(random.uniform(*sleep_range))

            logger.info(
                f"[VIEW-ALL] Просмотрено {viewed} твитов из {to_view} "
                f"для @{twitter_working_account.get('screen_name')}"
            )

            # Возвращаем только успешно просмотренные твиты в исходном формате
            return viewed_tweets

        except Exception:
            logger.exception("[VIEW-ALL] Критическая ошибка в view_all_tweets")
            return []

    # ----------------------------
    # TWITTER ACTIONS
    # ----------------------------
    def follow(self, src, dst_uid=None, dst_screen_name=None):
        try:
            for i in range(2):
                logger.info(f"[FOLLOW] Аккаунт {src['screen_name']} выполняет подписку на {dst_uid['screen_name'] or dst_screen_name} !")
                if dst_uid:
                    res = twitter_search.user_friendship(src, "follow", user_id=dst_uid["uid"])
                    if not res:
                        raise
                elif dst_screen_name:
                    res = twitter_search.user_friendship(src, "follow", screen_name=dst_screen_name)
                    if not res:
                        raise

                if res == 'ban':
                    logger.info(f"[FOLLOW] Аккаунт {src['screen_name']} вероятно забанен!")
                    admin_error(f"[FOLLOW] Аккаунт {src['screen_name']} вероятно забанен!")
                    try:
                        db.update_is_banned_by_sn(src['screen_name'])
                    except Exception as e:
                        logger.exception(f"[SETUP] Ошибка при update_is_banned: {e}")
                    return 'ban'

                elif res == 'proxy_dead':
                    logger.info(f"[VIEW] У аккаунта {src['screen_name']} умер прокси!")
                    src = self.regenerate_acc_object(src, new_proxy=True)
                    if src:
                        continue
                elif res == 'no_auth':
                    logger.info(f"[VIEW] Аккаунт {src['screen_name']} вероятно нуждается в обновлении сессии!")
                    # admin_error(f"[VIEW] Аккаунт {x_working_acc['screen_name']} вероятно нуждается в обновлении сессии!")
                    try:
                        db.update_regen_session(src["uid"], True)
                    except Exception as e:
                        logger.exception(f"[SETUP] Ошибка при update_regen_session: {e}")
                    return 'no_auth'
                elif res == 'lock':
                    logger.info(f"[VIEW] Аккаунт {src['screen_name']} вероятно временно заблокирован!")
                    # admin_error(f"[VIEW] Аккаунт {x_working_acc['screen_name']} вероятно нуждается в обновлении сессии!")
                    try:
                        db.update_is_locked(src["uid"])
                    except Exception as e:
                        logger.exception(f"[SETUP] Ошибка при update_is_locked: {e}")
                    return 'lock'
                break

        except Exception as e:
            logger.exception(f"[FOLLOW] Ошибка follow: {e}")
            raise

    def like(self, twitter_working_account, tweet_id):
        try:
            for i in range(2):
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
                elif res == 'proxy_dead':
                    logger.info(f"[VIEW] У аккаунта {twitter_working_account['screen_name']} умер прокси!")
                    twitter_working_account = self.regenerate_acc_object(twitter_working_account, new_proxy=True)
                    if twitter_working_account:
                        continue
                elif res == 'no_auth':
                    logger.info(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно нуждается в обновлении сессии!")
                    # admin_error(f"[VIEW] Аккаунт {x_working_acc['screen_name']} вероятно нуждается в обновлении сессии!")
                    try:
                        db.update_regen_session(twitter_working_account["uid"], True)
                    except Exception as e:
                        logger.exception(f"[SETUP] Ошибка при update_regen_session: {e}")
                    return 'no_auth'
                elif res == 'lock':
                    logger.info(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно временно заблокирован!")
                    # admin_error(f"[VIEW] Аккаунт {x_working_acc['screen_name']} вероятно нуждается в обновлении сессии!")
                    try:
                        db.update_is_locked(twitter_working_account["uid"])
                    except Exception as e:
                        logger.exception(f"[SETUP] Ошибка при update_is_locked: {e}")
                    return 'lock'
                break

        except Exception as e:
            logger.exception(f"[LIKE] Ошибка like: {e}")

    def retweet(self, twitter_working_account, tweet_id):
        try:
            for i in range(2):
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
                elif res == 'proxy_dead':
                    logger.info(f"[VIEW] У аккаунта {twitter_working_account['screen_name']} умер прокси!")
                    twitter_working_account = self.regenerate_acc_object(twitter_working_account, new_proxy=True)
                    if twitter_working_account:
                        continue
                elif res == 'no_auth':
                    logger.info(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно нуждается в обновлении сессии!")
                    # admin_error(f"[VIEW] Аккаунт {x_working_acc['screen_name']} вероятно нуждается в обновлении сессии!")
                    try:
                        db.update_regen_session(twitter_working_account["uid"], True)
                    except Exception as e:
                        logger.exception(f"[SETUP] Ошибка при update_regen_session: {e}")
                    return 'no_auth'
                elif res == 'lock':
                    logger.info(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно временно заблокирован!")
                    # admin_error(f"[VIEW] Аккаунт {x_working_acc['screen_name']} вероятно нуждается в обновлении сессии!")
                    try:
                        db.update_is_locked(twitter_working_account["uid"])
                    except Exception as e:
                        logger.exception(f"[SETUP] Ошибка при update_is_locked: {e}")
                    return 'lock'
                break
        except Exception as e:
            logger.exception(f"[RT] Ошибка retweet: {e}")

    def bookmark(self, twitter_working_account, tweet_id):
        try:
            for i in range(2):
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
                elif res == 'proxy_dead':
                    logger.info(f"[VIEW] У аккаунта {twitter_working_account['screen_name']} умер прокси!")
                    twitter_working_account = self.regenerate_acc_object(twitter_working_account, new_proxy=True)
                    if twitter_working_account:
                        continue
                elif res == 'no_auth':
                    logger.info(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно нуждается в обновлении сессии!")
                    # admin_error(f"[VIEW] Аккаунт {x_working_acc['screen_name']} вероятно нуждается в обновлении сессии!")
                    try:
                        db.update_regen_session(twitter_working_account["uid"], True)
                    except Exception as e:
                        logger.exception(f"[SETUP] Ошибка при update_regen_session: {e}")
                    return 'no_auth'
                elif res == 'lock':
                    logger.info(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно временно заблокирован!")
                    # admin_error(f"[VIEW] Аккаунт {x_working_acc['screen_name']} вероятно нуждается в обновлении сессии!")
                    try:
                        db.update_is_locked(twitter_working_account["uid"])
                    except Exception as e:
                        logger.exception(f"[SETUP] Ошибка при update_is_locked: {e}")
                    return 'lock'
                break
        except Exception as e:
            logger.exception(f"[BM] Ошибка bookmark: {e}")

    def reply(self, twitter_working_account, tweet_text, tweet_id):
        try:
            for i in range(2):
                res = twitter_search.reply_tweet_by_tweet_id(twitter_working_account, tweet_text, tweet_id)
                if res == 'ban':
                    logger.info(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно забанен!")
                    admin_error(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно забанен!")
                    try:
                        db.update_is_banned(twitter_working_account["uid"])
                    except Exception as e:
                        logger.exception(f"[SETUP] Ошибка при update_is_banned: {e}")
                    return 'ban'
                elif res == 'proxy_dead':
                    logger.info(f"[VIEW] У аккаунта {twitter_working_account['screen_name']} умер прокси!")
                    twitter_working_account = self.regenerate_acc_object(twitter_working_account, new_proxy=True)
                    if twitter_working_account:
                        continue
                elif res == 'no_auth':
                    logger.info(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно нуждается в обновлении сессии!")
                    # admin_error(f"[VIEW] Аккаунт {x_working_acc['screen_name']} вероятно нуждается в обновлении сессии!")
                    try:
                        db.update_regen_session(twitter_working_account["uid"], True)
                    except Exception as e:
                        logger.exception(f"[SETUP] Ошибка при update_regen_session: {e}")
                    return 'no_auth'
                elif res == 'lock':
                    logger.info(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно временно заблокирован!")
                    # admin_error(f"[VIEW] Аккаунт {x_working_acc['screen_name']} вероятно нуждается в обновлении сессии!")
                    try:
                        db.update_is_locked(twitter_working_account["uid"])
                    except Exception as e:
                        logger.exception(f"[SETUP] Ошибка при update_is_locked: {e}")
                    return 'lock'
                break
        except Exception as e:
            logger.exception(f"[REPLY] Ошибка reply: {e}")

    def view(self, twitter_working_account, tweet_id, author_id):
        try:
            for i in range(2):
                res = twitter_search.view_tweet_by_tweet_id(twitter_working_account, tweet_id, author_id=author_id)
                if res == 'ban':
                    logger.info(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно забанен!")
                    admin_error(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно забанен!")
                    try:
                        db.update_is_banned(twitter_working_account["uid"])
                    except Exception as e:
                        logger.exception(f"[SETUP] Ошибка при update_is_banned: {e}")
                    return 'ban'
                elif res == 'proxy_dead':
                    if i == 1:
                        return 'proxy_dead'
                    logger.info(f"[VIEW] У аккаунта {twitter_working_account['screen_name']} умер прокси!")
                    twitter_working_account = self.regenerate_acc_object(twitter_working_account, new_proxy=True)
                    if twitter_working_account:
                        continue
                elif res == 'no_auth':
                    logger.info(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно нуждается в обновлении сессии!")
                    # admin_error(f"[VIEW] Аккаунт {x_working_acc['screen_name']} вероятно нуждается в обновлении сессии!")
                    try:
                        db.update_regen_session(twitter_working_account["uid"], True)
                    except Exception as e:
                        logger.exception(f"[SETUP] Ошибка при update_regen_session: {e}")
                    return 'no_auth'
                elif res == 'lock':
                    logger.info(f"[VIEW] Аккаунт {twitter_working_account['screen_name']} вероятно временно заблокирован!")
                    # admin_error(f"[VIEW] Аккаунт {x_working_acc['screen_name']} вероятно нуждается в обновлении сессии!")
                    try:
                        db.update_is_locked(twitter_working_account["uid"])
                    except Exception as e:
                        logger.exception(f"[SETUP] Ошибка при update_is_locked: {e}")
                    return 'lock'
                break
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
                if timeline == 'proxy_dead':
                    logger.info(f"[VIEW] У аккаунта {x_working_acc['screen_name']} умер прокси!")
                    x_working_acc = self.regenerate_acc_object(x_working_acc, new_proxy=True)
                    if x_working_acc:
                        continue
                elif timeline == 'ban':
                    logger.info(f"[VIEW] Аккаунт {x_working_acc['screen_name']} вероятно забанен!")
                    admin_error(f"[VIEW] Аккаунт {x_working_acc['screen_name']} вероятно забанен!")
                    try:
                        db.update_is_banned(x_working_acc["uid"])
                    except Exception as e:
                        logger.exception(f"[SETUP] Ошибка при update_is_banned: {e}")
                    return 'ban'
                elif timeline == 'no_auth':
                    logger.info(f"[VIEW] Аккаунт {x_working_acc['screen_name']} вероятно нуждается в обновлении сессии!")
                    # admin_error(f"[VIEW] Аккаунт {x_working_acc['screen_name']} вероятно нуждается в обновлении сессии!")
                    try:
                        db.update_regen_session(x_working_acc["uid"], True)
                    except Exception as e:
                        logger.exception(f"[SETUP] Ошибка при update_regen_session: {e}")
                    return 'no_auth'
                elif timeline == 'lock':
                    logger.info(f"[VIEW] Аккаунт {x_working_acc['screen_name']} вероятно временно заблокирован!")
                    # admin_error(f"[VIEW] Аккаунт {x_working_acc['screen_name']} вероятно нуждается в обновлении сессии!")
                    try:
                        db.update_is_locked(x_working_acc["uid"])
                    except Exception as e:
                        logger.exception(f"[SETUP] Ошибка при update_is_locked: {e}")
                    return 'lock'
                elif timeline:
                    return timeline
                else:
                    time.sleep(10)

        except Exception as e:
            logger.exception(f"[TIMELINE] Критическая ошибка в get_timeline: {e}")

        logger.info(x_working_acc)
        logger.warning(f'[TIMELINE] Невозможно получить timeline для аккаунта {x_working_acc["screen_name"]}!')

    def clear_acc_info_if_banned(self, acc_data, delete=False):
        if acc_data["avatar"]:
            mark_unmark_used_image(acc_data["avatar"], instruction=False)
        if acc_data["description_id"]:
            mark_unmark_used_desc(acc_data["description_id"], instruction=False)
        if delete:
            db.delete_banned_by_uid(acc_data["uid"])

    def regenerate_acc_object(self, twitter_working_account, new_proxy=False, new_auth=False):
        screen_name = twitter_working_account.get("screen_name")
        uid = twitter_working_account.get("uid")

        logger.info(f"[REGEN] Регенерирую аккаунт @{screen_name}")

        if new_auth:
            new_auth = db.get_auth_by_uid(uid)
            if new_auth != twitter_working_account['auth_token']:
                twitter_working_account['auth_token'] = new_auth
                # save_cookies_and_sess_with_timeout(outdated_session=twitter_working_account)
            else:
                logger.info(f"[REGEN] Auth-token в базе не обновлен для аккаунта {screen_name}! Возможно сбой в работе Selen-regen скрипта!")
                admin_error(f"[REGEN] Auth-token в базе не обновлен для аккаунта {screen_name}! Возможно сбой в работе Selen-regen скрипта!")
                return

        # ---- 1. Выдать новый прокси ----
        if new_proxy:
            sid = generate_valid_sid_nodemaven_proxy()
            new_proxy_value = get_proxy_by_sid(sid)
            twitter_working_account["proxy"] = new_proxy_value
            logger.info(f"[REGEN] @{screen_name} → новый прокси SID={sid}")

        # ---- 2. Обновляем сессию аккаунта ----
        result = process_account(twitter_working_account)

        if not result["account"]:
            logger.warning(f"[REGEN] @{screen_name} — не удалось обновить сессию")
            return None

        updated_acc = result["account"]

        # ---- 3. Обновляем поля в self.x_accounts_data ----
        updated = False
        for acc in self.x_accounts_data:
            if acc["uid"] == uid:  # ← идентификация по UID
                acc["session"] = updated_acc["session"]
                acc["proxy"] = updated_acc["proxy"]
                updated = True
                logger.info(f"[REGEN] @{screen_name} данные обновлены в x_accounts_data")
                break

        if not updated:
            logger.warning(f"[REGEN] @{screen_name} не найден в x_accounts_data — добавляю")
            self.x_accounts_data.append(updated_acc)

        # ---- 4. Обновление прокси в базе ----
        if new_proxy:
            try:
                db.update_proxy(sid, uid=uid)
                logger.info(f"[REGEN] @{screen_name} proxy SID обновлён в базе")
            except Exception:
                logger.exception(f"[REGEN] Ошибка update_proxy для @{screen_name}")

        return result['account']

    def accounts_health_test(self, accs):
        for acc in accs:

            cookies = acc['session'].get_cookies()
            print(type(cookies[0]), cookies[0])
            print(cookies)
            for cookie in cookies:
                print(cookie)
                if 'auth_token' in cookie.name and cookie.value != acc['auth_token']:
                    print(cookie.value)
            # print(twitter_search.change_email(acc, 'X9ZLXXTb5f', 'archivas.ai@outlook.com'))
            # print(twitter_search.get_phone_mail_data(acc))
            # self.view(acc,2003894829424824683, 44196397)
            # time.sleep(1)
            # self.like(acc, 2004307581599469917)
            # time.sleep(2)
            # self.get_timeline(acc)
            # time.sleep(2)
            # self.like(acc, 2004296606020190305)
            # time.sleep(2)
            # self.like(acc, 2004401789567742030)
            # time.sleep(2)
            # self.like(acc, 2004209430561542238)
#
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

    def change_email_safe_loop(acc_, ferma_):
        MAX_ITERATION_TIME = 120

        p = Process(
            target=ferma_.change_email_and_save,
            args=(acc_,)
        )
        p.start()
        p.join(timeout=MAX_ITERATION_TIME)

        if p.is_alive():
            p.terminate()
            p.join()
            print(f"[KILLED] change_email_and_save завис для {acc_}")
            return False

        return True

    def regen_all_sessions():
        from collections import Counter

        accs = db.get_working_accounts()
        total = len(accs)

        stats = Counter()
        ok_list = []
        fail_list = []  # (screen_name, status)

        started = datetime.now()
        print(f"🧾 Всего аккаунтов: {total}")
        print(f"🕒 Старт: {started:%Y-%m-%d %H:%M:%S}\n")

        for i, acc in enumerate(accs, 1):
            sn = acc.get("screen_name") or acc.get("username") or acc.get("login") or f"uid={acc.get('uid')}"
            try:
                res = save_cookies_and_sess_with_timeout(outdated_session=acc)
            except Exception as e:
                logger.exception(f"[REGEN_ALL] @{sn} unexpected exception")
                res = f"exception:{type(e).__name__}"

            stats[res] += 1

            if res == "ok":
                ok_list.append(sn)
                print(f"[{i}/{total}] ✅ @{sn} -> ok")
            else:
                fail_list.append((sn, res))
                print(f"[{i}/{total}] ❌ @{sn} -> {res}")

        finished = datetime.now()
        print("\n" + "=" * 80)
        print("📊 ИТОГОВАЯ СТАТИСТИКА РЕГЕНЕРАЦИИ")
        print("-" * 80)
        print(f"🧾 Всего:      {total}")
        print(f"✅ Успешно:    {stats.get('ok', 0)}")
        print(f"❌ Неудачно:   {total - stats.get('ok', 0)}")
        print(f"🕒 Старт:      {started:%Y-%m-%d %H:%M:%S}")
        print(f"🕒 Финиш:      {finished:%Y-%m-%d %H:%M:%S}")
        print(f"⏱ Длительность: {str(finished - started).split('.')[0]}")
        print("-" * 80)
        print("📌 Распределение статусов:")
        for k, v in stats.most_common():
            print(f"  • {k}: {v}")
        print("=" * 80)

        if fail_list:
            print("\n🚫 НЕУДАЧНЫЕ АККАУНТЫ (первые 50):")
            for sn, st in fail_list[:50]:
                print(f"  - @{sn}: {st}")

        return {
            "total": total,
            "stats": dict(stats),
            "ok": ok_list,
            "fail": fail_list,
            "started_at": started,
            "finished_at": finished,
        }


    print("\n🚀  Добро пожаловать в xFerma!")
    print("Выберите режим работы:")
    print("  1 — Работа фермы (work)")
    print("  2 — Настройка новых аккаунтов (set_up)")
    print("  3 — Тестовый режим (testing)")
    print("  4 — Смена пароля")
    print("  5 — Смена proxy")
    print("  6 — Смена email")
    print("  7 — Selen-regen")
    print("  8 — MFerma")
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
        print("  3 — Регенерация сессии всех аккаунтов (save_cookies_and_sess)\n")

        choice = input("👉 Введите номер режима: ").strip()
        ferma = xFerma(mode='test')

        if choice == '1':
            print("\n▶ Запуск режима проверки аккаунтов...\n")
            acc_un = input("🔹 Введите username тестового аккаунта (без @): ").strip()
            if not acc_un:
                print("❌ Вы не ввели username. Завершение работы.")
            else:
                accs = load_accounts_tweeterpy(mode='test', acc_un=acc_un)
                ferma.accounts_health_test(accs)

        elif choice == '2':
            print("\n⚙ Запуск режима регенерации сессии аккаунта...\n")
            acc_un = input("🔹 Введите username тестового аккаунта (без @): ").strip()
            if not acc_un:
                print("❌ Вы не ввели username. Завершение работы.")
            else:
                accs = db.get_working_accounts(screen_name=acc_un)
                save_cookies_and_sess_with_timeout(outdated_session=accs[0])

        elif choice == '3':
            print("\n⚙ Запуск режима регенерации сессии ВСЕХ аккаунтов...\n")
            regen_all_sessions()

    elif choice == '4':
        print("\n🔐 Режим смены пароля\n")
        print("  1 — Смена пароля только у одного аккаунта")
        print("  2 — Смена пароля у всех аккаунтов\n")

        ferma = xFerma(mode='test')

        pw_choice = input("👉 Введите номер режима смены пароля: ").strip()

        if pw_choice == '1':
            acc_un = input("🔹 Введите username аккаунта (без @): ").strip()
            if not acc_un:
                print("❌ Вы не ввели username. Завершение работы.")
            else:
                # accs = load_accounts_cookies(mode='one', acc_un=acc_un)
                accs = load_accounts_tweeterpy(mode='pw_change', acc_un=acc_un)
                ferma.change_pw_and_save(accs[0])

        elif pw_choice == '2':
            confirm = input("⚠ Ты уверен, что хочешь сменить пароли у ВСЕХ аккаунтов? (yes/no): ").strip().lower()
            if confirm == 'yes':
                accs = load_accounts_tweeterpy(mode='pw_change')
                for acc in accs:
                    ferma.change_pw_and_save(acc)
            else:
                print("❌ Операция отменена.")

        else:
            print("\n❌ Неверный выбор режима смены пароля.")

    elif choice == '5':
        print("\n▶ Запуск режима смены прокси...\n")
        acc_un = input("🔹 Enter the name of account to change proxy (without @): ").strip()
        if not acc_un:
            print("❌ Вы не ввели username. Завершение работы.")
        else:
            db.update_proxy(generate_valid_sid_nodemaven_proxy(), un=acc_un)
            time.sleep(1)
            print('ok')

    elif choice == '6':
        print("\n🔐 Режим смены email\n")
        print("  1 — Смена email только у одного аккаунта")
        print("  2 — Смена email у всех аккаунтов\n")

        ferma = xFerma(mode='test')

        pw_choice = input("👉 Введите номер режима смены email: ").strip()

        if pw_choice == '1':
            acc_un = input("🔹 Введите username аккаунта (без @): ").strip()
            if not acc_un:
                print("❌ Вы не ввели username. Завершение работы.")
            else:
                # accs = load_accounts_cookies(mode='one', acc_un=acc_un)
                accs = load_accounts_tweeterpy(mode='email_change', acc_un=acc_un)
                ferma.change_email_and_save(accs[0])

        elif pw_choice == '2':
            confirm = input("⚠ Ты уверен, что хочешь сменить email у ВСЕХ аккаунтов? (yes/no): ").strip().lower()
            if confirm == 'yes':
                accs = load_accounts_tweeterpy(mode='email_change')
                for acc in accs:
                    change_email_safe_loop(acc, ferma)
            else:
                print("❌ Операция отменена.")

        else:
            print("\n❌ Неверный выбор режима смены пароля.")

    elif choice == '7':
        print("\n♻️ Запуск web режима регенерации аккаунтов...\n")
        regen_auth()

    elif choice == '8':
        print("\n▶ Запуск MFerma...\n")
        create_new_acc()


    elif choice == '0':
        print("\n👋 Выход из программы. До встречи!")
        exit(0)

    else:
        print("\n❌ Неверный выбор. Перезапустите программу и выберите правильный режим.")