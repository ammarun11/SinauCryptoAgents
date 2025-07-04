# CryptoAgents Telegram Bot Setup & Usage Guide

## Overview
CryptoAgents is a multi-agent LLM cryptocurrency trading framework. This guide covers how to set up and use the integrated Telegram bot for running agent-based crypto analyses directly from Telegram chat.

---

## Features
- Trigger full agent-based trading analyses via Telegram commands
- Specify symbol, date, and portfolio balance
- Receive concise trading tables and research team recommendations as chat messages
- Download full PDF and Markdown reports from Telegram
- Progress updates streamed during analysis
- Uses OpenAI GPT models (configurable)

---

## Requirements
- Python 3.10+
- OpenAI API key (for LLMs)
- Telegram Bot Token
- All dependencies in `requirements.txt`

---

## Setup Instructions

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd SinauCryptoAgents
```

### 2. Install Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Set Environment Variables
- **OpenAI API Key:**
  ```bash
  export OPENAI_API_KEY=sk-...
  ```
- **Telegram Bot Token:**
  ```bash
  export TELEGRAM_BOT_TOKEN=123456:ABC-...
  ```

You can add these to your `.env` or systemd service for persistence.

### 4. Configure Models (Optional)
Edit `cryptoagents/config.py` to set default LLMs:
- `quick_think_llm` (for shallow/fast analysis, e.g. `gpt-4o-mini`)
- `deep_think_llm` (for deep/complex analysis, e.g. `gpt-4o`)

---

## Running the Telegram Bot

```bash
python cli/telegram_bot.py
```

You should see:
```
CryptoAgents Telegram bot is running...
```

---

## Using the Bot on Telegram

### 1. Start a Chat
- Open Telegram and search for your bot (by username).
- Click **Start** or type `/start`.

### 2. Run an Analysis (Quick Command)
Send:
```
/analyze <symbol> <portfolio_usd> <date YYYY-MM-DD>
```
Example:
```
/analyze BTC 1000 2025-07-03
```

**Optional arguments:**
- Analysts (comma-separated): `market,social,news,fundamentals`
- Research depth: `1`, `2`, or `3`
- Shallow model: e.g. `gpt-4o-mini`
- Deep model: e.g. `gpt-4o`

Full example:
```
/analyze ETH 5000 2025-07-03 market,social 2 gpt-3.5-turbo gpt-4
```

### 3. Interactive Flow
- Type `/start` and follow the prompts to enter symbol, date, portfolio, analysts, and models step by step.

---

## What You Get
- **Progress updates** as the analysis runs
- **Trading summary table** and **Research Team Decision** as a chat message
- **Full PDF and Markdown reports** as downloadable files

---

## Model Support
- Default: OpenAI GPT-4o, GPT-4o-mini, GPT-3.5-turbo (set in config)
- You can override models per analysis via command arguments or interactive flow

---

## Troubleshooting
- Ensure both `OPENAI_API_KEY` and `TELEGRAM_BOT_TOKEN` are set in your environment
- For long analyses, wait for progress messages and final reports
- If you see errors, check logs and ensure your API keys are valid

---

## Example Output
```
| Action | Price Trigger (USD) | Amount (USD) | Condition/Note |
|--------|--------------------|--------------|----------------|
| Buy    | 98695.81058156    | 200.00   | If price dips 10% below current |
| Sell   | 120628.21293302   | 500.00   | If price surges 10% above current |
| Hold   | 109662.01175729        | 1000.00   | Default/No strong signal |

## Research Team Decision
Here’s my concise take: ...
```

---

## Advanced
- To run the CLI instead: `python cli/main.py analyze`
- To customize agent teams, research depth, or models, edit `cryptoagents/config.py` or use command arguments

---

## License
See `LICENSE` in the repository.
