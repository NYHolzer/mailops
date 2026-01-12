# MailOps

MailOps is a powerful local email automation tool designed to take control of your Gmail inbox. It allows you to define rules to automatically print, archive, or delete emails, and even integrate with external tools like ClickUp.

## Features

- **Daily Automation**: Automatically process emails from the last 24 hours.
- **Safety Check**: Interactive review of planned actions before execution.
- **Auto-Printing**: Automatically print improved PDFs of emails (e.g., invoices).
- **Bulk Search & Actions**: Powerful CLI for filtering and cleaning up (archive/delete).
- **Web Dashboard**: Local UI for easy rule configuration.
- **ClickUp Integration**: Create tasks directly from your inbox.
- **Smart Rules**: Supports "Exclusions" (e.g., From Amazon but NOT an Order).

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/mailops.git
    cd mailops
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install the package (editable mode):**
    ```bash
    pip install -e .
    ```
    *This registers the `mailops` command in your shell.*

## Usage

### 1. Configuration (Web UI)
The easiest way to configure rules is using the Web Dashboard.

```bash
mailops ui
# Open http://localhost:8000 in your browser
```

- **Set Printer Name**: The system name of your printer (e.g., `HP_OfficeJet`).
- **Add Rules**: Create rules to match emails.
    - **From Domain**: `example.com`
    - **Subject Excludes**: `Sale` (Matches "Invoice" but not "Huge Sale")
    - **Action**: `print`, `archive`, `delete`, or `clickup`.

### 2. Daily Automation
Run this command daily (e.g., via cron) or manually to clean your inbox.

```bash
mailops run
```

- It will scan the last 24 hours of emails.
- It will show a table of **Planned Actions**.
- It asks for confirmation before doing anything.
- Use `--dry-run` to strictly see what would happen without asking.
- Use `--yes` to skip confirmation (for cron jobs).

### 3. Bulk Search & Actions
Perform ad-hoc deep cleaning.

```bash
# Search for emails from a domain
mailops search --from "newsletter.com"

# Archive them (dry run first)
mailops search --from "newsletter.com" --archive --dry-run

# Delete strict
mailops search --days 30 --delete
```

### 4. ClickUp Integration
To enable ClickUp task creation:

1.  Get your API Key (Personal Settings -> Apps) and List ID (URL of the list).
2.  Export them in your shell:
    ```bash
    export CLICKUP_API_KEY="pk_..."
    export CLICKUP_LIST_ID="12345"
    ```
3.  Create a rule with action `clickup`.

## Development

**Running Tests:**
```bash
pytest
```
