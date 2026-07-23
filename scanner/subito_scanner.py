import json
import re
import time
from datetime import datetime
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests
from scanner.base import BaseScanner, Product

RETRY_DELAYS = [2, 5, 10]

class SubitoScanner(BaseScanner):
    def __init__(self, config, global_config):
        super().__init__(config, global_config)
        self.max_pages = config.get("max_pages", 3)
        self._search_in_desc = True
        self._required_keywords = []
        self.session = None

    def run(self):
        if not self.enabled:
            return [], []
        
        self.session = self._make_session()
        try:
            all_matched = []
            all_near_miss = []
            seen_urls = set()
            source_key = self.config.get("source_key", self.name.lower())
            for product in self.products:
                enabled = product.get(source_key, True)
                if not enabled:
                    continue
                max_price = product.get("max_price", 500)
                keywords = product.get("keywords", [])
                exclude_kw = product.get("exclude_keywords", [])
                self._search_in_desc = product.get("search_in_description", True)
                self._required_keywords = product.get("required_keywords", [])
                for keyword in keywords:
                    margin = product.get("price_margin", 50)
                    pe = max_price + margin
                    results = self.search(keyword, pe=pe)
                    results = [r for r in results if not self._excluded_by_keywords(r, exclude_kw)]
                    matched, near = self.classify_results(results, max_price, margin)
                    for p in matched:
                        p.product_name = product.get("name", keyword)
                    for p in near:
                        p.product_name = product.get("name", keyword)
                        p.near_miss = True
                    for lst in (matched, near):
                        deduped = []
                        for p in lst:
                            if p.url not in seen_urls:
                                seen_urls.add(p.url)
                                deduped.append(p)
                        lst.clear()
                        lst.extend(deduped)
                    all_matched.extend(matched)
                    all_near_miss.extend(near)
                # Fetch manually specified item URLs (not in search)
                urls = product.get("subito_urls", [])
                for url in urls:
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    item = self._fetch_item_by_url(url)
                    if not item:
                        continue
                    item.product_name = product.get("name", "")
                    margin = product.get("price_margin", 50)
                    matched, near = self.classify_results([item], max_price, margin)
                    for p in matched:
                        p.product_name = product.get("name", "")
                    all_matched.extend(matched)
                    all_near_miss.extend(near)
                    time.sleep(1)
            return all_matched, all_near_miss
        finally:
            try:
                self.session.close()
            except:
                pass
            self.session = None

    def _build_search_url(self, keyword, ps=None, pe=None):
        url = self.config["search_url"].format(keyword=keyword)
        params = []
        if ps is not None:
            params.append(f"ps={ps}")
        if pe is not None:
            params.append(f"pe={pe}")
        if params:
            url = f"{url}&{'&'.join(params)}"
        return url

    def search(self, keyword, ps=None, pe=None):
        results = []
        seen_urns = set()
        for page in range(1, self.max_pages + 1):
            url = self._build_search_url(keyword, ps=ps, pe=pe)
            if page > 1:
                url = f"{url}&page={page}"
            try:
                items = self._fetch_page(url)
                for item in items:
                    urn = item.get("urn", "")
                    if urn in seen_urns:
                        continue
                    seen_urns.add(urn)
                    product = self._parse_item(item, keyword)
                    if product:
                        results.append(product)
            except Exception as e:
                print(f"  [ERROR] Subito page {page}: {e}")
            time.sleep(1.5)
        return results

    def _make_session(self):
        s = curl_requests.Session()
        s.curl.setopt(78, 15)
        s.curl_options[78] = 15
        s.curl.setopt(75, 15)
        s.curl_options[75] = 15
        # Disabilita thread DNS asincroni libcurl su Windows che causano getaddrinfo thread failed
        s.curl.setopt(99, 1)
        s.curl_options[99] = 1
        return s

    def _fetch_page(self, url):
        client = self.session if self.session else curl_requests.Session()
        for attempt, delay in enumerate(RETRY_DELAYS):
            try:
                resp = client.get(url, impersonate="chrome", timeout=25)
                if resp.status_code != 200:
                    print(f"  [WARN] Subito status {resp.status_code}")
                    return []
                m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
                if not m:
                    soup = BeautifulSoup(resp.text, "lxml")
                    items = []
                    for card in soup.select("article[data-testid='listing-card'], [class*='item-card'], .items__item"):
                        items.append({"__html": str(card)})
                    return items
                data = json.loads(m.group(1))
                return (data.get("props", {}).get("pageProps", {}).get("initialState", {}).get("items", {}).get("originalList", []))
            except Exception as e:
                err_str = str(e)
                if "getaddrinfo" in err_str or "thread failed" in err_str:
                    print(f"  [WARN] Subito DNS error (attempt {attempt + 1}/{len(RETRY_DELAYS)}), riprovo tra {delay}s: {e}")
                    time.sleep(delay)
                else:
                    print(f"  [WARN] Subito request failed: {e}")
                    return []
        print(f"  [ERROR] Subito page fallito dopo {len(RETRY_DELAYS)} tentativi")
        return []

    def _fetch_item_by_url(self, url):
        item_id = ""
        m = re.search(r"/vi/(\d+)", url)
        if m:
            item_id = m.group(1)
        for attempt, delay in enumerate(RETRY_DELAYS):
            try:
                resp = self.session.get(url, impersonate="chrome", timeout=25)
                if resp.status_code != 200:
                    print(f"  [WARN] Subito item page {url}: HTTP {resp.status_code}")
                    return None
                all_text = ""
                for chunk_m in re.finditer(r'self\.__next_f\.push\(\[[^,]*,\s*"(.*?)"\]\)', resp.text):
                    raw = chunk_m.group(1)
                    try:
                        all_text += json.loads('"' + raw + '"')
                    except:
                        pass
                if not all_text:
                    print(f"  [WARN] Subito item {item_id}: no RSC data found")
                    return None
                title = ""
                tm = re.search(r'"subject"\s*:\s*"([^"]+)"', all_text)
                if tm:
                    title = tm.group(1)
                if not title:
                    print(f"  [WARN] Subito item {item_id}: no title found")
                    return None
                price = None
                pm = re.search(r'"/price"[^}]*?"key"\s*:\s*"(\d+)"', all_text)
                if pm:
                    price = self._parse_price(pm.group(1))
                if not price:
                    pm2 = re.search(r'"price"\s*:\s*(\d+)', all_text)
                    if pm2:
                        price = self._parse_price(pm2.group(1))
                shipping = False
                sm = re.search(r'"/item_shippable"[^}]*?"key"\s*:\s*"(\d+)"', all_text)
                if sm and sm.group(1) == "1":
                    shipping = True
                location = ""
                town_m = re.search(r'"town"[^}]*?"value"\s*:\s*"([^"]+)"', all_text)
                city_m = re.search(r'"city"[^}]*?"value"\s*:\s*"([^"]+)"', all_text)
                if town_m or city_m:
                    town = town_m.group(1) if town_m else ""
                    city = city_m.group(1) if city_m else ""
                    location = f"{town} ({city})" if city else town
                if not location:
                    loc_m = re.search(r'"url"[^:]*:\s*"([^"]*-latina-[^"]*)"', all_text)
                    if loc_m:
                        location = "Latina"
                return Product(
                    title=title.strip(), price=price, url=url, source="Subito.it",
                    location=location or "Italia", shipping=shipping, condition="usato"
                )
            except Exception as e:
                err = str(e)
                if "getaddrinfo" in err or "thread failed" in err:
                    print(f"  [WARN] Subito item {item_id} DNS error (tentativo {attempt + 1}/{len(RETRY_DELAYS)}), riprovo tra {delay}s")
                    time.sleep(delay)
                else:
                    print(f"  [WARN] Subito item {item_id} error: {e}")
                    return None
        return None

    def _parse_item(self, raw, keyword):
        if "__html" in raw:
            return self._parse_fallback_html(raw["__html"], keyword)
        try:
            title = raw.get("subject", "") or ""
            body = raw.get("body", "") or ""
            combined = f"{title} {body}" if self._search_in_desc else title
            if not self._matches_keyword(combined, keyword):
                return None
            urn = raw.get("urn", "")
            urls = raw.get("urls", {}) or {}
            link = urls.get("default", "")
            if not link and urn:
                link = f"https://www.subito.it/annunci/{urn}"
            features = raw.get("features", {}) or {}
            price_raw = None
            pf = features.get("/price", {}) or {}
            if pf.get("values"):
                price_raw = pf["values"][0].get("key")
            price = self._parse_price(price_raw)
            shipping = False
            sf = features.get("/item_shippable", {}) or {}
            if sf.get("values"):
                sk = sf["values"][0].get("key", "0")
                shipping = sk == "1"
            elif sf.get("value"):
                shipping = sf["value"] in ("yes", "true", "si", "1")
            geo = raw.get("geo", {}) or {}
            town = geo.get("town", "")
            if isinstance(town, dict):
                town = town.get("value", "")
            city = geo.get("city", "")
            if isinstance(city, dict):
                city = city.get("shortName", "")
            location = f"{town} ({city})" if city else town
            is_sold = raw.get("sold", False)
            if is_sold:
                return None
            return Product(
                title=title.strip(), price=price, url=link, source="Subito.it",
                location=location, shipping=shipping, condition="usato"
            )
        except Exception:
            return None

    def _parse_fallback_html(self, html, keyword):
        soup = BeautifulSoup(html, "lxml")
        try:
            title_el = soup.select_one("h2, [class*=title], [data-testid='title']")
            title = title_el.get_text(strip=True) if title_el else ""
            if self._search_in_desc:
                desc_el = soup.select_one("[class*=description], [class*=body], p, [data-testid*=description]")
                desc = desc_el.get_text(strip=True) if desc_el else ""
                combined = f"{title} {desc}"
            else:
                combined = title
            if not self._matches_keyword(combined, keyword):
                return None
            link_el = soup.select_one("a[href]")
            href = link_el["href"] if link_el else ""
            link = href if href.startswith("http") else f"https://www.subito.it{href}"
            price_el = soup.select_one("[class*=price], [data-testid*=price], .price")
            price = self._parse_price(price_el.get_text(strip=True) if price_el else "")
            ship_el = soup.select_one("[class*=shipping], [data-testid*=shipping], [class*=ship]")
            shipping = bool(ship_el and "spedizion" in ship_el.get_text(strip=True).lower())
            loc_el = soup.select_one("[class*=location], [class*=town], [class*=city]")
            location = loc_el.get_text(strip=True) if loc_el else "Italia"
            return Product(
                title=title, price=price, url=link, source="Subito.it",
                location=location, shipping=shipping, condition="usato"
            )
        except Exception:
            return None

    def _matches_keyword(self, title, keyword):
        t = title.lower()
        k = keyword.lower()
        if not all(word in t for word in k.split()):
            return False
        for rk in self._required_keywords:
            if rk.lower() not in t:
                return False
        return True

    def _excluded_by_keywords(self, product, exclude_keywords):
        if not exclude_keywords:
            return False
        t = f"{product.title} {product.product_name}".lower()
        return any(word.strip().lower() in t for word in exclude_keywords)

    def _parse_price(self, raw):
        if not raw:
            return None
        if isinstance(raw, (int, float)):
            return int(raw)
        cleaned = re.sub(r"[^\d,]", "", str(raw)).replace(",", ".")
        try:
            return int(float(cleaned))
        except (ValueError, TypeError):
            return None
