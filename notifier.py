import requests
import urllib3
from datetime import datetime

urllib3.disable_warnings()

class TelegramNotifier:
    def __init__(self, config):
        tg = config.get("telegram", {})
        self.enabled = tg.get("enabled", False)
        self.bot_token = tg.get("bot_token", "")
        self.chat_id = tg.get("chat_id", "")
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send(self, products):
        if not self.enabled or not self.bot_token or not self.chat_id:
            return
        for p in products:
            msg = self._format(p)
            try:
                resp = requests.get(
                    f"{self.api_url}/sendMessage",
                    params={
                        "chat_id": self.chat_id,
                        "text": msg,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": False
                    },
                    timeout=10, verify=False
                )
                if resp.status_code == 200:
                    print(f"  [TELEGRAM] Notifica inviata: {p.title}")
                else:
                    print(f"  [TELEGRAM] Errore: {resp.status_code} - {resp.text}")
            except Exception as e:
                print(f"  [TELEGRAM] Errore di connessione: {e}")

    def send_summary(self, source, count, products):
        if not self.enabled:
            return
        msg = f"<b>📊 Riepilogo {source}</b>\n"
        msg += f"Trovati {count} annunci nelle ultime 24h\n\n"
        for p in products[:10]:
            ship = "📦" if p.shipping else ""
            msg += f"• <a href='{p.url}'>{p.title[:60]}</a> - €{p.price} {ship}\n"
        if len(products) > 10:
            msg += f"\n...e altri {len(products) - 10}"
        try:
            requests.get(
                f"{self.api_url}/sendMessage",
                params={"chat_id": self.chat_id, "text": msg, "parse_mode": "HTML"},
                    timeout=10, verify=False
                )
        except Exception as e:
            print(f"  [TELEGRAM] Errore summary: {e}")

    def send_near_miss(self, products):
        if not self.enabled or not self.bot_token or not self.chat_id:
            return
        for p in products:
            sopra = p.price - (p.max_price or 500)
            msg = (
                f"<b>⚠️ ATTENZIONE: Prezzo leggermente sopra la soglia!</b>\n\n"
                f"<b>{p.title}</b>\n"
                f"💰 <b>€{p.price}</b> (soglia €{p.max_price or 500}, +€{sopra})\n"
                f"🏪 {p.source}\n"
                f"📍 {p.location}\n"
                f"🚛 {'Spedizione disponibile' if p.shipping else 'Nessuna spedizione'}\n"
                f"📅 {p.date[:16]}\n\n"
                f"🔗 <a href='{p.url}'>Vedi annuncio</a>"
            )
            try:
                requests.get(
                    f"{self.api_url}/sendMessage",
                    params={"chat_id": self.chat_id, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": False},
                    timeout=10, verify=False
                )
                print(f"  [TELEGRAM] Near-miss inviata: {p.title}")
            except Exception as e:
                print(f"  [TELEGRAM] Errore near-miss: {e}")

    def _format(self, p):
        ship = "📦 Spedizione disponibile" if p.shipping else "❌ Nessuna spedizione"
        return (
            f"<b>🚨 OFFERTA TROVATA!</b>\n\n"
            f"<b>{p.title}</b>\n"
            f"💰 <b>€{p.price}</b>\n"
            f"🏪 {p.source}\n"
            f"📍 {p.location}\n"
            f"{ship}\n"
            f"📅 {p.date[:16]}\n\n"
            f"🔗 <a href='{p.url}'>Vedi annuncio</a>"
        )
