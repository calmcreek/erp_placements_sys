# IIT KGP ERP Monitor — GitHub Actions + GitHub Pages

This version separates the system into two parts:

- **GitHub Actions:** logs into IIT KGP ERP, reads the CDC Notice Board and Placement/Internship Board, sends Gmail notifications, and updates persistent JSON state about every 30 minutes.
- **GitHub Pages:** serves `index.html` as a static dashboard. The dashboard reads `dashboard_data.json` directly from the same repository.

There is no Flask server and no always-running process.

## Repository layout

```text
.
├── monitor.py
├── run_monitor.py
├── index.html
├── dashboard_data.json
├── seen_notices.json
├── seen_placements.json
├── requirements.txt
├── .env.example
├── .gitignore
└── .github/
    └── workflows/
        └── erp-monitor.yml
```

## 1. Add GitHub Actions secrets

In the repository, open **Settings → Secrets and variables → Actions → New repository secret** and add:

```text
ERP_USERNAME
ERP_PASSWORD
SECURITY_Q1
SECURITY_A1
SECURITY_Q2
SECURITY_A2
SECURITY_Q3
SECURITY_A3
GMAIL_ADDRESS
GMAIL_APP_PASSWORD
MAIL_TO
```

Do not put these values in `monitor.py`, `index.html`, JSON files, or the repository.

## 2. GitHub Pages

Enable GitHub Pages for the repository using the `main` branch and the repository root as the publishing source.

The dashboard is `index.html`, and it loads `dashboard_data.json` from the same directory.

The resulting URL is normally:

```text
https://YOUR_USERNAME.github.io/YOUR_REPOSITORY/
```

## 3. Run the monitor manually

The workflow contains `workflow_dispatch`, so after pushing the repository you can use:

**Actions → IIT KGP ERP Monitor → Run workflow**

The first successful run will populate the dashboard and initialize the monitoring state.

## 4. Schedule

The workflow uses:

```text
*/30 * * * *
```

GitHub Actions scheduled workflows are best-effort, so this means approximately every 30 minutes rather than an exact wall-clock guarantee.

## 5. Important public-data note

If this repository is public, `dashboard_data.json`, `seen_notices.json`, and `seen_placements.json` are public too. The repository must never contain ERP credentials, Gmail app passwords, or other secrets.

The dashboard is intentionally static: JavaScript refreshes `dashboard_data.json` every 60 seconds in the browser, while GitHub Actions updates the JSON about every 30 minutes.

## Local testing

Create `.env` from `.env.example`, install dependencies, and run:

```bash
pip install -r requirements.txt
python run_monitor.py
```

This performs one monitoring cycle and exits.
