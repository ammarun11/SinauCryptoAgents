import os
import logging
from telegram import Update, InputFile, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from cli.main import run_analysis_headless, AnalystType
from cli.purchase_analysis import analyze_purchase_generic
from cryptoagents.config import CRYPTO_CONFIG
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

# Steps for purchase analysis flow
PURCHASE_STEPS = [
    "symbol",
    "fiat",
    "buy_date",
    "buy_price",
    "total_spent",
    "amount_bought",
    "sell_threshold",
    "buy_threshold"
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

    # If in purchase analysis flow
    if state.get("purchase_flow", False):
        purchase_step = state.get("purchase_step", 0)
        purchase_data = data

        try:
            if purchase_step == 0:  # Symbol
                purchase_data["symbol"] = text.upper()
                user_states[user_id] = {"purchase_flow": True, "purchase_step": 1, "data": purchase_data}
                await update.message.reply_text("Enter the fiat currency (e.g. IDR, USD):")
            elif purchase_step == 1:  # Fiat
                purchase_data["fiat"] = text.upper()
                user_states[user_id] = {"purchase_flow": True, "purchase_step": 2, "data": purchase_data}
                await update.message.reply_text("Enter the buy date (YYYY-MM-DD):")
            elif purchase_step == 2:  # Buy date
                try:
                    datetime.datetime.strptime(text, "%Y-%m-%d")
                    purchase_data["buy_date"] = text
                    user_states[user_id] = {"purchase_flow": True, "purchase_step": 3, "data": purchase_data}
                    await update.message.reply_text("Enter the buy price (in fiat per coin):")
                except ValueError:
                    await update.message.reply_text("Invalid date format. Please use YYYY-MM-DD:")
            elif purchase_step == 3:  # Buy price
                try:
                    purchase_data["buy_price"] = float(text)
                    user_states[user_id] = {"purchase_flow": True, "purchase_step": 4, "data": purchase_data}
                    await update.message.reply_text("Enter the total spent (in fiat):")
                except ValueError:
                    await update.message.reply_text("Buy price must be a number. Please enter again:")
            elif purchase_step == 4:  # Total spent
                try:
                    purchase_data["total_spent"] = float(text)
                    user_states[user_id] = {"purchase_flow": True, "purchase_step": 5, "data": purchase_data}
                    await update.message.reply_text("Enter the amount bought (in coin units):")
                except ValueError:
                    await update.message.reply_text("Total spent must be a number. Please enter again:")
            elif purchase_step == 5:  # Amount bought
                try:
                    purchase_data["amount_bought"] = float(text)
                    user_states[user_id] = {"purchase_flow": True, "purchase_step": 6, "data": purchase_data}
                    await update.message.reply_text("Enter the SELL threshold in % (default: 20):")
                except ValueError:
                    await update.message.reply_text("Amount bought must be a number. Please enter again:")
            elif purchase_step == 6:  # Sell threshold
                try:
                    if text.strip() == "":
                        purchase_data["sell_threshold"] = 20.0
                    else:
                        purchase_data["sell_threshold"] = float(text)
                    user_states[user_id] = {"purchase_flow": True, "purchase_step": 7, "data": purchase_data}
                    await update.message.reply_text("Enter the BUY threshold in % (default: -20):")
                except ValueError:
                    await update.message.reply_text("Sell threshold must be a number (or leave blank for default 20):")
            elif purchase_step == 7:  # Buy threshold
                try:
                    if text.strip() == "":
                        purchase_data["buy_threshold"] = -20.0
                    else:
                        purchase_data["buy_threshold"] = float(text)
                    # All data collected, run analysis
                    await update.message.reply_text("Analyzing your purchase... Please wait.", reply_markup=ReplyKeyboardRemove())
                    result = analyze_purchase_generic(
                        symbol=purchase_data["symbol"],
                        fiat=purchase_data["fiat"],
                        buy_date=purchase_data["buy_date"],
                        buy_price=purchase_data["buy_price"],
                        total_spent=purchase_data["total_spent"],
                        amount_bought=purchase_data["amount_bought"],
                        sell_threshold=purchase_data["sell_threshold"],
                        buy_threshold=purchase_data["buy_threshold"]
                    )
                    if "error" in result:
                        await update.message.reply_text(f"Error: {result['error']}")
                    else:
                        msg = (
                            f"Purchase Analysis for {result['symbol']}/{result['fiat']}\n"
                            f"------------------------------\n"
                            f"Buy Date: {result['buy_date']}\n"
                            f"Buy Price: {result['buy_price']} {result['fiat']}\n"
                            f"Amount Bought: {result['amount_bought']} {result['symbol']}\n"
                            f"Total Spent: {result['total_spent']} {result['fiat']}\n\n"
                            f"Current Price: {result['current_price']:.8f} {result['fiat']}\n"
                            f"Current Value: {result['current_value']:.2f} {result['fiat']}\n"
                            f"Profit/Loss: {result['profit_loss']:+.2f} {result['fiat']} ({result['percent_change']:+.2f}%)\n\n"
                            f"Thresholds: Sell if >{result['sell_threshold']}%, Buy if <{result['buy_threshold']}%, else Hold\n\n"
                            f"Recommendation: {result['recommendation']}"
                        )
                        await update.message.reply_text(msg)
                    user_states[user_id] = {"step": 0, "data": {}}  # Reset state
                except ValueError:
                    await update.message.reply_text("Buy threshold must be a number (or leave blank for default -20):")
            else:
                await update.message.reply_text("Type /analyze_purchase to start a new purchase analysis.")
        except Exception as e:
            await update.message.reply_text(f"Unexpected error: {e}")
            user_states[user_id] = {"step": 0, "data": {}}
        return

    # Default: main analysis flow
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

async def analyze_purchase_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = {"purchase_flow": True, "purchase_step": 0, "data": {}}
    await update.message.reply_text("Let's analyze your crypto purchase!\nPlease enter the coin symbol (e.g. SHIB, BTC):")

async def analyze_purchase_bulk_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 6:
        await update.message.reply_text(
            "Usage: /analyze_purchase_bulk <symbol> <fiat> <buy_date YYYY-MM-DD> <buy_price> <total_spent> <amount_bought> [sell_threshold] [buy_threshold]\n"
            "Example: /analyze_purchase_bulk SHIB IDR 2025-07-04 0.189136 9774720 51680912 20 -20"
        )
        return
    try:
        symbol = args[0].upper()
        fiat = args[1].upper()
        buy_date = args[2]
        buy_price = float(args[3])
        total_spent = float(args[4])
        amount_bought = float(args[5])
        sell_threshold = float(args[6]) if len(args) > 6 else 20.0
        buy_threshold = float(args[7]) if len(args) > 7 else -20.0
    except Exception as e:
        await update.message.reply_text(f"Invalid arguments: {e}")
        return

    # Use the purchase as the context for a real agent-based analysis
    # Use the buy date as the analysis date, and total_spent as portfolio value (in fiat)
    # Use default analysts and models for now, or allow user to customize in future
    await update.message.reply_text(
        f"Running in-depth agent-based analysis for your purchase of {symbol} on {buy_date}... This may take a few minutes."
    )

    analysts = [AnalystType.MARKET.value, AnalystType.SOCIAL.value, AnalystType.NEWS.value, AnalystType.FUNDAMENTALS.value]
    research_depth = 3
    shallow_model = "gpt-4o-mini"
    deep_model = "gpt-4o"
    fiat_currency = fiat

    progress_msgs = []
    async def send_progress(msg):
        progress_msgs.append(msg)
        if len(progress_msgs) % 3 == 0:
            await update.message.reply_text(f"Progress: {msg}")

    loop = asyncio.get_running_loop()
    try:
        pdf_path, md_path, summary_path = await asyncio.to_thread(
            run_analysis_headless,
            symbol,
            total_spent,
            buy_date,
            analysts,
            research_depth,
            shallow_model,
            deep_model,
            fiat_currency,
            send_progress
        )
        await update.message.reply_text("Analysis complete! Sending reports...")
        # Send summary table as text if possible
        if summary_path and os.path.exists(summary_path):
            with open(summary_path, "r") as f:
                summary_text = f.read()
            await update.message.reply_text(f"Summary Table:\n{summary_text}")
            # Also send as document
            with open(summary_path, "rb") as f:
                await update.message.reply_document(document=InputFile(f, filename=os.path.basename(summary_path)))
        # Send markdown file
        if md_path and os.path.exists(md_path):
            with open(md_path, "rb") as f:
                await update.message.reply_document(document=InputFile(f, filename=os.path.basename(md_path)))
        # Send PDF file
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                await update.message.reply_document(document=InputFile(f, filename=os.path.basename(pdf_path)))
    except Exception as e:
        await update.message.reply_text(f"Error running agent-based analysis: {e}")

async def analyze_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /analyze <symbol> <portfolio> <date YYYY-MM-DD> [analysts] [research_depth] [shallow_model] [deep_model] [fiat_currency]")
        return
    symbol = args[0].upper()
    try:
        portfolio = float(args[1])
    except ValueError:
        await update.message.reply_text("Portfolio value must be a number.")
        return
    date = args[2] if len(args) > 2 else datetime.datetime.now().strftime("%Y-%m-%d")
    analysts = args[3].split(",") if len(args) > 3 else [AnalystType.MARKET.value, AnalystType.SOCIAL.value, AnalystType.NEWS.value, AnalystType.FUNDAMENTALS.value]
    research_depth = int(args[4]) if len(args) > 4 else 3
    shallow_model = args[5] if len(args) > 5 else "gpt-4o-mini"
    deep_model = args[6] if len(args) > 6 else "gpt-4o"
    # Use config default for fiat_currency if not provided
    fiat_currency = args[7] if len(args) > 7 else CRYPTO_CONFIG.get("fiat_currency", "USD")

    await update.message.reply_text(f"Running analysis for {symbol} ({portfolio} {fiat_currency}, {date})... This may take a while.")

    progress_msgs = []
    async def send_progress(msg):
        progress_msgs.append(msg)
        if len(progress_msgs) % 3 == 0:
            await update.message.reply_text(f"Progress: {msg}")

    loop = asyncio.get_running_loop()
    try:
        # run_analysis_headless is sync, so run in thread
        pdf_path, md_path, summary_path = await asyncio.to_thread(
            run_analysis_headless,
            symbol,
            portfolio,
            date,
            analysts,
            research_depth,
            shallow_model,
            deep_model,
            fiat_currency,
            send_progress
        )
        await update.message.reply_text("Analysis complete! Sending reports...")
        # Send summary table as text if possible
        if summary_path and os.path.exists(summary_path):
            with open(summary_path, "r") as f:
                summary_text = f.read()
            await update.message.reply_text(f"Summary Table:\n{summary_text}")
            # Also send as document
            with open(summary_path, "rb") as f:
                await update.message.reply_document(document=InputFile(f, filename=os.path.basename(summary_path)))
        # Send markdown file
        if md_path and os.path.exists(md_path):
            with open(md_path, "rb") as f:
                await update.message.reply_document(document=InputFile(f, filename=os.path.basename(md_path)))
        # Send PDF file
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                await update.message.reply_document(document=InputFile(f, filename=os.path.basename(pdf_path)))
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("analyze", analyze_cmd))
    app.add_handler(CommandHandler("analyze_purchase", analyze_purchase_cmd))
    app.add_handler(CommandHandler("analyze_purchase_bulk", analyze_purchase_bulk_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("CryptoAgents Telegram bot is running...")
    app.run_polling()
