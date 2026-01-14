# cdp_header_sniffer.py
import asyncio
import json
import time
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


@dataclass
class SniffMatch:
    ts: float
    phase: str          # request | extra | response
    request_id: str
    url: Optional[str]
    method: Optional[str]
    resource_type: Optional[str]
    matched: Dict[str, str]  # watched_header -> value


class HeaderSniffer:
    """
    Collects watched headers from CDP Network events.
    Use attach(page) after network.enable().
    """
    def __init__(
        self,
        watch_headers: Set[str],
        match_url_substr: Optional[str] = None,
        only_types: Optional[Set[str]] = None,
        phases: Set[str] = frozenset({"request", "extra"}),
        out_jsonl: Optional[str] = None,
        print_all_requests: bool = False,
        on_match: Optional[Callable[[SniffMatch], None]] = None,
    ):
        self.watch = {h.lower().strip() for h in watch_headers if h and h.strip()}
        self.match_url_substr = match_url_substr.lower() if match_url_substr else None
        self.only_types = {t.lower() for t in (only_types or set())}
        self.phases = {p.lower() for p in phases}
        self.out_jsonl = out_jsonl
        self.print_all_requests = print_all_requests
        self.on_match = on_match

        self._req_meta: Dict[str, Dict[str, Any]] = {}
        self._matches: List[SniffMatch] = []
        self._fh = open(out_jsonl, "a", encoding="utf-8") if out_jsonl else None

    def close(self):
        if self._fh:
            self._fh.close()
            self._fh = None

    @property
    def matches(self) -> List[SniffMatch]:
        return self._matches

    def _type_ok(self, rtype: Optional[str]) -> bool:
        if not self.only_types:
            return True
        if not rtype:
            return False
        return rtype.lower().split('.')[-1] in self.only_types

    def _url_ok(self, url: Optional[str]) -> bool:
        if not self.match_url_substr:
            return True
        return bool(url) and self.match_url_substr in url.lower()

    def _pick(self, headers: Dict[str, str]) -> Dict[str, str]:
        if not headers:
            return {}
        found = {}
        for k in self.watch:
            if k in headers:
                found[k] = headers[k]
        return found

    def _emit(self, m: SniffMatch):
        self._matches.append(m)

        if self._fh:
            self._fh.write(json.dumps(asdict(m), ensure_ascii=False) + "\n")
            self._fh.flush()

        if self.on_match:
            try:
                self.on_match(m)
            except Exception:
                pass

    def attach(self, page, label: str = "TAB"):
        async def on_req(evt: mycdp.network.RequestWillBeSent):
            url = evt.request.url
            method = evt.request.method
            rtype = str(evt.type_)

            # store meta always
            self._req_meta[evt.request_id] = {"url": url, "method": method, "rtype": rtype}

            if self.print_all_requests:
                print(f"[{label} REQ] {method} {rtype} {url}")

            if "request" not in self.phases:
                return
            if not self._type_ok(rtype) or not self._url_ok(url):
                return

            matched = self._pick(norm_headers(evt.request.headers))
            if matched:
                self._emit(SniffMatch(
                    ts=time.time(),
                    phase="request",
                    request_id=evt.request_id,
                    url=url,
                    method=method,
                    resource_type=rtype,
                    matched=matched
                ))

        async def on_extra(evt: mycdp.network.RequestWillBeSentExtraInfo):
            if "extra" not in self.phases:
                return

            meta = self._req_meta.get(evt.request_id, {})
            url = meta.get("url")
            method = meta.get("method")
            rtype = meta.get("rtype")

            if not self._type_ok(rtype) or not self._url_ok(url):
                return

            matched = self._pick(norm_headers(evt.headers))
            if matched:
                self._emit(SniffMatch(
                    ts=time.time(),
                    phase="extra",
                    request_id=evt.request_id,
                    url=url,
                    method=method,
                    resource_type=rtype,
                    matched=matched
                ))

        async def on_resp(evt: mycdp.network.ResponseReceived):
            if "response" not in self.phases:
                return

            url = evt.response.url
            rtype = str(evt.type_)

            if not self._type_ok(rtype) or not self._url_ok(url):
                return

            self._req_meta.setdefault(evt.request_id, {}).update({"url": url, "rtype": rtype})

            matched = self._pick(norm_headers(evt.response.headers))
            if matched:
                meta = self._req_meta.get(evt.request_id, {})
                self._emit(SniffMatch(
                    ts=time.time(),
                    phase="response",
                    request_id=evt.request_id,
                    url=url,
                    method=meta.get("method"),
                    resource_type=rtype,
                    matched=matched
                ))

        page.add_handler(mycdp.network.RequestWillBeSent, on_req)
        page.add_handler(mycdp.network.RequestWillBeSentExtraInfo, on_extra)
        page.add_handler(mycdp.network.ResponseReceived, on_resp)


