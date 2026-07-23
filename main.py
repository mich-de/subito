import sys
import os

# Reconfigure stdout/stderr to use UTF-8 and handle encoding errors gracefully on Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import json
import signal
import atexit
from urllib.parse import urlparse
from datetime import datetime, timedelta
from threading import Thread, Event, Lock, RLock
from concurrent.futures import ThreadPoolExecutor

import yaml
from flask import Flask, jsonify, render_template, request

from scanner.subito_scanner import SubitoScanner
from scanner.amazon_scanner import AmazonScanner
from scanner.northladder_scanner import NorthLadderScanner
from notifier import TelegramNotifier
from reporter import ShellReporter

CONFIG_DIR = "config"
DATA_DIR = "data"
HISTORY_FILE = f"{DATA_DIR}/history.json"

# Capture stdout for API logs stream
class LogCapture:
    def __init__(self, original_stdout):
        self.original_stdout = original_stdout
        self.log_queue = []
        self.index = 0
        self.max_logs = 1000
        self.lock = Lock()

    def write(self, buf):
        self.original_stdout.write(buf)
        self.original_stdout.flush()
        text = buf.strip()
        if text:
            level = "info"
            if "[NEW]" in text or "[OK]" in text or "NUOVI ANNUNCI" in text or "Notifica inviata" in text:
                level = "found"
            elif "[ERRORE]" in text or "[ERROR]" in text or "[WARN]" in text or "[!]" in text or "Errore" in text:
                level = "error"
            elif "[SCAN]" in text or "[WAIT]" in text or "[WEB]" in text or "Avviato" in text:
                level = "scan"
            
            with self.lock:
                self.index += 1
                entry = {
                    "index": self.index,
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "message": text,
                    "level": level
                }
                self.log_queue.append(entry)
                if len(self.log_queue) > self.max_logs:
                    self.log_queue.pop(0)

    def flush(self):
        self.original_stdout.flush()

log_capturer = LogCapture(sys.stdout)
sys.stdout = log_capturer

config = {}
scanners = []
notifier = None
reporter = ShellReporter()
scan_history = []
scan_event = Event()
scan_now_event = Event()
shutdown_event = Event()
start_time = datetime.now()
config_lock = RLock()

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["TEMPLATES_AUTO_RELOAD"] = True

def load_config():
    global config
    with config_lock:
        with open(f"{CONFIG_DIR}/config.yaml", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        with open(f"{CONFIG_DIR}/subito.yaml", encoding="utf-8") as f:
            config["subito"] = yaml.safe_load(f)
        with open(f"{CONFIG_DIR}/amazon.yaml", encoding="utf-8") as f:
            config["amazon"] = yaml.safe_load(f)
        if os.path.exists(f"{CONFIG_DIR}/northladder.yaml"):
            with open(f"{CONFIG_DIR}/northladder.yaml", encoding="utf-8") as f:
                config["northladder"] = yaml.safe_load(f)
        else:
            config["northladder"] = {"enabled": False}

def init_scanners():
    global scanners, notifier
    with config_lock:
        scanners = [
            SubitoScanner(config["subito"], config),
            AmazonScanner(config["amazon"], config),
            NorthLadderScanner(config["northladder"], config),
        ]
        notifier = TelegramNotifier(config)

def load_history():
    global scan_history
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding="utf-8") as f:
            scan_history = json.load(f)

