from datetime import datetime

class ShellReporter:
    @staticmethod
    def print_header():
        print("=" * 70)
        print("  [SUBITO.IT + AMAZON.IT] Monitor Prezzi Samsung S25 256GB")
        print("=" * 70)
        print(f"  Avviato: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Check ogni: 30 minuti | Max: EUR500 | Spedizione: Richiesta")
        print("=" * 70)

    @staticmethod
    def print_scan_start(source, keyword):
        now = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now}] [SCAN] {source} per '{keyword}'...")

    @staticmethod
    def print_scan_result(source, count, new_count=0):
        now = datetime.now().strftime("%H:%M:%S")
        print(f"  [{now}] [OK] {source}: {count} annunci totali, {new_count} nuovi")

    @staticmethod
    def print_new_items(products):
        if not products:
            return
        print(f"\n  [NEW] NUOVI ANNUNCI TROVATI ({len(products)}):")
        print("  " + "-" * 66)
        for p in products:
            ship = "[S]" if p.shipping else "[ ]"
            print(f"  {ship} EUR{p.price:>5} | {p.title[:55]:<55}")
            print(f"       {p.source:<20} | {p.location:<30}")
            print(f"       {p.url}")
            print("  " + "-" * 66)

    @staticmethod
    def print_error(source, msg):
        print(f"  [ERRORE] {source}: {msg}")

    @staticmethod
    def print_near_misses(products):
        if not products:
            return
        print(f"\n  [!] ATTENZIONE - Prezzo leggermente sopra soglia ({len(products)}):")
        print("  " + "-" * 66)
        for p in products:
            sopra = p.price - (p.max_price or 500)
            print(f"  [!] EUR{p.price:>5} (+EUR{sopra}) | {p.title[:50]:<50}")
            print(f"       {p.source:<20} | {p.url}")
            print("  " + "-" * 66)

    @staticmethod
    def print_summary(all_new, all_total):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{'=' * 70}")
        print(f"  [SUMMARY] {now}")
        print(f"  Annunci trovati: {all_total} | Nuovi: {len(all_new)}")
        print(f"{'=' * 70}")

    @staticmethod
    def print_wait(minutes):
        now = datetime.now().strftime("%H:%M:%S")
        print(f"\n  [WAIT] Prossimo check tra {minutes} minuti...")
        print(f"  {now} | Premi Ctrl+C per fermare\n")

    @staticmethod
    def print_telegram_status(enabled):
        status = "[ON]" if enabled else "[OFF]"
        print(f"  [TELEGRAM] Status: {status}")
