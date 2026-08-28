import glob
import json
import os

def build_static_site():
    print("Building static site for GitHub Pages...")
    os.makedirs("public", exist_ok=True)
    with open("public/.nojekyll", "w", encoding="utf-8") as f:
        f.write("")
    
    with open("templates/index.html", encoding="utf-8") as f:
        html_content = f.read()

    # Sostituisci chiamate API con dati pre-caricati per la visualizzazione statica su GitHub Pages.
    # Glob su tutti gli scanner: prima subito/amazon erano hardcoded e NorthLadder non arrivava mai in dashboard.
    items = []
    for path in sorted(glob.glob("data/*scanner_results.json")):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                items.extend(data)
                print(f"  {path}: {len(data)} annunci")
            else:
                print(f"  [WARN] {path}: formato inatteso, ignorato")
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [WARN] {path}: illeggibile ({e}), ignorato")

    # Inietta direttamente lo stile CSS inline per eliminare problemi di caricamento o percorsi su GitHub Pages.
    # Due fogli in cascata: prima il design system, poi il livello applicativo. L'ordine va rispettato.
    os.makedirs("public/static", exist_ok=True)
    final_html = html_content
    for sheet in ("quadro-partenze.css", "style.css"):
        with open(f"static/{sheet}", encoding="utf-8") as f:
            css = f.read()
        with open(f"public/static/{sheet}", "w", encoding="utf-8") as f:
            f.write(css)
        style_tag = f"<style>\n{css}\n</style>"
        for href in (f'static/{sheet}', f'/static/{sheet}'):
            final_html = final_html.replace(f'<link rel="stylesheet" href="{href}">', style_tag)

    # Pre-carica configurazioni strutturate per il pannello form prodotti su GitHub Pages
    import yaml

    def read_yaml(path):
        if not os.path.exists(path):
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}

    config_data = {}
    c = read_yaml("config/config.yaml")
    if c:
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

    # I toggle Subito/Amazon vivono nei rispettivi file: senza questi restavano sui default HTML
    for key, path in (("subito", "config/subito.yaml"), ("amazon", "config/amazon.yaml")):
        s = read_yaml(path)
        if s:
            config_data[key] = {
                "enabled": s.get("enabled", True),
                "max_pages": s.get("max_pages", 3),
            }

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

    # La cadenza reale su Pages è il cron del workflow, non scanner.interval_minutes (che vale solo per il server Flask)
    CRON_MINUTES = 15
    try:
        import re
        with open(".github/workflows/scanner.yml", encoding="utf-8") as f:
            m = re.search(r"cron:\s*['\"]\*/(\d+)", f.read())
        if m:
            CRON_MINUTES = int(m.group(1))
    except Exception:
        pass

    # Log derivati dai risultati reali dell'ultimo run (prima erano stringhe inventate e disallineate)
    from datetime import datetime, timezone, timedelta
    rome_tz = timezone(timedelta(hours=2))
    now_str = datetime.now(rome_tz).strftime("%H:%M:%S")

    def count_from(path):
        if not os.path.exists(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return len(json.load(f))
        except Exception:
            return None

    product_names = [p.get("name", "?") for p in config_data.get("products", [])]
    scan_logs = [{
        "message": f"Build statico generato da GitHub Actions - {len(product_names)} prodotti monitorati.",
        "level": "info", "time": now_str
    }]

    for label, path, key in (
        ("SUBITO.IT", "data/subitoscanner_results.json", "subito"),
        ("AMAZON.IT", "data/amazonscanner_results.json", "amazon"),
    ):
        if not config_data.get(key, {}).get("enabled", True):
            scan_logs.append({"message": f"[{label}] Scanner disabilitato in config.", "level": "info", "time": now_str})
            continue
        n = count_from(path)
        if n is None:
            scan_logs.append({"message": f"[{label}] Nessun file risultati generato dall'ultimo run.", "level": "error", "time": now_str})
        elif n == 0:
            scan_logs.append({"message": f"[{label}] Scansione completata: 0 annunci entro soglia.", "level": "scan", "time": now_str})
        else:
            scan_logs.append({"message": f"[{label}] Scansione completata: {n} annunci entro soglia.", "level": "found", "time": now_str})

    nl = read_yaml("config/northladder.yaml")
    if nl.get("enabled", False):
        nl_price = None
        try:
            with open("data/northladder_history.json", encoding="utf-8") as f:
                hist = json.load(f)
            if hist:
                nl_price = hist[-1].get("price")
        except Exception:
            pass
        nl_device = nl.get("device_name", "?")
        if nl_price is not None:
            scan_logs.append({
                "message": f"[NORTHLADDER] Ultima valutazione permuta {nl_device}: {nl_price}EUR "
                           f"(soglia {nl.get('price_threshold', 0)}EUR).",
                "level": "found", "time": now_str
            })
        else:
            scan_logs.append({"message": f"[NORTHLADDER] Nessuna valutazione registrata per {nl_device}.", "level": "error", "time": now_str})

    tg_on = config_data.get("telegram", {}).get("enabled", False)
    scan_logs.append({
        "message": "[TELEGRAM] Notifiche abilitate (token da GitHub Secrets)." if tg_on
                   else "[TELEGRAM] Notifiche disabilitate in config.",
        "level": "found" if tg_on else "info", "time": now_str
    })
    scan_logs.append({
        "message": f"Prossima esecuzione via cron GitHub Actions (ogni {CRON_MINUTES} minuti). "
                   f"Il pannello configurazione e' di sola lettura su GitHub Pages.",
        "level": "info", "time": now_str
    })

    # Inietta lo stato pre-popolato nell'HTML statico per GitHub Pages
    inject_script = f"""
    <script>
      window.STATIC_ITEMS = {json.dumps(items, ensure_ascii=False)};
      window.STATIC_CONFIGS = {json.dumps(configs, ensure_ascii=False)};
      window.STATIC_CONFIG_DATA = {json.dumps(config_data, ensure_ascii=False)};
      window.STATIC_LOGS = {json.dumps(scan_logs, ensure_ascii=False)};
      // La pagina scriveva "cron 15m" da una costante: dopo il passaggio a 30
      // minuti diceva il falso. La cadenza vera e' quella del workflow.
      window.SCAN_CADENCE = {CRON_MINUTES};
      document.addEventListener('DOMContentLoaded', () => {{
        if (window.STATIC_ITEMS && window.STATIC_ITEMS.length) {{
          state.items = window.STATIC_ITEMS;
          renderItems(window.STATIC_ITEMS);
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
