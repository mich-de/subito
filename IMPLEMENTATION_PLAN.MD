# IMPLEMENTATION_PLAN.MD - Style, Optimization, and Multi-Agent Handover

This plan outlines the optimization of the Subito & Amazon scanner interface and scraping back-end under a multi-agent model (Researcher, Frontend, Backend, DevOps) coordinated via `HANDOVER.MD`.

## Project Strategy
1. **DevOps-Agent**: Establish a fully isolated virtual environment, setup dependencies, install browser binaries.
2. **Researcher-Agent**: Research best practices for scraping, rate-limiting, and premium Vanilla CSS styling.
3. **Backend-Agent**: Optimize scanning logic (parallel execution), reuse browser context to prevent headless detection/overhead, implement a central log buffer.
4. **Frontend-Agent**: Replace Tailwind CDN with a highly premium Vanilla CSS layout (`static/style.css`), add glassmorphism, responsive designs, micro-animations, and pull logs in real-time.

---

## 1. DevOps & Environment Isolation

### Proposed Changes

#### [MODIFY] [requirements.txt](file:///d:/nodejs/subito.it/requirements.txt)
- Add missing requirements:
  - `curl_cffi` (for HTTP request impersonation and bypassing Cloudflare on Subito)
  - `playwright` (for page fetching on Amazon)
  - `playwright-stealth` (optional, for anti-bot detection)

---

## 2. Scraper & Logic Optimization (Backend)

### Proposed Changes

#### [MODIFY] [main.py](file:///d:/nodejs/subito.it/main.py)
- **Parallel Scanning**: Run scans concurrently.
- **Log Buffer API**: Create a circular buffer capturing all print/logger output and serve it via `/api/logs` to allow real-time monitoring on the frontend.
- **Thread Safety**: Protect configuration modification/reloads using `threading.Lock`.
- **Graceful Shutdown**: Close browser instances correctly on exit signals.

#### [MODIFY] [amazon_scanner.py](file:///d:/nodejs/subito.it/scanner/amazon_scanner.py)
- Re-use a single, persistent browser context rather than spinning up browser instances on every single keyword search.
- Clean closing of Playwright objects on exit.

#### [MODIFY] [subito_scanner.py](file:///d:/nodejs/subito.it/scanner/subito_scanner.py)
- Maintain a single `curl_cffi` requests Session per run.

---

## 3. UI/UX Refactoring & Aesthetics (Frontend)

### Proposed Changes

#### [MODIFY] [index.html](file:///d:/nodejs/subito.it/templates/index.html)
- Remove Tailwind CDN link.
- Re-architect HTML structure using semantic components.
- Connect log box to `/api/logs` with real-time fetching.

#### [MODIFY] [style.css](file:///d:/nodejs/subito.it/static/style.css)
- Implement pure Vanilla CSS.
- Design theme using CSS variables (`--bg`, `--accent`, `--card`, etc.).
- Add custom scrollbars, animations, and hover states.

---

## Verification Plan

### Automated
1. Create and active virtual environment `.venv`.
2. Run `pip install -r requirements.txt`.
3. Run `playwright install chromium`.
4. Validate Flask server execution.

### Manual
1. Access the web dashboard, verify the premium Vanilla CSS theme.
2. Check tab switching responsiveness.
3. Verify live logs and parallel scanner performance.
