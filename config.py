import os

from dotenv import load_dotenv
load_dotenv() 
# Clés API (depuis .env)
API_KEY    = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
SYMBOL = "PF_ETHUSD"
INVESTMENT_USD = 10
LEVERAGE = 8
TIMEFRAMES = { 'M15': '15m', 'M5': '5m' }
LOOKBACK = 100
TICK_SIZE = 0.5
POLL_INTERVAL = 10  # en secondes
DB_PATH = "donnees/trading.db"