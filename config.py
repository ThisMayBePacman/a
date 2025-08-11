import os

from dotenv import load_dotenv
load_dotenv() 
# Clés API (depuis .env)
API_KEY    = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
SYMBOL = "PF_ETHUSD"
INVESTMENT_USD = 12
LEVERAGE = 8
TIMEFRAMES = { 'M15': '15m', 'M5': '5m' }
LOOKBACK = 100
TICK_SIZE = 0.5
POLL_INTERVAL = 10  # en secondes
DB_PATH = "donnees/trading.db"

# Sélection de stratégie au runtime
STRATEGY: str | None = None   # None ou "trailing_sl_only" | "trailing_sl_and_tp"
STRATEGY_PARAMS: dict = {}    # ex: {"theta": 0.5, "rho": 1.0}