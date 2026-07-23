from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
import json
import os

ROME_TZ = timezone(timedelta(hours=2))

PRICE_MARGIN = 50
SENT_HISTORY_FILE = "data/sent_items.json"

class Product:
    def __init__(self, title, price, url, source, location="", shipping=False, condition="", date=None, product_name="", near_miss=False, max_price=0):
        self.title = title
        self.price = price
        self.url = url
        self.source = source
        self.location = location
        self.shipping = shipping
        self.condition = condition
        self.date = date or datetime.now(ROME_TZ).isoformat()
        self.product_name = product_name
        self.near_miss = near_miss
        self.max_price = max_price

    def to_dict(self):
        return {
            "title": self.title,
            "price": self.price,
            "url": self.url,
            "source": self.source,
            "location": self.location,
            "shipping": self.shipping,
            "condition": self.condition,
            "date": self.date,
            "product_name": self.product_name,
            "near_miss": self.near_miss,
            "max_price": self.max_price
        }

    def __repr__(self):
        tag = " [NEAR MISS]" if self.near_miss else ""
        ship = " [S]" if self.shipping else " [ ]"
        return f"[{self.source}]{tag} {self.title} - EUR{self.price}{ship} - {self.location}"

class BaseScanner(ABC):
    def __init__(self, config, global_config):
        self.config = config
        self.global_config = global_config
        self.name = config.get("name", "Unknown")
        self.enabled = config.get("enabled", True)
        self.shipping_required = global_config["scanner"]["shipping_required"]
        self.products = global_config["scanner"].get("products", [])
        self.results_file = f"data/{self.__class__.__name__.lower()}_results.json"

    @abstractmethod
    def search(self, keyword):
        pass

    def run(self):
        if not self.enabled:
            return [], []
        all_matched = []
        all_near_miss = []
        source_key = self.config.get("source_key", self.name.lower())
        for product in self.products:
            enabled = product.get(source_key, True)
            if not enabled:
                continue
            max_price = product.get("max_price", 500)
            keywords = product.get("keywords", [])
            for keyword in keywords:
                results = self.search(keyword)
                margin = product.get("price_margin", 50)
                matched, near = self.classify_results(results, max_price, margin)
                for p in matched:
                    p.product_name = product.get("name", keyword)
                for p in near:
                    p.product_name = product.get("name", keyword)
                    p.near_miss = True
                all_matched.extend(matched)
                all_near_miss.extend(near)
        combined = all_matched + all_near_miss
        self._save_results(combined)
        return all_matched, all_near_miss

    def classify_results(self, results, max_price, margin=50):
        matched = []
        near_miss = []
        for p in results:
            if not p.price or p.price <= 1 or (not p.shipping and self.shipping_required):
                continue
            if p.price <= max_price:
                p.max_price = max_price
                matched.append(p)
            elif p.price <= max_price + margin:
                p.max_price = max_price
                near_miss.append(p)
        return matched, near_miss

    def is_new(self, product):
        sent = self._load_sent_history()
        key = f"{product.url}|{product.product_name}"
        if key in sent:
            return sent[key].get("price") != product.price
        return True

    def mark_sent(self, product):
        sent = self._load_sent_history()
        key = f"{product.url}|{product.product_name}"
        sent[key] = {"price": product.price, "timestamp": datetime.now().isoformat()}
        self._save_sent_history(sent)

    def _load_sent_history(self):
        if not os.path.exists(SENT_HISTORY_FILE):
            return {}
        try:
            with open(SENT_HISTORY_FILE, encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def _save_sent_history(self, sent):
        os.makedirs("data", exist_ok=True)
        with open(SENT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(sent, f, indent=2, ensure_ascii=False)

    def _load_results(self):
        if not os.path.exists(self.results_file):
            return []
        with open(self.results_file, encoding="utf-8") as f:
            return json.load(f)

    def _save_results(self, results):
        os.makedirs("data", exist_ok=True)
        with open(self.results_file, "w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in results], f, indent=2, ensure_ascii=False)

    def _prune_sold(self, current):
        pass
