import re
import time
from datetime import datetime
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests
from scanner.base import BaseScanner, Product

RETRY_DELAYS = [3, 8, 15]

class AmazonScanner(BaseScanner):
    def __init__(self, config, global_config):
        super().__init__(config, global_config)
        self.all_asins = []

    def _make_session(self):
        s = curl_requests.Session()
        s.curl.setopt(78, 15)
        s.curl_options[78] = 15
        s.curl.setopt(64, 0)
        s.curl_options[64] = 0
        s.curl.setopt(75, 20)
        s.curl_options[75] = 20
        s.curl.setopt(113, 1)
        s.curl_options[113] = 1
        s.curl.setopt(92, 0)
        s.curl_options[92] = 0
        s.curl.setopt(99, 1)
        s.curl_options[99] = 1
        return s

    def run(self):
        if not self.enabled:
            return [], []

        self.all_asins = []
        try:
            all_matched = []
            all_near_miss = []
            source_key = self.config.get("source_key", self.name.lower())
            for product in self.products:
                enabled = product.get(source_key, True)
                if not enabled:
                    continue
                max_price = product.get("max_price", 500)
                margin = product.get("price_margin", 50)
                
                # 1. Ricerca per keywords
                keywords = product.get("keywords", [])
                exclude_kw = product.get("exclude_keywords", [])
                for keyword in keywords:
                    results = self.search(keyword)
                    filtered = [p for p in results if not any(w.lower() in f"{p.title} {product.get('name','')}".lower() for w in exclude_kw)]
                    matched, near = self.classify_results(filtered, max_price, margin)
                    for p in matched:
                        p.product_name = product.get("name", keyword)
                    for p in near:
                        p.product_name = product.get("name", keyword)
                        p.near_miss = True
                    all_matched.extend(matched)
                    all_near_miss.extend(near)
                    time.sleep(1.5)

                # 2. Ricerca per ASIN specifici se configurati
                asins = product.get("asins", [])
                for asin in asins:
                    item = self._fetch_product_page(asin)
                    if not item:
                        continue
                    self.all_asins.append(asin)
                    p = self._make_product(item, product.get("name", "Amazon"), max_price, margin)
                    if p:
                        if p.near_miss:
                            all_near_miss.append(p)
                        else:
                            all_matched.append(p)
                    time.sleep(2)

            used_matched, used_near = self._fetch_used_offers_for_all(self.products)
            all_matched.extend(used_matched)
            all_near_miss.extend(used_near)

            return all_matched, all_near_miss
        finally:
            pass

    def search(self, keyword):
        url = f"https://www.amazon.it/s?k={keyword.replace(' ', '+')}"
        results = []
        for attempt, delay in enumerate(RETRY_DELAYS):
            session = None
            try:
                session = self._make_session()
                resp = session.get(url, impersonate="chrome131", timeout=25)
                if resp.status_code != 200:
                    time.sleep(delay)
                    continue
                soup = BeautifulSoup(resp.text, "lxml")
                cards = soup.select("div[data-component-type='s-search-result'], div.s-result-item[data-asin]")
                for card in cards:
                    asin = card.get("data-asin", "")
                    if not asin or card.select_one(".a-row.a-spacing-micro"):
                        # Salta sponsorizzati generici se privi di ASIN valido
                        pass
                    title_el = card.select_one("h2 a span, h2 span, .a-size-medium, .a-size-base-plus")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    price_el = card.select_one(".a-price .a-offscreen, span.a-price-whole, .a-color-price, .a-price")
                    if not price_el:
                        continue
                    price = self._parse_price(price_el.get_text(strip=True))
                    if not price or price <= 1:
                        continue
                    link_el = card.select_one("h2 a, a.a-link-normal[href*='/dp/']")
                    href = link_el["href"] if link_el and link_el.has_attr("href") else f"/dp/{asin}"
                    full_url = href if href.startswith("http") else f"https://www.amazon.it{href}"
                    
                    # Rilevamento condizione (Nuovo, Ricondizionato o Usato)
                    condition = "Nuovo"
                    badge_text = card.get_text(separator=" ", strip=True).lower()
                    if "ricondizionato" in badge_text or "renewed" in badge_text:
                        condition = "Ricondizionato"
                    elif "usato" in badge_text or "seconda mano" in badge_text:
                        condition = "Usato"

                    p = Product(
                        title=title, price=price, url=full_url, source="Amazon.it",
                        location="Amazon.it", shipping=True, condition=condition
                    )
                    results.append(p)
                if results:
                    return results
            except Exception as e:
                time.sleep(delay)
            finally:
                if session:
                    try:
                        session.close()
                    except:
                        pass
        return results

    def _fetch_product_page(self, asin):
        urls = [
            f"https://www.amazon.it/dp/{asin}",
            f"https://www.amazon.it/gp/product/{asin}",
        ]
        for url in urls:
            for attempt, delay in enumerate(RETRY_DELAYS):
                session = None
                try:
                    session = self._make_session()
                    resp = session.get(url, impersonate="chrome131", timeout=25)
                    if resp.status_code != 200:
                        if resp.status_code == 503 or resp.status_code == 403:
                            print(f"  [WARN] Amazon {asin}: HTTP {resp.status_code} (bloccato), riprovo tra {delay}s")
                            time.sleep(delay)
                            continue
                        print(f"  [WARN] Amazon {asin}: HTTP {resp.status_code} per {url}")
                        break

                    soup = BeautifulSoup(resp.text, "lxml")
                    title_el = soup.select_one("span#productTitle")
                    if not title_el:
                        preview = resp.text[:200].replace("\n", " ")
                        print(f"  [WARN] Amazon {asin}: no #productTitle in {url}. HTML: {preview}...")
                        break

                    title = title_el.get_text(strip=True)
                    price = self._extract_product_price(soup)
                    if not price:
                        print(f"  [WARN] Amazon {asin}: no price in {url}")
                        break

                    ship_text = soup.get_text(separator=" ", strip=True).lower()
                    shipping = any(kw in ship_text for kw in ["spedizion", "gratis", "consegna"])
                    condition = "Nuovo"
                    cond_el = soup.select_one("span#condition-label, span.a-size-small.offer-attribute")
                    if cond_el:
                        ct = cond_el.get_text(strip=True).lower()
                        if "ricondizionato" in ct:
                            condition = "Ricondizionato"
                        elif "usato" in ct:
                            condition = "Usato"

                    return {
                        "asin": asin,
                        "title": title,
                        "price": price,
                        "url": url,
                        "shipping": shipping,
                        "condition": condition,
                    }
                except Exception as e:
                    err = str(e)
                    if "getaddrinfo" in err or "thread failed" in err or "timed out" in err:
                        print(f"  [WARN] Amazon {asin} DNS/Timeout (tentativo {attempt + 1}/{len(RETRY_DELAYS)}), riprovo tra {delay}s: {type(e).__name__}")
                        time.sleep(delay)
                    else:
                        print(f"  [WARN] Amazon {asin} errore: {type(e).__name__}: {e}")
                        break
                finally:
                    if session:
                        try:
                            session.close()
                        except:
                            pass
        return None

    def _extract_product_price(self, soup):
        price_selectors = [
            ".apexPriceToPay span.a-offscreen",
            "#price_inside_buybox",
            "#corePrice_feature_div .a-price .a-offscreen",
            "#corePriceDisplay_desktop_feature_div .a-price-whole",
            "span.a-price-whole",
            ".a-price .a-offscreen",
            "span.a-offscreen",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            ".a-price[data-a-size='xl'] .a-offscreen",
        ]
        for sel in price_selectors:
            el = soup.select_one(sel)
            if el:
                price = self._parse_price(el.get_text(strip=True))
                if price:
                    return price
        return None

    def _make_product(self, item, product_name, max_price, margin):
        price = item["price"]
        near_miss = price > max_price and price <= max_price + margin
        if price > max_price + margin:
            return None
        p = Product(
            title=item["title"],
            price=price,
            url=item["url"],
            source="Amazon.it",
            location="Amazon.it",
            shipping=item.get("shipping", False),
            condition=item.get("condition", "Nuovo"),
            date=datetime.now().isoformat(),
        )
        p.product_name = product_name
        p.max_price = max_price
        p.near_miss = near_miss
        return p

    def _fetch_used_offers_for_all(self, products):
        all_matched = []
        all_near = []
        seen = set()
        for asin in self.all_asins:
            if asin in seen:
                continue
            seen.add(asin)
            used = self._fetch_used_offers(asin, products)
            for p in used:
                if p.near_miss:
                    all_near.append(p)
                else:
                    all_matched.append(p)
            time.sleep(1.5)
        return all_matched, all_near

    def _fetch_used_offers(self, asin, products):
        url = f"https://www.amazon.it/gp/offer-listing/{asin}/ref=olp_f_used?ie=UTF8&f_used=true&f_usedAcceptable=true&f_usedGood=true&f_usedLikeNew=true&f_usedVeryGood=true"
        for attempt, delay in enumerate(RETRY_DELAYS):
            session = None
            try:
                session = self._make_session()
                resp = session.get(url, impersonate="chrome131", timeout=25)
                if resp.status_code != 200:
                    print(f"  [WARN] Amazon used offers {asin}: HTTP {resp.status_code}")
                    return []
                soup = BeautifulSoup(resp.text, "lxml")
                results = []
                for card in soup.select("div.a-row.olpOffer, .olpOffer, [data-testid='offer']"):
                    text = card.get_text(separator=" ", strip=True)
                    price_el = card.select_one(".olpOfferPrice, .a-price-whole, .a-offscreen")
                    if not price_el:
                        continue
                    price = self._parse_price(price_el.get_text(strip=True))
                    if not price:
                        continue
                    cond_el = card.select_one(".olpCondition, .a-size-small.offer-attribute")
                    cond_label = cond_el.get_text(strip=True) if cond_el else ""
                    notes_el = card.select_one(".olpConditionInfo")
                    notes = notes_el.get_text(strip=True) if notes_el else ""
                    cond_parts = ["Usato Garantito"]
                    if cond_label:
                        cond_parts.append(cond_label)
                    if notes:
                        cond_parts.append(f"- {notes}")
                    condition = " | ".join(cond_parts)
                    p = Product(
                        title=f"Usato Garantito {asin}",
                        price=price,
                        url=f"https://www.amazon.it/dp/{asin}",
                        source="Amazon.it",
                        location="Amazon.it",
                        shipping=True,
                        condition=condition,
                        date=datetime.now().isoformat()
                    )
                    for prod_cfg in products:
                        max_price = prod_cfg.get("max_price", 500)
                        margin = prod_cfg.get("price_margin", 50)
                        if price <= max_price:
                            p.max_price = max_price
                            p.product_name = prod_cfg.get("name", "?") + " - Usato Garantito"
                            results.append(p)
                            break
                        elif price <= max_price + margin:
                            p.max_price = max_price
                            p.product_name = prod_cfg.get("name", "?") + " - Usato Garantito"
                            p.near_miss = True
                            results.append(p)
                            break
                return results
            except Exception as e:
                err = str(e)
                if "getaddrinfo" in err or "thread failed" in err or "timed out" in err:
                    print(f"  [WARN] Amazon used offers {asin} DNS/Timeout (tentativo {attempt + 1}/{len(RETRY_DELAYS)}), riprovo tra {delay}s")
                    time.sleep(delay)
                else:
                    print(f"  [WARN] Amazon used offers {asin}: {e}")
                    return []
            finally:
                if session:
                    try:
                        session.close()
                    except:
                        pass
        return []

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
