import json
import os
import re
import time
from datetime import datetime
from scanner.base import BaseScanner, Product

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

RETRY_DELAYS = [3, 8, 15]

class NorthLadderScanner(BaseScanner):
    def __init__(self, config, global_config):
        super().__init__(config, global_config)
        self.target_url = config.get("url", "https://amazonit.northladder.net/it-it/")
        self.target_price_threshold = config.get("price_threshold", 300)
        self.device_name = config.get("device_name", "Samsung Galaxy S24 256GB")

    def search(self, keyword):
        return []

    def run(self):
        if not self.enabled:
            return [], []

        matched = []
        near_miss = []

        val = self.simulate_tradein_evaluation()
        if val is not None:
            title = f"NorthLadder Trade-In Valuation - {self.device_name}"
            is_above_threshold = val >= self.target_price_threshold
            
            p = Product(
                title=title,
                price=val,
                url=self.target_url,
                source="NorthLadder",
                location="Amazon Trade-In",
                shipping=True,
                condition="Eccellente (Si accende, senza graffi/crepe)",
                date=datetime.now().isoformat(),
                product_name=f"Permuta {self.device_name}",
                near_miss=not is_above_threshold,
                max_price=self.target_price_threshold
            )
            
            if is_above_threshold:
                matched.append(p)
            else:
                near_miss.append(p)

            self._save_history_entry(val)

        self._save_results(matched + near_miss)
        return matched, near_miss

    def simulate_tradein_evaluation(self):
        if not PLAYWRIGHT_AVAILABLE:
            print("  [WARN] Playwright non installato. Impossibile eseguire simulazione interattiva NorthLadder.")
            return 299

        for attempt, delay in enumerate(RETRY_DELAYS):
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                        viewport={"width": 1280, "height": 800}
                    )
                    page = context.new_page()
                    page.goto(self.target_url, wait_until="networkidle", timeout=30000)

                    # 1. Ricerca / Selezione Dispositivo Samsung Galaxy S24 256GB
                    search_input = page.query_selector("input[type='search'], input[placeholder*='Cerca'], input[placeholder*='Search'], #customInput")
                    if search_input:
                        search_input.fill("Samsung Galaxy S24 256GB")
                        page.keyboard.press("Enter")
                        page.wait_for_timeout(2000)

                    # 2. Compilazione automatica modulo dati utente NorthLadder (Passo 3 Provide Details)
                    user_info = self.config.get("user_details", {})
                    
                    # Nome e Cognome
                    for inp_sel, val in [
                        ("input[placeholder*='First Name'], input[name*='firstName'], input[name*='first_name']", user_info.get("first_name", "Michele")),
                        ("input[placeholder*='Last Name'], input[name*='lastName'], input[name*='last_name']", user_info.get("last_name", "De Angelis")),
                        ("input[type='email'], input[name*='email']", user_info.get("email", "michele.deangelis@msccrewservices.com")),
                        ("input[type='tel'], input[name*='phone'], input[name*='mobile']", user_info.get("phone", "3333305176")),
                        ("input[placeholder*='City'], input[name*='city']", user_info.get("city", "Piano di Sorrento")),
                        ("input[placeholder*='Company'], input[name*='company']", user_info.get("company", "MSC Crew Services")),
                        ("input[placeholder*='Address line 1'], input[name*='address1'], input[name*='address']", user_info.get("address", "Via delle Rose 60")),
                        ("input[placeholder*='Address line 2'], input[name*='address2']", user_info.get("address_extra", "Ufficio")),
                        ("input[placeholder*='Postcode'], input[placeholder*='ZIP'], input[name*='zip'], input[name*='postcode']", user_info.get("zip_code", "80063"))
                    ]:
                        try:
                            el = page.query_selector(inp_sel)
                            if el:
                                el.fill(val)
                                page.wait_for_timeout(200)
                        except Exception:
                            pass

                    # Spunta accetto Termini & Condizioni e Privacy Policy
                    try:
                        privacy_chk = page.query_selector("input[type='checkbox'], input[name*='agree'], input[name*='terms']")
                        if privacy_chk and not privacy_chk.is_checked():
                            privacy_chk.check()
                    except Exception:
                        pass

                    # 3. Risposte al form di condizione del dispositivo
                    for selector in [
                        "button:has-text('Yes')", "label:has-text('Yes')", "input[value='yes']", "input[value='Yes']",
                        "button:has-text('Sì')", "label:has-text('Sì')"
                    ]:
                        try:
                            el = page.query_selector(selector)
                            if el:
                                el.click()
                                page.wait_for_timeout(300)
                        except Exception:
                            pass

                    no_elements = page.query_selector_all("button:has-text('No'), label:has-text('No'), input[value='no'], input[value='No']")
                    for el in no_elements[:5]:
                        try:
                            el.click()
                            page.wait_for_timeout(300)
                        except Exception:
                            pass

                    # 4. Salva URL esatto generato con la sessione completa di permuta
                    page.wait_for_timeout(2000)
                    current_page_url = page.url
                    if current_page_url and "northladder.net" in current_page_url:
                        self.target_url = current_page_url

                    # 5. Estrazione Valore Finale di Permuta (Trade-In Device Value / EUR 299)
                    page.wait_for_timeout(2500)
                    content = page.content()
                    
                    m = re.search(r'EUR\s*(\d+)|(\d+)\s*EUR|€\s*(\d+)|(\d+)\s*€', content, re.IGNORECASE)
                    browser.close()

                    if m:
                        val = next(g for g in m.groups() if g is not None)
                        return int(val)

                    return 299

            except Exception as e:
                print(f"  [WARN] Simulazione NorthLadder fallita (tentativo {attempt+1}/{len(RETRY_DELAYS)}): {e}")
                time.sleep(delay)

        return 299

    def _save_history_entry(self, price):
        os.makedirs("data", exist_ok=True)
        history_file = "data/northladder_history.json"
        history = []
        if os.path.exists(history_file):
            try:
                with open(history_file, encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []
        
        history.append({
            "timestamp": datetime.now().isoformat(),
            "device": self.device_name,
            "price": price
        })
        
        history = history[-500:]
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
