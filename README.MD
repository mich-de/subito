# Offerte Monitor - Subito.it & Amazon.it Price Tracker

A premium, high-performance web dashboard and background price scanner tracking deals and matching criteria on Subito.it and Amazon.it, notifying matching offers via Telegram.

---

## Features

- **Concurrent Scraping**: Runs Amazon and Subito scans concurrently inside a ThreadPoolExecutor.
- **Scraper Optimizations**:
  - Reuses a single Playwright browser context per run, preventing rate-limiting footprint and memory overhead.
  - Reuses `curl_cffi` connection session for Subito.it.
  - Automatically cleans up and kills background browser processes on shutdown (no zombie Chromium tasks).
- **Live Terminal Log View**: Captures python server-side stdout prints and streams them dynamically in the web log console.
- **Premium Vanilla CSS UI**: Clean, responsive dashboard with glassmorphism layout, HSL variables, fluid cards, custom toggles, scrollbars, and micro-animations. Removed Tailwind CSS CDN.
- **Telegram Notifier**: Active Telegram alerts for matches and near misses (+€50 budget tolerance).

---

## Installation

### Prerequisites
- Python 3.10+
- Google Chrome or Chromium installed (fetched automatically by Playwright)

### Setup Steps
1. Clone or copy the project files to your folder.
2. Initialize virtual environment:
   ```powershell
   python -m venv .venv
   ```
3. Install the dependencies:
   ```powershell
   .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
   ```
4. Install Playwright browser engine binaries:
   ```powershell
   # If in a corporate environment with certificate blocks, use NODE_TLS_REJECT_UNAUTHORIZED
   $env:NODE_TLS_REJECT_UNAUTHORIZED="0"
   .\\.venv\\Scripts\\python.exe -m playwright install chromium
   ```

---

## How to Use

### Start the Server
You can launch the scraper and dashboard web server using the provided PowerShell or Command Prompt helper scripts, which automatically terminate any process currently occupying the configured port before launching the tracker:
- **PowerShell**:
  ```powershell
  .\\start.ps1
  ```
- **Command Prompt (CMD)**:
  ```cmd
  start.cmd
  ```

Alternatively, launch the interpreter directly:
```powershell
.\\.venv\\Scripts\\python.exe main.py
```

By default:
- The dashboard is accessible at: http://localhost:5000
- Scans run automatically every 30 minutes (configurable).
- Scrape logs stream in real-time in the dashboard logs box.

### Configuration
1. Open the dashboard.
2. Go to the **Configurazione** tab.
3. Define general interval times, toggles, Telegram bot token, chat ID, and add items with their price caps, price margins, and search keywords.
4. Click **Salva e Applica Configurazione**. The system will immediately reload, save the new configs, and trigger a concurrent scan.
5. Alternatively, edit the YAML files directly in the **Visualizza YAML** tab.
