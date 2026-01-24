import asyncio
import json
import time
import telebot
import traceback
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Set, List, Callable, Union

import mycdp
from seleniumbase.undetected import cdp_driver


def norm_headers(h: Any) -> Dict[str, str]:
    if not h:
        return {}
    try:
        items = h.items()
    except Exception:
        try:
            items = dict(h).items()
        except Exception:
            return {}
    return {str(k).lower(): str(v) for k, v in items}


def parse_payload(raw: Optional[str]) -> Dict[str, Any]:
    """
    Try to parse payload into dict (json / form / raw)
    """
    if not raw:
        return {}

    raw = raw.strip()

    # JSON
    if raw.startswith("{") and raw.endswith("}"):
        try:
            return json.loads(raw)
        except Exception:
            pass

    # form-urlencoded
    if "=" in raw and "&" in raw:
        out = {}
        for part in raw.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                out[k] = v
        return out

    # raw fallback
    return {"__raw__": raw}


@dataclass
class SniffMatch:
    ts: float
    phase: str          # request | extra | response
    request_id: str
    url: Optional[str]
    method: Optional[str]
    resource_type: Optional[str]
    matched: Dict[str, Any]


class HeaderSniffer:

    def __init__(
        self,
        watch: Set[str],
        search_mode: str = "headers",  # headers | payload
        match_url_substr: Optional[str] = None,
        only_types: Optional[Set[str]] = None,
        phases: Set[str] = frozenset({"request", "extra"}),
        out_jsonl: Optional[str] = None,
        on_match: Optional[Callable[[SniffMatch], None]] = None,
        stop_on_first: bool = False,
        debug: bool = False,
        debug_payload_limit: int = 1000
    ):
        self.watch = {w.lower() for w in watch}
        self.search_mode = search_mode
        self.match_url_substr = match_url_substr.lower() if match_url_substr else None
        self.only_types = {t.lower() for t in (only_types or set())}
        self.phases = {p.lower() for p in phases}
        self.on_match = on_match
        self.stop_on_first = stop_on_first

        self.debug = debug
        self.debug_payload_limit = debug_payload_limit

        self._req_meta: Dict[str, Dict[str, Any]] = {}
        self._matches: List[SniffMatch] = []
        self._stop_event = asyncio.Event()

        self._fh = open(out_jsonl, "a", encoding="utf-8") if out_jsonl else None

    def close(self):
        if self._fh:
            self._fh.close()

    @property
    def matches(self):
        return self._matches

    def _url_ok(self, url: Optional[str]) -> bool:
        return not self.match_url_substr or (url and self.match_url_substr in url.lower())

    def _type_ok(self, rtype: Optional[str]) -> bool:
        return not self.only_types or (rtype and rtype.lower() in self.only_types)

    def _emit(self, m: SniffMatch):
        self._matches.append(m)

        if self._fh:
            self._fh.write(json.dumps(asdict(m), ensure_ascii=False) + "\n")
            self._fh.flush()

        if self.on_match:
            self.on_match(m)

        if self.stop_on_first:
            self._stop_event.set()

    def _pick_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        return {k: headers[k] for k in self.watch if k in headers}

    def _pick_payload(self, payload: Any) -> dict:
        found = {}

        def walk(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k in self.watch:
                        found[k] = v
                    walk(v)

            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(payload)
        return found

    def attach(self, page):

        async def on_req(evt: mycdp.network.RequestWillBeSent):
            url = evt.request.url
            method = evt.request.method
            rtype = str(evt.type_).split('.')[-1]

            self._req_meta[evt.request_id] = {
                "url": url,
                "method": method,
                "rtype": rtype,
            }

            if "request" not in self.phases:
                return
            if not self._type_ok(rtype) or not self._url_ok(url):
                return

            matched = {}

            if self.search_mode == "headers":
                # 🧪 DEBUG MODE
                if self.debug:
                    debug_print_request(
                        method=method,
                        url=url,
                        headers=evt.request.headers,
                        payload=evt.request.post_data,
                        limit=self.debug_payload_limit
                    )
                headers = norm_headers(evt.request.headers)
                matched = self._pick_headers(headers)

            elif self.search_mode == "payload":
                # 🧪 DEBUG MODE
                if self.debug:
                    debug_print_request(
                        method=method,
                        url=url,
                        headers=evt.request.headers,
                        payload=evt.request.post_data,
                        limit=self.debug_payload_limit
                    )
                payload = parse_payload(evt.request.post_data)
                matched = self._pick_payload(payload)

            if matched:
                self._emit(SniffMatch(
                    ts=time.time(),
                    phase="request",
                    request_id=evt.request_id,
                    url=url,
                    method=method,
                    resource_type=rtype,
                    matched=matched,
                ))

        async def on_extra(evt: mycdp.network.RequestWillBeSentExtraInfo):
            if self.search_mode != "headers":
                return
            if "extra" not in self.phases:
                return

            if self.debug:
                debug_print_request(
                    method='EXTRA',
                    url='UNKNOWN',
                    headers=evt.headers,
                )

            meta = self._req_meta.get(evt.request_id, {})
            headers = norm_headers(evt.headers)
            matched = self._pick_headers(headers)

            if matched:
                self._emit(SniffMatch(
                    ts=time.time(),
                    phase="extra",
                    request_id=evt.request_id,
                    url=meta.get("url"),
                    method=meta.get("method"),
                    resource_type=meta.get("rtype"),
                    matched=matched,
                ))

        page.add_handler(mycdp.network.RequestWillBeSent, on_req)
        page.add_handler(mycdp.network.RequestWillBeSentExtraInfo, on_extra)

    async def wait(self, timeout: int):
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout)
        except asyncio.TimeoutError:
            pass


