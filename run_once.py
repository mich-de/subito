import sys
import os

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

import yaml
from scanner.subito_scanner import SubitoScanner
from scanner.amazon_scanner import AmazonScanner
from scanner.northladder_scanner import NorthLadderScanner
from notifier import TelegramNotifier
from reporter import ShellReporter

CONFIG_DIR = "config"

def main():
    with open(f"{CONFIG_DIR}/config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    with open(f"{CONFIG_DIR}/subito.yaml", encoding="utf-8") as f:
        config["subito"] = yaml.safe_load(f)
    with open(f"{CONFIG_DIR}/amazon.yaml", encoding="utf-8") as f:
        config["amazon"] = yaml.safe_load(f)
    if os.path.exists(f"{CONFIG_DIR}/northladder.yaml"):
        with open(f"{CONFIG_DIR}/northladder.yaml", encoding="utf-8") as f:
            config["northladder"] = yaml.safe_load(f)

    # Overwrite telegram tokens if passed via environment variables (GitHub Secrets)
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        config["telegram"]["bot_token"] = os.environ.get("TELEGRAM_BOT_TOKEN")
    if os.environ.get("TELEGRAM_CHAT_ID"):
        config["telegram"]["chat_id"] = os.environ.get("TELEGRAM_CHAT_ID")

    reporter = ShellReporter()
    notifier = TelegramNotifier(config)
    scanners = [
        SubitoScanner(config["subito"], config),
        AmazonScanner(config["amazon"], config),
        NorthLadderScanner(config["northladder"], config),
    ]

    reporter.print_header()
    reporter.print_telegram_status(config["telegram"]["enabled"])

    products = config["scanner"].get("products", [])
    all_new = []
    all_near_new = []
    all_total = 0

    for scanner in scanners:
        if not scanner.enabled:
            continue
        for product in products:
            reporter.print_scan_start(scanner.name, product.get("name", "?"))
        try:
            matched, near_miss = scanner.run()
            new_items = [p for p in matched if scanner.is_new(p)]
            new_near = [p for p in near_miss if scanner.is_new(p)]
            all_new.extend(new_items)
            all_near_new.extend(new_near)
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
        except Exception as e:
            reporter.print_error(scanner.name, str(e))

    reporter.print_summary(all_new, all_total)

if __name__ == "__main__":
    main()
