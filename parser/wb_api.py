import json
import logging
import os
import re
import time
from html import unescape
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger("parser.wb_api")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    logger.addHandler(h)
logger.setLevel(logging.INFO)

class WBApiParser:
    SEARCH_URLS = [
        "https://search.wb.ru/exactmatch/ru/common/v5/search",
        "https://search.wb.ru/exactmatch/ru/common/v4/search",
    ]
    DETAIL_URLS = [
        "https://card.wb.ru/cards/v2/detail",
        "https://card.wb.ru/cards/v1/detail",
        "https://card.wb.ru/cards/detail",
    ]
    SEARCH_HTML_URL = "https://www.wildberries.ru/catalog/0/search.aspx"

    def __init__(self, ua_path: Optional[str] = None, cookies_path: Optional[str] = None, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.user_agent = self._load_user_agent(ua_path)
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru,en;q=0.9",
            "Connection": "keep-alive",
        })

        if cookies_path is None:
            here = os.path.dirname(__file__)
            guess = os.path.abspath(os.path.join(here, "..", "cookies.json"))
            cookies_path = guess if os.path.exists(guess) else None
        if cookies_path and os.path.exists(cookies_path):
            self._load_cookies(cookies_path)

        self.xinfo_raw: Optional[str] = None
        address = os.getenv("WB_ADDRESS", "Москва")
        self.geo = self._get_geo_info_via_xinfo(address)  

        self.enable_html_meta = bool(int(os.getenv("WB_HTML_META", "1")))

        self.html_headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru,en;q=0.9",
            "Connection": "keep-alive",
            "Referer": "https://www.wildberries.ru/",
        }

        if self.xinfo_raw:
            self.html_headers["X-Info"] = self.xinfo_raw
            self.session.headers["X-Info"] = self.xinfo_raw

    def parse(self, query: str, max_products: Optional[int] = None, max_pages: Optional[int] = None) -> List[Dict]:
        """
        max_products=None  -> собрать вообще все товары (до окончания страниц или max_pages)
        max_pages=None     -> без ограничения по страницам (пока не кончатся товары)
        Можно совмещать: например max_products=2000 и max_pages=50.
        """
        items = self._search(query, limit=max_products, max_pages=max_pages)
        logger.info("search returned %d items for query='%s'", len(items), query)
        if not items:
            return []

        ids = [it["id"] for it in items if it.get("id")]
        id2stock, id2price = self._detail_info(ids)

        html_meta: Dict[int, Dict[str, Any]] = {}
        if self.enable_html_meta:
            html_meta = self._collect_html_meta_for_ids(query, ids, per_page=100, max_pages=max_pages or 50)

        out: List[Dict] = []
        for it in items:
            pid = int(it.get("id", 0) or 0)
            name = (it.get("name") or "").strip()
            brand = it.get("brand") or it.get("brandName")

            raw_rating = it.get("reviewRating")
            if raw_rating is None:
                raw_rating = it.get("rating")
            if raw_rating is None:
                raw_rating = it.get("supplierRating")
            try:
                rating = float(raw_rating or 0.0)
                if rating > 5:
                    rating = rating / 10.0
                rating = round(rating, 1)
            except Exception:
                rating = 0.0

            review_count = int(it.get("feedbacks") or it.get("feedbackCount") or 0)

            price_u = it.get("promoPriceU") or it.get("salePriceU") or it.get("priceU") or 0
            price_api = (price_u or 0) // 100

            if pid in id2price:
                price_api = min(price_api, id2price[pid]) if price_api else id2price[pid]

            meta = html_meta.get(pid, {})
            wallet_price = meta.get("wallet_price")
            idx = meta.get("index")
            page = meta.get("page")

            price_final = wallet_price if isinstance(wallet_price, int) and wallet_price > 0 else price_api

            out.append({
                "nm_id": pid,
                "name": name,
                "brand": brand,
                "price_api": int(price_api or 0),
                "price_wallet": int(wallet_price) if wallet_price is not None else None,
                "price_final": int(price_final or 0),
                "rating": rating,
                "review_count": review_count,
                "stock": int(id2stock.get(pid, 0)),
                "data_card_index": idx if isinstance(idx, int) else None,
                "page": int(page) if isinstance(page, int) else None,
            })

        out.sort(key=lambda x: (
            x["page"] is None, x["page"] if x["page"] is not None else 10**9,
            x["data_card_index"] is None, x["data_card_index"] if x["data_card_index"] is not None else 10**9
        ))
        return out

    def _load_user_agent(self, ua_path: Optional[str]) -> str:
        default = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        if not ua_path or not os.path.exists(ua_path):
            return default
        try:
            with open(ua_path, "r", encoding="utf-8") as f:
                lines = [ln.strip() for ln in f if ln.strip()]
            if lines:
                logger.info("UA loaded from ua.txt")
                return lines[0]
        except Exception as e:
            logger.warning("UA load failed: %s", e)
        return default

    def _load_cookies(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data = [data]
            cnt = 0
            for c in data:
                if "wildberries.ru" not in (c.get("domain") or ""):
                    continue
                name = c.get("name")
                value = c.get("value")
                if not name or value is None:
                    continue
                cookie = requests.cookies.create_cookie(
                    name=name,
                    value=str(value),
                    domain=c.get("domain") or ".wildberries.ru",
                    path=c.get("path", "/"),
                    secure=bool(c.get("secure", False)),
                )
                self.session.cookies.set_cookie(cookie)
                cnt += 1
            logger.info("Загружены cookies: %d шт из %s", cnt, path)
        except Exception as e:
            logger.warning("Не удалось загрузить cookies из %s: %s", path, e)

    def _get_geo_info_via_xinfo(self, address: str = "Москва") -> Dict[str, Any]:
        url = "https://user-geo-data.wildberries.ru/get-geo-info"
        try:
            r = self.session.get(url, params={"address": address}, timeout=self.timeout)
            r.raise_for_status()
            data = r.json() or {}
            xinfo = data.get("xinfo", "") or ""
            self.xinfo_raw = xinfo or None

            geo: Dict[str, Any] = {}
            for part in xinfo.split("&"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    if v != "":
                        geo[k] = int(v) if v.lstrip("-").isdigit() else v
            if "dest" not in geo:
                geo["dest"] = -1257786
            if "spp" not in geo:
                geo["spp"] = 0
            return geo
        except Exception as e:
            logger.warning("Не удалось получить geo-info via xinfo: %s", e)
            return {"dest": -1257786, "spp": 0}

    def _search(self, query: str, limit: Optional[int], max_pages: Optional[int]) -> List[Dict]:
        """
        Идём постранично, пока:
          - не кончатся товары,
          - не достигнем max_pages (если задан),
          - не наберём limit (если задан).
        """
        all_items: List[Dict] = []
        seen_ids: set[int] = set()
        page = 1

        if limit is None or limit > 300:
            per_page = 300
        else:
            per_page = min(max(10, limit), 300)

        while True:
            if max_pages is not None and page > max_pages:
                break

            got = None
            last_err = None
            for url in self.SEARCH_URLS:
                params = {
                    "resultset": "catalog",
                    "page": page,
                    "limit": per_page,
                    "query": query,
                    "sort": "popular",
                    "appType": 1,
                    "curr": "rub",
                    "locale": "ru",
                    **{k: v for k, v in self.geo.items() if isinstance(v, (str, int))},
                }
                try:
                    r = self.session.get(url, params=params, timeout=self.timeout)
                    r.raise_for_status()
                    data = r.json() or {}
                    products = (data.get("data") or {}).get("products") or []
                    if products:
                        got = products
                        break
                except Exception as e:
                    last_err = e
                    continue

            if not got:
                logger.info("Страниц больше нет (page=%d, last_err=%s).", page, str(last_err))
                break

            for p in got:
                pid = p.get("id")
                if isinstance(pid, int) and pid not in seen_ids:
                    seen_ids.add(pid)
                    all_items.append(p)
                    if limit is not None and len(all_items) >= limit:
                        return all_items

            if len(got) < per_page:
                break

            page += 1
            time.sleep(0.25)  
        return all_items

    def _detail_info(self, ids: List[int]) -> Tuple[Dict[int, int], Dict[int, int]]:
        id2stock: Dict[int, int] = {}
        id2price: Dict[int, int] = {}
        if not ids:
            return id2stock, id2price

        for i in range(0, len(ids), 100):
            batch = ids[i:i + 100]
            base_params = {
                "appType": 1,
                "curr": "rub",
                "nm": ";".join(map(str, batch)),
                **{k: v for k, v in self.geo.items() if isinstance(v, (str, int))},
            }
            success = False
            for url in self.DETAIL_URLS:
                params = dict(base_params)
                if url.endswith("/cards/detail"):
                    params.update({"reg": 0, "emp": 0, "locale": "ru", "lang": "ru", "pricemarginCoeff": 1.0})
                for attempt in range(3):
                    try:
                        r = self.session.get(url, params=params, timeout=self.timeout)
                        if r.status_code in (429, 503):
                            time.sleep(0.5 * (attempt + 1))
                            continue
                        r.raise_for_status()
                        data = r.json() or {}
                        d = data.get("data")
                        if isinstance(d, dict):
                            products = d.get("products") or []
                        elif isinstance(d, list):
                            products = d
                        else:
                            products = []
                        for p in products:
                            pid = p.get("id")
                            total_stock = 0
                            price_candidates_u: List[int] = []

                            for key in ("promoPriceU", "salePriceU", "priceU"):
                                v = p.get(key)
                                if isinstance(v, int) and v > 0:
                                    price_candidates_u.append(v)

                            for size in (p.get("sizes") or []):
                                for st in (size.get("stocks") or []):
                                    qty = st.get("qty")
                                    if isinstance(qty, int):
                                        total_stock += qty
                                po = size.get("price") or {}
                                for k in ("product", "basic", "total"):
                                    v = po.get(k)
                                    if isinstance(v, int) and v > 0:
                                        price_candidates_u.append(v)

                            if pid:
                                id2stock[pid] = total_stock
                                if price_candidates_u:
                                    id2price[pid] = min(price_candidates_u) // 100
                        logger.info("stocks/price batch ok via %s (%d ids)", url, len(batch))
                        success = True
                        break
                    except requests.HTTPError as e:
                        logger.warning("Ошибка detail для партии %s на %s: %s", batch, url, e)
                        time.sleep(0.4 * (attempt + 1))
                    except Exception as e:
                        logger.warning("Сбой detail для партии %s на %s: %s", batch, url, e)
                        time.sleep(0.4 * (attempt + 1))
                if success:
                    break
            if not success:
                logger.warning("Не удалось получить detail ни по одному URL для партии %s", batch)
            time.sleep(0.2)
        return id2stock, id2price

    def _collect_html_meta_for_ids(self, query: str, target_ids: List[int], per_page: int = 100, max_pages: int = 50) -> Dict[int, Dict[str, Any]]:
        needed = set(int(x) for x in target_ids)
        if not needed:
            return {}

        result: Dict[int, Dict[str, Any]] = {}
        page = 1
        while needed and page <= max_pages:
            params = {"search": query, "page": page}
            try:
                r = self.session.get(
                    self.SEARCH_HTML_URL,
                    params=params,
                    timeout=self.timeout,
                    headers=self.html_headers,
                )
                if r.status_code in (429, 498, 503):
                    time.sleep(0.4)
                    r = self.session.get(
                        self.SEARCH_HTML_URL,
                        params=params,
                        timeout=self.timeout,
                        headers=self.html_headers,
                    )
                r.raise_for_status()
            except Exception as e:
                logger.warning("HTML page %d fetch failed: %s", page, e)
                break

            cards = self._extract_cards_from_html(r.text)
            for nm_id, meta in cards.items():
                if nm_id in needed:
                    meta["page"] = page
                    result[nm_id] = meta
                    needed.discard(nm_id)

            if not cards:

                break

            page += 1
            time.sleep(0.15)

        return result

    def _extract_cards_from_html(self, html: str) -> Dict[int, Dict[str, Any]]:
        """
        Достаём nm_id, data-card-index (из атрибутов <article ...>)
        и wallet_price (из блока цены). Если верстка другая —
        дольём данные из window.__WBSTATE__.
        """
        out: Dict[int, Dict[str, Any]] = {}

        article_re = re.compile(
            r'<article\b([^>]*)>(.*?)</article>',
            flags=re.S | re.I
        )

        for m in article_re.finditer(html):
            attrs_str = m.group(1) or ""
            block = m.group(2) or ""

            nm_id = None
            for pat in (
                r'(?:\s|^)data-nm-id\s*=\s*"(\d+)"',
                r'(?:\s|^)data-id\s*=\s*"(\d+)"',
                r'(?:\s|^)id\s*=\s*"c(\d+)"',
            ):
                mi = re.search(pat, attrs_str, flags=re.I)
                if mi:
                    try:
                        nm_id = int(mi.group(1))
                        break
                    except Exception:
                        pass
            if not nm_id:
                continue

            idx = None
            for pat in (
                r'(?:\s|^)data-card-index\s*=\s*"(\d+)"',
                r'(?:\s|^)data-card-idx\s*=\s*"(\d+)"',
                r'(?:\s|^)data-index\s*=\s*"(\d+)"',
            ):
                mi = re.search(pat, attrs_str, flags=re.I)
                if mi:
                    try:
                        idx = int(mi.group(1))
                        break
                    except Exception:
                        pass

            price = None
            m_price = re.search(
                r'<(?:ins|span)\b[^>]*class="[^"]*price__lower-price[^"]*"[^>]*>([\s\S]*?)</(?:ins|span)>',
                block, flags=re.I
            )
            if not m_price:
                m_price = re.search(
                    r'class="[^"]*price[^"]*"[\s\S]*?>([\s\S]*?)(?:₽|руб)',
                    block, flags=re.I
                )
            if m_price:
                raw = unescape(m_price.group(1))
                raw_digits = re.sub(r'[^\d]', '', raw)
                if raw_digits.isdigit():
                    try:
                        price = int(raw_digits)
                    except Exception:
                        price = None

            out[nm_id] = {"wallet_price": price, "index": idx}

        if not out or any(v.get("wallet_price") is None and v.get("index") is None for v in out.values()):
            from_state = self._extract_from_wbstate(html)
            for nid, meta in from_state.items():
                if nid not in out:
                    out[nid] = meta
                else:
                    if out[nid].get("wallet_price") is None and meta.get("wallet_price") is not None:
                        out[nid]["wallet_price"] = meta["wallet_price"]
                    if out[nid].get("index") is None and meta.get("index") is not None:
                        out[nid]["index"] = meta["index"]

        return out

    def _extract_from_wbstate(self, html: str) -> Dict[int, Dict[str, Any]]:
        """
        Разбираем window.__WBSTATE__ и вытаскиваем:
          - wallet_price (мин. из promo/sale/basic/total/priceU, делённый на 100)
          - index (если встречается поблизости)
        WBSTATE часто не чистый JSON — используем регэкспы.
        """
        out: Dict[int, Dict[str, Any]] = {}
        m = re.search(r"window\.__WBSTATE__\s*=\s*(\{[\s\S]*?\})\s*;<", html, flags=re.I)
        if not m:
            return out
        raw = m.group(1)

        for hit in re.finditer(
            r'(?:"nm"|\"id\")\s*:\s*(\d+)[\s\S]*?(?:"promoPriceU"|"salePriceU"|"priceU"|"basic"|"total")\s*:\s*(\d+)',
            raw, flags=re.I
        ):
            try:
                nm_id = int(hit.group(1))
                price_u = int(hit.group(2))
                price = price_u // 100 if price_u > 0 else None

                window = raw[hit.start():hit.end()]
                mi = re.search(r'"index"\s*:\s*(\d+)', window)
                idx = int(mi.group(1)) if mi else None

                if nm_id in out:
                    a = out[nm_id].get("wallet_price")
                    out[nm_id]["wallet_price"] = (
                        min(x for x in (a, price) if isinstance(x, int))
                        if isinstance(a, int) and isinstance(price, int)
                        else (price or a)
                    )
                    if out[nm_id].get("index") is None and idx is not None:
                        out[nm_id]["index"] = idx
                else:
                    out[nm_id] = {"wallet_price": price, "index": idx}
            except Exception:
                continue

        return out