async def sniff_headers(
    url: str,
    watch: Union[Set[str], List[str]],
    duration: int = 30,
    proxy: Optional[str] = None,
    search_mode: str = "headers",        # 🔥 headers | payload
    match_url_substr: Optional[str] = None,
    only_types: Optional[Set[str]] = None,
    phases: Set[str] = frozenset({"request", "extra"}),
    out_jsonl: Optional[str] = None,
    on_match: Optional[Callable[[SniffMatch], None]] = None,
    stop_on_first: bool = False,
    debug: bool = False
):
    """
    Universal CDP sniffer.
    Supports:
      - header sniffing
      - payload sniffing (POST body)
    """

    watch_set = set(watch) if not isinstance(watch, set) else watch
    watch_set = {w.lower().strip() for w in watch_set if w and w.strip()}
    if not watch_set:
        return []

    # --- start chrome ---
    driver = (
        await cdp_driver.cdp_util.start_async(proxy=proxy, lang='en')
        if proxy else
        await cdp_driver.cdp_util.start_async(lang='en')
    )

    tab = await driver.get("about:blank")
    await tab.send(mycdp.network.enable())

    sniffer = HeaderSniffer(
        watch=watch_set,
        search_mode=search_mode,
        match_url_substr=match_url_substr,
        only_types=only_types,
        phases=phases,
        out_jsonl=out_jsonl,
        on_match=on_match,
        stop_on_first=stop_on_first,
        debug=debug
    )

    sniffer.attach(tab)

    # --- navigate ---
    tab = await driver.get(url)
    if 'castle_token' in watch:
        try:
            await tab.type("input[name='text']", 'elonmusk', timeout=40)
        except:
            await tab.save_screenshot('ss_test.png')
            # sb.cdp.save_screenshot('ss_test.png')
            web_audit_vip_user_message_with_photo(
                '680688412',
                'ss_test.png',
                f"❌ [CDP_SNIFFER] Ошибка ввода логина"
            )
        next_btn = await tab.find_element_by_text('Next', best_match=True)
        await next_btn.click_async()
    try:
        await tab.send(mycdp.network.enable())
        sniffer.attach(tab)
    except Exception:
        pass

    # --- wait ---
    await sniffer.wait(duration)

    matches = sniffer.matches
    sniffer.close()
    driver.quit()
    return collapse_matches(matches, watch)

def web_audit_vip_user_message_with_photo(user, path_to_photo, text):
    WebAuditBot = telebot.TeleBot('6408330846:AAFZLrHOqaTYveAlbeO8CzNdth_fTrbRGac')
    for i in range(3):
        try:
            with open(path_to_photo, 'rb') as photo:
                WebAuditBot.send_photo(user, photo=photo, caption=text, parse_mode='html')
            break
        except Exception:
            if 'PHOTO_INVALID_DIMENSIONS' in traceback.format_exc():
                time.sleep(15)

def collapse_matches(matches: list, required: set[str] | None = None) -> dict:
    result = {}
    for m in matches:
        for k, v in m.matched.items():
            result.setdefault(k, v)
        if required and required.issubset(result):
            break
    return result


def debug_print_request(
    *,
    method: str,
    url: str,
    headers: dict | None = None,
    payload: str | None = None,
    limit: int = 1000
):
    print("\n" + "=" * 80)
    print(f"[REQ] {method} {url}")

    if headers:
        print("---- HEADERS ----")
        for k, v in headers.items():
            print(f"{k}: {v}")

    if payload:
        print("---- PAYLOAD ----")
        payload = payload[:limit]
        print(payload)

    print("=" * 80)


if __name__ == '__main__':
    res = asyncio.run(sniff_headers(
        url="https://x.com/i/flow/login",
        proxy='vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-acbeddd763fd2-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080',
        watch={"castle_token"},
        search_mode="payload",
        only_types={"xhr", "fetch"},
        stop_on_first=True,
    ))