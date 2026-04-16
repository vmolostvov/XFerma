import asyncio
import json
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Set, List, Callable, Union
from urllib.parse import urlparse, parse_qs, unquote_plus

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

    # JSON object / array
    if (raw.startswith("{") and raw.endswith("}")) or (raw.startswith("[") and raw.endswith("]")):
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
                out[unquote_plus(k).lower()] = unquote_plus(v)
        return out

    # single k=v
    if "=" in raw and "&" not in raw:
        try:
            k, v = raw.split("=", 1)
            return {unquote_plus(k).lower(): unquote_plus(v)}
        except Exception:
            pass

    # raw fallback
    return {"__raw__": raw}


def parse_url_params(url: Optional[str]) -> Dict[str, Any]:
    """
    Parse query params from URL into a lowercase dict.
    Single values become strings, repeated params become lists.
    """
    if not url:
        return {}

    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query, keep_blank_values=True)
        out = {}
        for k, v in qs.items():
            key = str(k).lower()
            out[key] = v[0] if len(v) == 1 else v
        return out
    except Exception:
        return {}


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
        search_mode: str = "headers",  # headers | payload | url | all
        match_url_substr: Optional[str] = None,
        only_types: Optional[Set[str]] = None,
        phases: Set[str] = frozenset({"request", "extra"}),
        out_jsonl: Optional[str] = None,
        on_match: Optional[Callable[[SniffMatch], None]] = None,
        stop_on_first: bool = False,
        debug: bool = False,
        debug_payload_limit: int = 2000,
        required_url_params: Optional[Dict[str, Any]] = None
    ):
        self.watch = {w.lower() for w in watch}
        self.search_mode = search_mode.lower().strip()
        self.match_url_substr = match_url_substr.lower() if match_url_substr else None
        self.only_types = {t.lower() for t in (only_types or set())}
        self.phases = {p.lower() for p in phases}
        self.on_match = on_match
        self.stop_on_first = stop_on_first

        self.debug = debug
        self.debug_payload_limit = debug_payload_limit

        self.required_url_params = {
            str(k).lower(): str(v).lower()
            for k, v in (required_url_params or {}).items()
        }

        self._req_meta: Dict[str, Dict[str, Any]] = {}
        self._matches: List[SniffMatch] = []
        self._stop_event = asyncio.Event()

        self._fh = open(out_jsonl, "a", encoding="utf-8") if out_jsonl else None

        allowed_modes = {"headers", "payload", "url", "all"}
        if self.search_mode not in allowed_modes:
            raise ValueError(f"Unsupported search_mode={self.search_mode!r}. Allowed: {sorted(allowed_modes)}")

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

    def _pick_nested_keys(self, payload: Any) -> Dict[str, Any]:
        found = {}

        def walk(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    key_l = str(k).lower()
                    if key_l in self.watch and key_l not in found:
                        found[key_l] = v
                    walk(v)

            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(payload)
        return found

    def _collect_matches(
        self,
        *,
        url: Optional[str],
        headers_raw: Any,
        payload_raw: Optional[str]
    ) -> Dict[str, Any]:
        """
        Collect watched keys according to search_mode.
        In `all` mode, later sources do not overwrite earlier found values.
        Priority:
          headers -> payload -> url
        """
        matched: Dict[str, Any] = {}

        if self.search_mode in {"headers", "all"}:
            headers = norm_headers(headers_raw)
            for k, v in self._pick_headers(headers).items():
                matched.setdefault(k, v)

        if self.search_mode in {"payload", "all"}:
            payload = parse_payload(payload_raw)
            for k, v in self._pick_nested_keys(payload).items():
                matched.setdefault(k, v)

        if self.search_mode in {"url", "all"}:
            url_params = parse_url_params(url)
            for k, v in self._pick_nested_keys(url_params).items():
                matched.setdefault(k, v)

        return matched

    def attach(self, page):

        async def on_req(evt: mycdp.network.RequestWillBeSent):
            url = evt.request.url
            method = evt.request.method
            rtype = str(evt.type_).split('.')[-1].lower()

            self._req_meta[evt.request_id] = {
                "url": url,
                "method": method,
                "rtype": rtype,
            }

            if self.debug:
                debug_print_request(
                    method=method,
                    url=url,
                    headers=evt.request.headers,
                    payload=evt.request.post_data,
                    limit=self.debug_payload_limit
                )

            if "request" not in self.phases:
                return
            if not self._type_ok(rtype) or not self._url_ok(url):
                return
            if not self._url_params_match(url):
                return

            matched = self._collect_matches(
                url=url,
                headers_raw=evt.request.headers,
                payload_raw=evt.request.post_data
            )

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
            if self.search_mode not in {"headers", "all"}:
                return
            if "extra" not in self.phases:
                return

            meta = self._req_meta.get(evt.request_id, {})

            if self.debug:
                debug_print_request(
                    method="EXTRA",
                    url=meta.get("url") or "UNKNOWN",
                    headers=evt.headers,
                )

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

    def _url_params_match(self, url: Optional[str]) -> bool:
        if not self.required_url_params:
            return True

        params = parse_url_params(url)

        for k, expected in self.required_url_params.items():
            if k not in params:
                return False

            value = params[k]

            if isinstance(value, list):
                values = [str(x).lower() for x in value]
                if expected not in values:
                    return False
            else:
                if str(value).lower() != expected:
                    return False

        return True

    async def wait(self, timeout: int):
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout)
        except asyncio.TimeoutError:
            pass


async def sniff_headers(
    url: str,
    watch: Union[Set[str], List[str]],
    duration: int = 300,
    proxy: Optional[str] = None,
    search_mode: str = "headers",        # headers | payload | url | all
    match_url_substr: Optional[str] = None,
    required_url_params: Optional[Dict[str, Any]] = None,
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
      - url query param sniffing
      - all at once
    """

    watch_set = set(watch) if not isinstance(watch, set) else watch
    watch_set = {w.lower().strip() for w in watch_set if w and w.strip()}
    if not watch_set:
        return {}

    driver = (
        await cdp_driver.cdp_util.start_async(proxy=proxy)
        if proxy else
        await cdp_driver.cdp_util.start_async()
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
        debug=debug,
        required_url_params=required_url_params
    )

    sniffer.attach(tab)

    tab = await driver.get(url)

    try:
        await tab.send(mycdp.network.enable())
        sniffer.attach(tab)
    except Exception:
        pass

    await sniffer.wait(duration)

    matches = sniffer.matches
    sniffer.close()
    driver.quit()
    return collapse_matches(matches, watch_set)


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
        if len(payload) > limit:
            print(payload[:limit] + f"\n... [truncated {len(payload) - limit} chars]")
        else:
            print(payload)

    print("=" * 80)


if __name__ == '__main__':
    res = asyncio.run(sniff_headers(
        url="https://dexscreener.com/solana/fpyosqzp5ijfrxqqbvnm67rfam7vsbvnam7puf8yvt1c",
        proxy='vmolostvov96_gmail_com-country-us-type-mobile-ipv4-true-sid-ba0ce33d7cdc1-filter-medium:e3ibl6cpq4@gate.nodemaven.com:8080',
        watch={"type", "rid", "sid"},
        search_mode="url",
        required_url_params={"type": "terminate"},
        only_types={"xhr", "fetch", "ping"},
        stop_on_first=True,
        debug=True
    ))
    print(res)