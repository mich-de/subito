# GEMINI.MD - Persistent Memory Log

## Session Info
- **Date**: 2026-06-30
- **Scope**: Codebase styling refactoring, performance optimization, and Multi-Agent simulation with MD handovers.

## Architectural Decisions
1. **Multi-Agent Simulation**:
   - `Researcher-Agent`: Research best practices (anti-scraping, thread safety, CSS systems).
   - `Frontend-Agent`: Visual design system in pure CSS, removing dependencies on Tailwind CSS CDN.
   - `Backend-Agent`: Running scanners in parallel threads, persisting the Playwright browser/context, exposing server-side logs via `/api/logs` endpoint.
   - `DevOps-Agent`: Creating `.venv` isolation, standard dependency management, setting up Playwright chromium.
   - Handovers will be coordinated using `HANDOVER.MD` at the project root.

2. **Styling & Assets**:
   - Replaced Tailwind CDN with Vanilla CSS (`static/style.css`) using CSS variables and modern Grid/Flexbox structures to improve loading speed, compliance with constraints, and user experience.
   - Pure HSL coloring scheme (emerald primary accents, dark background, glass glassmorphism overlays, custom typography).

3. **Concurrency and Speed**:
   - Scanners run concurrently using Python's `threading` or `concurrent.futures`.
   - Browser persistence in AmazonScanner to avoid spawning/terminating browser engines for each scrape.

## Current State
- All planned modifications are fully implemented and integrated.
- Environment successfully isolated in `.venv`, with requirements updated.
- Playwright Chromium binaries installed with SSL warnings bypassed.
- Scanning concurrency (thread pools) and browser context persistence live.
- Server-side log capture stream and thread safety locking implemented.
- Beautiful, high-end, responsive Vanilla CSS styling active, with Tailwind CDN fully removed.
- Handover log documented and ready for verification.

## Session Info - 2026-07-02
- **Scope**: Resolve 'charmap' / cp1252 codec errors caused by Unicode characters (emojis like 🔋) on Windows.
- **Agent Roles**:
  - `Backend-Agent`: Reconfigure stdout/stderr standard streams on startup to support UTF-8 with character replacement on errors, preventing console encoding crashes. Add explicit `utf-8` encoding parameters to all JSON/YAML file write/read open statements.

## Architectural Decisions
1. **Unicode/Encoding Resilience**:
   - For all configuration YAML files and data JSON files, explicitly defined `encoding="utf-8"` in `open` function calls to handle Unicode characters consistently on all platforms, including Windows where CP1252/charmap is the default system encoding.
   - For standard output stream capturing (`LogCapture` in `main.py`), reconfigured `sys.stdout` and `sys.stderr` to use `utf-8` and `errors="replace"` on startup to prevent traceback print calls containing emojis from triggering `UnicodeEncodeError`.

## Current State (Post-Fix)
- Codebase updated to fully handle emoji and Unicode characters on Windows systems.
- Validated python compilation of updated modules (main.py and scanner/base.py).

## Session Info - 2026-07-02 (Part 2)
- **Scope**: Fix dashboard results slice bug, add product-specific filtering, and stabilize network connection timeouts.
- **Agent Roles**:
  - `Backend-Agent`: 
    - Resolve the bug in `/api/latest` endpoint where slicing `[-20:]` on a price-sorted list cut off the cheapest listings (such as the €300 S24 listing). Traversed scan entries in reverse and sorted by date descending instead, increasing output count to 100.
    - Identified that `CURLOPT_CONNECTTIMEOUT` (`78`) was set to a 1-second limit in `_make_session()` for both `SubitoScanner` and `AmazonScanner`. This caused frequent connection/DNS failures on Windows. Increased timeouts to 10 seconds (Subito) and 15 seconds (Amazon) to stabilize execution.
  - `Frontend-Agent`: Added an interactive product filtering bar to the dashboard, dynamically generated from active products, enabling the user to toggle filters between all items and specific target products.

## Current State (Post-Filtering)
- Slice bug in `/api/latest` successfully resolved.
- Connection timeout limits raised to 10s (Subito) and 15s (Amazon), eliminating spurious `DNSError` / `Timeout` errors.
- Dynamic product filters implemented in UI (`templates/index.html` and `static/style.css`).
- App validated and compiled successfully.

## Session Info - 2026-07-03
- **Scope**: Support keyword matching in Subito descriptions.
- **Agent Roles**:
  - `Backend-Agent`: Updated `SubitoScanner._parse_item` in [subito_scanner.py](file:///D:/nodejs/subito.it/scanner/subito_scanner.py) to extract both title (`subject`) and description (`body`) and match search keywords against their combination, allowing products like the €450 Naples S25 (which only lists "256" in the description) to be parsed successfully.

## Session Info - 2026-07-23
- **Scope**: Aggiornamento delle soglie di prezzo (S24 a €240 e S25 a €400 su tagli da 256GB e 512GB) e ottimizzazione della ricerca Subito.it e Amazon.it.
- **Agent Roles**:
  - `Backend-Agent`:
    - Aggiornato [config.yaml](file:///D:/nodejs/subito.it/config/config.yaml) con i 4 profili separati: `Samsung S24 256GB` (€240), `Samsung S24 512GB` (€240), `Samsung S25 256GB` (€400), `Samsung S25 512GB` (€400).
    - Ottimizzata l'estrazione dei prezzi in [amazon_scanner.py](file:///D:/nodejs/subito.it/scanner/amazon_scanner.py) incorporando i selettori CSS recenti (`.apexPriceToPay span.a-offscreen`, `#price_inside_buybox`, `#corePrice_feature_div .a-price .a-offscreen`, `#corePriceDisplay_desktop_feature_div .a-price-whole`).
  - `Frontend-Agent`:
    - Verificata la corrispondenza dei filtri dinamici dell'interfaccia UI con le nuove tipologie e le nuove tag di prezzo.

## Current State
- Tutte le modifiche e le soglie di prezzo richieste sono attive e verificate.
- Codice aggiornato e compilato con successo senza errori.




