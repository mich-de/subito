# Offerte Monitor - Subito.it, Amazon.it & NorthLadder Trade-In Price Tracker

A premium, high-performance web dashboard and automated background price scanner tracking deals and matching criteria on **Subito.it**, **Amazon.it**, and **NorthLadder Trade-In Valuation**, sending real-time notifications via Telegram.

---

## 🌟 Key Features

- **Multi-Source Scraping**:
  - **Subito.it**: Real-time keyword & description search with filter exclusions (`scambio`, `cerco`, accessories, etc.).
  - **Amazon.it**: Keyword search & ASIN tracking with modern price selectors.
  - **NorthLadder Trade-In**: Automated Playwright simulation reproducing full trade-in evaluation questionnaires (device condition, working status, screen/body checks) and email entry for valuation tracking.
- **GitHub Actions Automated Scans (Cloud)**:
  - Runs in the cloud every **15 minutes** via GitHub Actions workflow (`.github/workflows/scanner.yml`).
  - Automated history caching (`data/sent_items.json`) to prevent duplicate alerts.
  - Secure integration with **GitHub Repository Secrets** (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`).
- **Web Dashboard & Responsive Interface**:
  - Fluid grid layout optimized for mobile, tablet, and high-resolution desktop screens (up to 1400px+).
  - Dynamic product filtering tabs (*S24 256GB*, *S24 512GB*, *S25 256GB*, *S25 512GB*, *Pixel*).
  - Real-time terminal logs viewer via `/api/logs`.
  - Dark mode glassmorphism UI built with Vanilla CSS.
- **Telegram Notifier**: Instant alerts for deals below target threshold and *near-miss* offers (+€50 margin).

---

## 🚀 Setup & Installation

### 1. GitHub Actions (Automated Cloud Scans)

To run automated 15-minute scans on GitHub Cloud:

1. Go to your repository settings: **Settings > Secrets and variables > Actions**.
2. Add the following **Repository Secrets**:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram Bot Token.
   - `TELEGRAM_CHAT_ID`: Your Telegram Chat ID.
3. Automated scans will run every **15 minutes** and send Telegram alerts whenever a price drop or trade-in offer is matched.

---

### 2. Local Setup (Web Dashboard & Local Scraper)

#### Prerequisites
- Python 3.10+
- Chromium browser (installed automatically via Playwright)

#### Installation Steps
1. Clone the repository:
   ```bash
   git clone https://github.com/mich-de/subito.git
   cd subito
   ```
2. Initialize virtual environment:
   ```powershell
   python -m venv .venv
   ```
3. Install dependencies:
   ```powershell
   .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
   ```
4. Install Playwright binaries:
   ```powershell
   .\\.venv\\Scripts\\python.exe -m playwright install chromium
   ```

#### Local Credentials Setup
Create a file named `config/credentials.yaml` (ignored by git):
```yaml
telegram:
  enabled: true
  bot_token: 'YOUR_TELEGRAM_BOT_TOKEN'
  chat_id: 'YOUR_TELEGRAM_CHAT_ID'
```
*(Alternatively, create a `.env` file containing `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`)*.

---

## 💻 Running Locally

Launch the scraper and web dashboard using the provided helper scripts:

- **PowerShell**:
  ```powershell
  .\\start.ps1
  ```
- **Command Prompt (CMD)**:
  ```cmd
  start.cmd
  ```

Access the Web Dashboard at: **[http://localhost:5000](http://localhost:5000)**

---

## ⚙️ Configuration Files

- `config/config.yaml`: Main products, search keywords, max price limits, and exclude filters.
- `config/subito.yaml`: Subito scanner parameters.
- `config/amazon.yaml`: Amazon scanner parameters.
- `config/northladder.yaml`: NorthLadder Trade-In valuation thresholds and device names.
- `config/credentials.yaml`: Isolated Telegram tokens (git-ignored).
