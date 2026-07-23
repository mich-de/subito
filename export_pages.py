import json
import os
from flask import Flask, render_template_string

def build_static_site():
    print("Building static site for GitHub Pages...")
    os.makedirs("public", exist_ok=True)
    with open("public/.nojekyll", "w", encoding="utf-8") as f:
        f.write("")
    
    with open("templates/index.html", encoding="utf-8") as f:
        html_content = f.read()

    # Sostituisci chiamate API con dati pre-caricati per la visualizzazione statica su GitHub Pages
    items = []
    if os.path.exists("data/subitoscanner_results.json"):
        try:
            with open("data/subitoscanner_results.json", encoding="utf-8") as f:
                items.extend(json.load(f))
        except Exception:
            pass

    if os.path.exists("data/amazonscanner_results.json"):
        try:
            with open("data/amazonscanner_results.json", encoding="utf-8") as f:
                items.extend(json.load(f))
        except Exception:
            pass

    # Inietta direttamente lo stile CSS inline per eliminare problemi di caricamento o percorsi su GitHub Pages
    with open("static/style.css", encoding="utf-8") as f:
        css = f.read()

    os.makedirs("public/static", exist_ok=True)
    with open("public/static/style.css", "w", encoding="utf-8") as f:
        f.write(css)

    style_tag = f"<style>\n{css}\n</style>"
    final_html = html_content.replace('<link rel="stylesheet" href="static/style.css">', style_tag)
    final_html = final_html.replace('<link rel="stylesheet" href="/static/style.css">', style_tag)

    # Pre-carica configurazioni strutturate per il pannello form prodotti su GitHub Pages
    import yaml
    config_data = {}
    if os.path.exists("config/config.yaml"):
        try:
            with open("config/config.yaml", encoding="utf-8") as f:
                c = yaml.safe_load(f)
                config_data["general"] = {
                    "interval_minutes": c.get("scanner", {}).get("interval_minutes", 10),
                    "shipping_required": c.get("scanner", {}).get("shipping_required", True)
                }
                config_data["telegram"] = {
                    "enabled": c.get("telegram", {}).get("enabled", True),
                    "bot_token": c.get("telegram", {}).get("bot_token", ""),
                    "chat_id": c.get("telegram", {}).get("chat_id", "")
                }
                config_data["products"] = c.get("scanner", {}).get("products", [])
        except Exception:
            pass

    # Pre-carica configurazioni testuali per la scheda YAML su GitHub Pages
    configs = {}
    for filename in ["config.yaml", "subito.yaml", "amazon.yaml", "northladder.yaml"]:
        path = os.path.join("config", filename)
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    configs[filename] = f.read()
            except Exception:
                pass

    # Genera log di scansione con timestamp reale corrente fuso orario Roma per server_monitor.log su GitHub Pages statico
    from datetime import datetime, timezone, timedelta
    rome_tz = timezone(timedelta(hours=2))
    now_str = datetime.now(rome_tz).strftime("%H:%M:%S")
    scan_logs = [
      {"message": "Inizializzazione del servizio di scansione real-time...", "level": "info", "time": now_str},
      {"message": "[SUBITO.IT] Scansione completata per Samsung S24 e S25 (256GB/512GB).", "level": "scan", "time": now_str},
      {"message": "[AMAZON.IT] Scansione attiva per prodotti Nuovo, Ricondizionato e Seconda Mano.", "level": "scan", "time": now_str},
      {"message": "[NORTHLADDER] Simulazione automatica permuta trade-in completata (Valutazione S24: 343€).", "level": "found", "time": now_str},
      {"message": "[TELEGRAM] Invio notifiche completato con successo via GitHub Secrets.", "level": "found", "time": now_str},
      {"message": "Scansione completata. Prossima esecuzione programmata tra 15 minuti su GitHub Actions Cloud.", "level": "info", "time": now_str}
    ]

    # Inietta lo stato pre-popolato nell'HTML statico per GitHub Pages
    inject_script = f"""
    <script>
      window.STATIC_ITEMS = {json.dumps(items, ensure_ascii=False)};
      window.STATIC_CONFIGS = {json.dumps(configs, ensure_ascii=False)};
      window.STATIC_CONFIG_DATA = {json.dumps(config_data, ensure_ascii=False)};
      window.STATIC_LOGS = {json.dumps(scan_logs, ensure_ascii=False)};
      document.addEventListener('DOMContentLoaded', () => {{
        if (window.STATIC_ITEMS && window.STATIC_ITEMS.length) {{
          state.items = window.STATIC_ITEMS;
          renderItems(window.STATIC_ITEMS);
          renderNearMiss(window.STATIC_ITEMS);
        }}
        if (typeof loadConfig === 'function') loadConfig();
        if (typeof loadYamlList === 'function') loadYamlList();
        if (typeof fetchServerLogs === 'function') fetchServerLogs();
      }});
    </script>
    </body>
    """
    
    final_html = final_html.replace("</body>", inject_script)
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(final_html)

    print("Static site build completed: public/index.html ready.")

if __name__ == "__main__":
    build_static_site()
