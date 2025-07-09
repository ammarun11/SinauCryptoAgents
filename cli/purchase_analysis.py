import datetime
from typing import Optional, Tuple, Dict
from cryptoagents.dataflows.coinmarketcap_utils import CoinMarketCapAPI

def analyze_purchase_generic(
    symbol: str,
    fiat: str,
    buy_date: str,
    buy_price: float,
    total_spent: float,
    amount_bought: float,
    sell_threshold: float = 20.0,
    buy_threshold: float = -20.0,
    api_key: Optional[str] = None
) -> Dict:
    """
    Analyze a crypto purchase and provide recommendation.

    Returns a dict with all relevant info and recommendation.
    """
    # Fetch current price
    cmc = CoinMarketCapAPI(api_key=api_key, fiat_currency=fiat)
    latest_quote = cmc.get_latest_quote([symbol])
    # Try to extract price in the requested fiat
    try:
        crypto_id = cmc.get_crypto_id(symbol)
        price = latest_quote['data'][str(crypto_id)]['quote'][fiat]['price']
    except Exception as e:
        return {
            "error": f"Could not fetch current price for {symbol}/{fiat}: {e}"
        }

    # Calculate current value, profit/loss, percent change
    current_value = amount_bought * price
    profit_loss = current_value - total_spent
    percent_change = ((current_value - total_spent) / total_spent) * 100 if total_spent != 0 else 0

    # Recommendation logic
    if percent_change >= sell_threshold:
        recommendation = "SELL"
    elif percent_change <= buy_threshold:
        recommendation = "BUY"
    else:
        recommendation = "HOLD"

    return {
        "symbol": symbol.upper(),
        "fiat": fiat.upper(),
        "buy_date": buy_date,
        "buy_price": buy_price,
        "total_spent": total_spent,
        "amount_bought": amount_bought,
        "current_price": price,
        "current_value": current_value,
        "profit_loss": profit_loss,
        "percent_change": percent_change,
        "sell_threshold": sell_threshold,
        "buy_threshold": buy_threshold,
        "recommendation": recommendation,
    }