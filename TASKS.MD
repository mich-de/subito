# Road Map & Tasks

Tracked tasks grouped by Agent responsibilities.

## [DEVOPS] Environment & Setup
- [x] Initialize Python Virtual Environment `.venv` <!-- id: 0 -->
- [x] Update [requirements.txt](file:///d:/nodejs/subito.it/requirements.txt) with `curl_cffi` and `playwright` <!-- id: 1 -->
- [x] Install package dependencies inside virtual environment <!-- id: 2 -->
- [x] Run `playwright install chromium` inside virtual environment <!-- id: 3 -->
- [x] Create helper `start.ps1` script to kill port listener before startup <!-- id: 17 -->
- [x] Create helper `start.cmd` script to kill port listener before startup <!-- id: 18 -->



## [RESEARCHER] Best Practices & Evasion
- [x] Research anti-blocking request parameters for Subito and Amazon <!-- id: 4 -->
- [x] Research modern layout and glassmorphism styling parameters in pure CSS <!-- id: 5 -->
- [x] Research thread safety for configurations in Flask background tasks <!-- id: 6 -->

## [BACKEND] Logic & Parallel Scrapers
- [x] Refactor [main.py](file:///d:/nodejs/subito.it/main.py) scheduler to run scans in parallel <!-- id: 7 -->
- [x] Implement thread lock for global configurations load/save in [main.py](file:///d:/nodejs/subito.it/main.py) <!-- id: 8 -->
- [x] Create log memory buffer and expose it via `/api/logs` endpoint in [main.py](file:///d:/nodejs/subito.it/main.py) <!-- id: 9 -->
- [x] Optimize browser context sharing and persistence in [amazon_scanner.py](file:///d:/nodejs/subito.it/scanner/amazon_scanner.py) <!-- id: 10 -->
- [x] Reuse `curl_cffi` requests Session in [subito_scanner.py](file:///d:/nodejs/subito.it/scanner/subito_scanner.py) <!-- id: 11 -->
- [x] Implement clean exit handler for browser closing on server shutdown <!-- id: 12 -->
- [x] Resolve charmap/CP1252 Unicode encoding errors on Windows by enforcing UTF-8 and configuring streams <!-- id: 19 -->
- [x] Fix /api/latest slice bug cutting off cheapest results in [main.py](file:///d:/nodejs/subito.it/main.py) <!-- id: 20 -->
- [x] Raise `CURLOPT_CONNECTTIMEOUT` limit to 10s (Subito) and 15s (Amazon) to resolve connection and DNS failures <!-- id: 22 -->
- [x] Extend Subito keyword matching to search listing description (`body` text) in [subito_scanner.py](file:///d:/nodejs/subito.it/scanner/subito_scanner.py) <!-- id: 23 -->


## [FRONTEND] Style & Interactivity
- [x] Rewrite [style.css](file:///d:/nodejs/subito.it/static/style.css) with HSL theme, glassmorphism, transitions, scrollbars, and fonts <!-- id: 13 -->
- [x] Rewrite [index.html](file:///d:/nodejs/subito.it/templates/index.html) to remove Tailwind CDN and restructure page sections <!-- id: 14 -->
- [x] Wire up real-time server log viewer via `/api/logs` page polling <!-- id: 15 -->
- [x] Verify responsive breakpoints, animations, and form interactions <!-- id: 16 -->
- [x] Add dynamic product filters to dashboard in [index.html](file:///d:/nodejs/subito.it/templates/index.html) and [style.css](file:///d:/nodejs/subito.it/static/style.css) <!-- id: 21 -->
- [x] Configure Samsung S24 thresholds to €240 and Samsung S25 thresholds to €400 for both 256GB and 512GB sizes in [config.yaml](file:///d:/nodejs/subito.it/config/config.yaml) <!-- id: 24 -->
- [x] Optimize Amazon price extraction selectors in [amazon_scanner.py](file:///d:/nodejs/subito.it/scanner/amazon_scanner.py) <!-- id: 25 -->