def save_history():
    os.makedirs(DATA_DIR, exist_ok=True)
    keep = scan_history[-100:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(keep, f, indent=2, ensure_ascii=False)

def run_scan():
    load_config()
    init_scanners()
    load_history()

    now = datetime.now().isoformat()
    all_new = []
    all_near_new = []
    all_items = []
    all_total = 0
    products = config["scanner"].get("products", [])

    active_scanners = [s for s in scanners if s.enabled]
    for scanner in active_scanners:
        for product in products:
            pname = product.get("name", "?")
            reporter.print_scan_start(scanner.name, pname)
        try:
            matched, near_miss = scanner.run()
            new_items = [p for p in matched if scanner.is_new(p)]
            new_near = [p for p in near_miss if scanner.is_new(p)]
            all_new.extend(new_items)
            all_near_new.extend(new_near)
            all_items.extend(matched + near_miss)
            all_total += len(matched) + len(near_miss)
            
            reporter.print_scan_result(scanner.name, len(matched), len(new_items))
            if new_items:
                notifier.send(new_items)
                for p in new_items:
                    scanner.mark_sent(p)
            if new_near:
                notifier.send_near_miss(new_near)
                for p in new_near:
                    scanner.mark_sent(p)
            try:
                reporter.print_new_items(new_items)
                if new_near:
                    reporter.print_near_misses(new_near)
            except Exception:
                pass
            scanner._save_results(matched + near_miss)
        except Exception as e:
            reporter.print_error(scanner.name, str(e))

    seen = {}
    for p in all_items:
        base = urlparse(p.url)._replace(query="").geturl() if p.url else p.url
        seen[base] = p
    all_items = list(seen.values())
    all_items.sort(key=lambda p: (p.price if p.price else 999999))
    entry = {
        "timestamp": now,
        "total": all_total,
        "new": len(all_new),
        "near_miss": len(all_near_new),
        "items": [p.to_dict() for p in all_items]
    }
    scan_history.append(entry)
    save_history()
    reporter.print_summary(all_new, all_total)
    return entry

def scheduler_loop():
    # Wait 10 seconds on startup for web server setup
    shutdown_event.wait(timeout=10)
    if shutdown_event.is_set():
        return

    while not shutdown_event.is_set():
        interval = config["scanner"].get("interval_minutes", 30)
        scan_event.clear()
        reporter.print_header()
        reporter.print_telegram_status(config["telegram"]["enabled"])
        run_scan()
        reporter.print_wait(interval)
        scan_event.set()
        
        # Wait for the interval, checking for shutdown or manual scan requests
        total_seconds = interval * 60
        elapsed = 0
        while elapsed < total_seconds and not shutdown_event.is_set() and not scan_now_event.is_set():
            shutdown_event.wait(timeout=1)
            elapsed += 1
            
        if scan_now_event.is_set():
            scan_now_event.clear()

@app.route("/")
def index():
    resp = render_template("index.html")
    return app.response_class(resp, mimetype="text/html", headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"})

@app.route("/api/status")
def api_status():
    uptime = datetime.now() - start_time
    last_scan = scan_history[-1] if scan_history else None
    return jsonify({
        "status": "running",
        "uptime": str(uptime).split(".")[0],
        "interval_minutes": config["scanner"].get("interval_minutes", 30),
        "products": config["scanner"].get("products", []),
        "telegram_enabled": config["telegram"]["enabled"],
        "scanners": {
            "subito": config["subito"]["enabled"],
            "amazon": config["amazon"]["enabled"]
        },
        "last_scan": last_scan,
        "scan_count": len(scan_history),
        "total_items_found": sum(s.get("total", 0) for s in scan_history),
        "total_new_items": sum(s.get("new", 0) for s in scan_history),
        "total_near_miss": sum(s.get("near_miss", 0) for s in scan_history)
    })

@app.route("/api/history")
def api_history():
    return jsonify(scan_history[-50:])

@app.route("/api/stats")
def api_stats():
    if not scan_history:
        return jsonify({})
    all_items = []
    for entry in scan_history:
        for item in entry.get("items", []):
            all_items.append(item)
    by_source = {}
    for item in all_items:
        s = item["source"]
        by_source.setdefault(s, {"count": 0, "min_price": None, "items": []})
        by_source[s]["count"] += 1
        by_source[s]["items"].append(item)
        p = item.get("price")
        if p:
            cur = by_source[s]["min_price"]
            by_source[s]["min_price"] = min(p, cur) if cur else p
    avg_price = None
    prices = [i["price"] for i in all_items if i.get("price")]
    if prices:
        avg_price = sum(prices) / len(prices)
    return jsonify({
        "total_scans": len(scan_history),
        "total_items": len(all_items),
        "by_source": {k: {"count": v["count"], "min_price": v["min_price"]} for k, v in by_source.items()},
        "avg_price": round(avg_price, 2) if avg_price else None,
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None
    })

@app.route("/api/logs")
def api_logs():
    since = request.args.get("since", 0, type=int)
    with log_capturer.lock:
        filtered = [l for l in log_capturer.log_queue if l["index"] > since]
    return jsonify({"logs": filtered})

@app.route("/api/config")
def api_config_list():
    files = [f for f in os.listdir(CONFIG_DIR) if f.endswith((".yaml", ".yml"))]
    return jsonify({"files": files})

@app.route("/api/config/form")
def api_config_form():
    return jsonify({
        "general": {
            "interval_minutes": config["scanner"].get("interval_minutes", 30),
            "shipping_required": config["scanner"].get("shipping_required", True),
        },
        "telegram": {
            "enabled": config["telegram"].get("enabled", False),
            "bot_token": config["telegram"].get("bot_token", ""),
            "chat_id": config["telegram"].get("chat_id", ""),
        },
        "products": config["scanner"].get("products", []),
        "subito": {
            "enabled": config["subito"].get("enabled", True),
            "max_pages": config["subito"].get("max_pages", 3),
        },
        "amazon": {
            "enabled": config["amazon"].get("enabled", True),
            "max_pages": config["amazon"].get("max_pages", 2),
        },
    })

@app.route("/api/config/form", methods=["POST"])
def api_config_form_save():
    data = request.get_json()
    if not data:
        return jsonify({"error": "missing data"}), 400

    try:
        cfg_path = os.path.join(CONFIG_DIR, "config.yaml")
        with config_lock:
            with open(cfg_path, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            cfg["telegram"]["enabled"] = data["telegram"]["enabled"]
            cfg["telegram"]["bot_token"] = data["telegram"]["bot_token"]
            cfg["telegram"]["chat_id"] = data["telegram"]["chat_id"]
            cfg["scanner"]["interval_minutes"] = int(data["general"]["interval_minutes"])
            cfg["scanner"]["shipping_required"] = data["general"]["shipping_required"]
            cfg["scanner"]["products"] = data["products"]
            with open(cfg_path, "w", encoding="utf-8") as f:
                yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

            sub_path = os.path.join(CONFIG_DIR, "subito.yaml")
            with open(sub_path, encoding="utf-8") as f:
                sub = yaml.safe_load(f) or {}
            sub["enabled"] = data["subito"]["enabled"]
            sub["max_pages"] = int(data["subito"]["max_pages"])
            with open(sub_path, "w", encoding="utf-8") as f:
                yaml.dump(sub, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

            amz_path = os.path.join(CONFIG_DIR, "amazon.yaml")
            with open(amz_path, encoding="utf-8") as f:
                amz = yaml.safe_load(f) or {}
            amz["enabled"] = data["amazon"]["enabled"]
            amz["max_pages"] = int(data["amazon"]["max_pages"])
            with open(amz_path, "w", encoding="utf-8") as f:
                yaml.dump(amz, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

            load_config()
            init_scanners()
            scan_now_event.set()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/config/<name>")
def api_config_get(name):
    path = os.path.join(CONFIG_DIR, name)
    if not os.path.exists(path) or not name.endswith((".yaml", ".yml")):
        return jsonify({"error": "not found"}), 404
    with open(path, encoding="utf-8") as f:
        content = f.read()
    return jsonify({"name": name, "content": content})

@app.route("/api/config/<name>", methods=["POST"])
def api_config_save(name):
    path = os.path.join(CONFIG_DIR, name)
    if not name.endswith((".yaml", ".yml")):
        return jsonify({"error": "invalid filename"}), 400
    data = request.get_json()
    if not data or "content" not in data:
        return jsonify({"error": "missing content"}), 400
    try:
        yaml.safe_load(data["content"])
    except Exception as e:
        return jsonify({"error": f"YAML non valido: {e}"}), 400
    with config_lock:
        with open(path, "w", encoding="utf-8") as f:
            f.write(data["content"])
        if name in ("config.yaml",) or name.startswith(("subito", "amazon")):
            load_config()
            init_scanners()
            scan_now_event.set()
    return jsonify({"ok": True, "name": name})

@app.route("/api/latest")
def api_latest():
    seen = {}
    for entry in reversed(scan_history[-10:]):
        for item in entry.get("items", []):
            url = item.get("url", "")
            if url and url not in seen:
                seen[url] = item
    items = list(seen.values())
    items.sort(key=lambda x: x.get("date", ""), reverse=True)
    return jsonify(items[:100])

def run_web():
    host = config["web"].get("host", "0.0.0.0")
    port = config["web"].get("port", 5000)
    debug = config["web"].get("debug", False)
    app.run(host=host, port=port, debug=debug, use_reloader=False)

def cleanup():
    pass

def signal_handler(sig, frame):
    print("\n  [STOP] Arresto in corso...")
    shutdown_event.set()
    cleanup()
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    atexit.register(cleanup)

    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    load_config()
    init_scanners()
    load_history()

    scheduler = Thread(target=scheduler_loop, daemon=True)
    scheduler.start()

    web = Thread(target=run_web, daemon=True)
    web.start()

    reporter.print_header()
    reporter.print_telegram_status(config["telegram"]["enabled"])
    print(f"  [WEB] http://localhost:{config['web']['port']}")
    print(f"  [INIT] Primo scan tra 10 secondi...\n")

    try:
        while not shutdown_event.is_set():
            shutdown_event.wait(timeout=1)
    except KeyboardInterrupt:
        signal_handler(None, None)