async def sniff_headers(
    url: str,
    watch: Union[Set[str], List[str]],
    duration: int = 30,
    proxy: Optional[str] = None,
    match_url_substr: Optional[str] = None,
    only_types: Optional[Set[str]] = None,          # {"xhr","fetch"} etc
    phases: Set[str] = frozenset({"request", "extra"}),
    out_jsonl: Optional[str] = None,
    print_all_requests: bool = False,
    on_match: Optional[Callable[[SniffMatch], None]] = None,
):
    """
    Run a CDP sniffer for `duration` seconds and return list of matches.
    Designed to be imported and called from other scripts.

    Returns:
        List[SniffMatch]
    """
    watch_set = set(watch) if not isinstance(watch, set) else watch
    watch_set = {h.lower().strip() for h in watch_set if h and h.strip()}
    if not watch_set:
        return []

    driver = await cdp_driver.cdp_util.start_async(proxy=proxy) if proxy else await cdp_driver.cdp_util.start_async()

    tab = await driver.get("about:blank")
    await tab.send(mycdp.network.enable())

    sniffer = HeaderSniffer(
        watch_headers=watch_set,
        match_url_substr=match_url_substr,
        only_types=only_types,
        phases=phases,
        out_jsonl=out_jsonl,
        print_all_requests=print_all_requests,
        on_match=on_match,
    )
    sniffer.attach(tab, "MAIN")

    # keep tab updated after navigation
    tab = await driver.get(url)
    try:
        await tab.send(mycdp.network.enable())
        sniffer.attach(tab, "NAV")
    except Exception:
        pass

    await asyncio.sleep(duration)

    matches = sniffer.matches
    sniffer.close()
    await driver.close()
    return matches


# --- Optional CLI entrypoint (only runs when executed directly) ---
def _parse_cli():
    import argparse
    p = argparse.ArgumentParser("cdp_header_sniffer.py")
    p.add_argument("--url", required=True)
    p.add_argument("--duration", type=int, default=30)
    p.add_argument("--proxy", default=None)
    p.add_argument("--watch", required=True, help="Comma-separated headers, e.g. canary,cookie")
    p.add_argument("--match", default=None, help="Only URLs containing this substring")
    p.add_argument("--only", default=None, help="Only types: xhr,fetch,document,... (comma-separated)")
    p.add_argument("--phases", default="request,extra", help="request,extra,response (comma-separated)")
    p.add_argument("--out", default=None, help="Write matches to JSONL")
    p.add_argument("--print-all", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_cli()

    only_types = None
    if args.only:
        only_types = {x.strip().lower() for x in args.only.split(",") if x.strip()}

    phases = {x.strip().lower() for x in args.phases.split(",") if x.strip()}
    phases = phases.intersection({"request", "extra", "response"}) or {"request", "extra"}

    watch = [x.strip().lower() for x in args.watch.split(",") if x.strip()]

    def _printer(m: SniffMatch):
        print(f"\n[MATCH:{m.phase}] {m.method} {m.resource_type}")
        print(f"  {m.url}")
        for k, v in m.matched.items():
            print(f"  {k}: {v}")

    res = asyncio.run(sniff_headers(
        url=args.url,
        watch=watch,
        duration=args.duration,
        proxy=args.proxy,
        match_url_substr=args.match,
        only_types=only_types,
        phases=phases,
        out_jsonl=args.out,
        print_all_requests=args.print_all,
        on_match=_printer,
    ))

    print(f"\nDone. Matches: {len(res)}")