import os
import logging
from telegram import Update, InputFile, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from cli.main import run_analysis_headless, AnalystType
import datetime
import asyncio

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable not set. Please set it before running the bot.")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Per-user state for interactive flow
user_states = {}

# Steps for the interactive flow
STEPS = [
    "symbol",
    "date",
    "portfolio",
    "analysts",
    "research_depth",
    "shallow_model",
    "deep_model"
]

ANALYST_OPTIONS = [
    ("Market", AnalystType.MARKET.value),
    ("Social", AnalystType.SOCIAL.value),
    ("News", AnalystType.NEWS.value),
    ("Fundamentals", AnalystType.FUNDAMENTALS.value)
]

MODEL_OPTIONS = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo", "gpt-4"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = {"step": 0, "data": {}}
    await update.message.reply_text(
        "Welcome to CryptoAgents Telegram Bot!\nLet's start your analysis.\nPlease enter the cryptocurrency symbol (e.g. BTC):"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    state = user_states.get(user_id, {"step": 0, "data": {}})
    step = state["step"]
    data = state["data"]

    if step == 0:  # Symbol
        data["symbol"] = text.upper()
        user_states[user_id] = {"step": 1, "data": data}
        await update.message.reply_text("Enter the analysis date (YYYY-MM-DD):")
    elif step == 1:  # Date
        try:
            datetime.datetime.strptime(text, "%Y-%m-%d")
            data["date"] = text
            user_states[user_id] = {"step": 2, "data": data}
            await update.message.reply_text("Enter your portfolio value in USD (e.g. 1000):")
        except ValueError:
            await update.message.reply_text("Invalid date format. Please use YYYY-MM-DD:")
    elif step == 2:  # Portfolio
        try:
            data["portfolio"] = float(text)
            user_states[user_id] = {"step": 3, "data": data}
            analyst_names = [a[0] for a in ANALYST_OPTIONS]
            reply_markup = ReplyKeyboardMarkup([[name] for name in analyst_names], one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text(
                "Select analysts (send one at a time, type 'done' when finished):",
                reply_markup=reply_markup
            )
            data["analysts_selected"] = []
        except ValueError:
            await update.message.reply_text("Portfolio value must be a number. Please enter again:")
    elif step == 3:  # Analysts
        if text.lower() == "done":
            if not data["analysts_selected"]:
                await update.message.reply_text("Please select at least one analyst.")
                return
            user_states[user_id] = {"step": 4, "data": data}
            await update.message.reply_text(
                "Select research depth (1=Shallow, 2=Medium, 3=Deep):",
                reply_markup=ReplyKeyboardRemove()
            )
        elif text in [a[0] for a in ANALYST_OPTIONS]:
            analyst_val = [a[1] for a in ANALYST_OPTIONS if a[0] == text][0]
            if analyst_val not in data["analysts_selected"]:
                data["analysts_selected"].append(analyst_val)
            await update.message.reply_text(f"Added {text}. Type another or 'done' to finish.")
        else:
            await update.message.reply_text("Invalid analyst. Please select from the keyboard or type 'done'.")
    elif step == 4:  # Research depth
        try:
            depth = int(text)
            if depth not in [1, 2, 3]:
                raise ValueError
            data["research_depth"] = depth
            user_states[user_id] = {"step": 5, "data": data}
            reply_markup = ReplyKeyboardMarkup([[m] for m in MODEL_OPTIONS], one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text("Select shallow (quick) model:", reply_markup=reply_markup)
        except ValueError:
            await update.message.reply_text("Please enter 1, 2, or 3 for research depth:")
    elif step == 5:  # Shallow model
        if text not in MODEL_OPTIONS:
            await update.message.reply_text("Invalid model. Please select from the keyboard:")
            return
        data["shallow_model"] = text
        user_states[user_id] = {"step": 6, "data": data}
        reply_markup = ReplyKeyboardMarkup([[m] for m in MODEL_OPTIONS], one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("Select deep (complex) model:", reply_markup=reply_markup)
    elif step == 6:  # Deep model
        if text not in MODEL_OPTIONS:
            await update.message.reply_text("Invalid model. Please select from the keyboard:")
            return
        data["deep_model"] = text
        user_states[user_id] = {"step": 7, "data": data}
        await update.message.reply_text("Running analysis... This may take a while.", reply_markup=ReplyKeyboardRemove())
        # Run the full analysis (headless)
        try:
            pdf_path, markdown_path, summary_path = run_analysis_headless(
                ticker=data["symbol"],
                portfolio_usd=data["portfolio"],
                analysis_date=data["date"],
                analysts=data["analysts_selected"],
                research_depth=data["research_depth"],
                shallow_model=data["shallow_model"],
                deep_model=data["deep_model"]
            )
            await update.message.reply_text("Analysis complete! Sending reports...")
            if summary_path:
                with open(summary_path, "rb") as f:
                    await update.message.reply_document(document=InputFile(f, filename=os.path.basename(summary_path)))
            if markdown_path:
                with open(markdown_path, "rb") as f:
                    await update.message.reply_document(document=InputFile(f, filename=os.path.basename(markdown_path)))
            if pdf_path:
                with open(pdf_path, "rb") as f:
                    await update.message.reply_document(document=InputFile(f, filename=os.path.basename(pdf_path)))
        except Exception as e:
            await update.message.reply_text(f"Error running analysis: {e}")
        user_states[user_id] = {"step": 0, "data": {}}  # Reset state
    else:
        await update.message.reply_text("Type /start to begin a new analysis.")

async def analyze_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("Usage: /analyze <symbol> <portfolio_usd> <date YYYY-MM-DD> [analysts] [research_depth] [shallow_model] [deep_model]\nExample: /analyze BTC 1000 2025-07-03")
        return
    symbol = args[0].upper()
    try:
        portfolio_usd = float(args[1])
    except ValueError:
        await update.message.reply_text("Portfolio value must be a number.")
        return
    analysis_date = args[2]
    try:
        datetime.datetime.strptime(analysis_date, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text("Date must be in YYYY-MM-DD format.")
        return
    # Import config for defaults
    from cryptoagents.config import CRYPTO_CONFIG
    from cli.main import AnalystType
    default_analysts = [AnalystType.MARKET.value, AnalystType.SOCIAL.value, AnalystType.NEWS.value, AnalystType.FUNDAMENTALS.value]
    analysts = default_analysts
    research_depth = CRYPTO_CONFIG.get("max_debate_rounds", 1)
    shallow_model = CRYPTO_CONFIG.get("quick_think_llm", "gpt-4o-mini")
    deep_model = CRYPTO_CONFIG.get("deep_think_llm", "gpt-4o")
    if len(args) > 3:
        # Analysts as comma-separated string
        analysts = [a.strip() for a in args[3].split(",") if a.strip()]
    if len(args) > 4:
        try:
            research_depth = int(args[4])
        except ValueError:
            pass
    if len(args) > 5:
        shallow_model = args[5]
    if len(args) > 6:
        deep_model = args[6]
    await update.message.reply_text(f"Running analysis for {symbol} (${portfolio_usd}, {analysis_date})... This may take a while.")

    # Progress callback for streaming updates
    async def send_progress(msg):
        try:
            await update.effective_message.reply_text(f"[Progress] {msg}")
        except Exception:
            pass
    loop = asyncio.get_event_loop()
    def progress_callback(msg):
        loop.create_task(send_progress(msg))

    try:
        from cli.main import run_analysis_headless
        pdf_path, markdown_path, summary_path = run_analysis_headless(
            ticker=symbol,
            portfolio_usd=portfolio_usd,
            analysis_date=analysis_date,
            analysts=analysts,
            research_depth=research_depth,
            shallow_model=shallow_model,
            deep_model=deep_model,
            progress_callback=progress_callback
        )
        await update.message.reply_text("Analysis complete! Sending reports...")

        # Extract summary table and Research Team Decision from markdown report
        summary_text = None
        research_decision = None
        if markdown_path:
            with open(markdown_path, "r") as f:
                md = f.read()
            # Extract the first markdown table (summary table)
            import re
            table_match = re.search(r'(\| Action \|[\s\S]+?\| Default/No strong signal \|)', md)
            if table_match:
                summary_text = table_match.group(1)
            # Extract the Research Team Decision section
            research_match = re.search(r'(## Research Team Decision[\s\S]+?)(?:\n## |\Z)', md)
            if research_match:
                research_decision = research_match.group(1).strip()
        # Send as chat message
        if summary_text or research_decision:
            msg = ''
            if summary_text:
                msg += f"{summary_text}\n\n"
            if research_decision:
                msg += research_decision
            await update.message.reply_text(msg, parse_mode="Markdown")
        # Continue sending files as before
        if summary_path:
            with open(summary_path, "rb") as f:
                await update.message.reply_document(document=InputFile(f, filename=os.path.basename(summary_path)))
        if markdown_path:
            with open(markdown_path, "rb") as f:
                await update.message.reply_document(document=InputFile(f, filename=os.path.basename(markdown_path)))
        if pdf_path:
            with open(pdf_path, "rb") as f:
                await update.message.reply_document(document=InputFile(f, filename=os.path.basename(pdf_path)))
    except Exception as e:
        await update.message.reply_text(f"Error running analysis: {e}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("analyze", analyze_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("CryptoAgents Telegram bot is running...")
    app.run_polling()
