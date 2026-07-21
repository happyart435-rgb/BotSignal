import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

PAIR_MAP = {
    "EUR/USD": "EURUSD",
    "GBP/USD": "GBPUSD",
    "USD/JPY": "USDJPY",
    "AUD/USD": "AUDUSD",
    "USD/CAD": "USDCAD",
    "USD/CHF": "USDCHF",
    "NZD/USD": "NZDUSD",
    "EUR/GBP": "EURGBP",
    "EUR/JPY": "EURJPY",
    "GBP/JPY": "GBPJPY",
    "AUD/JPY": "AUDJPY",
    "EUR/AUD": "EURAUD",
    "GBP/CAD": "GBPCAD",
    "CHF/JPY": "CHFJPY",
    "CAD/JPY": "CADJPY",
    "EUR/CAD": "EURCAD",
    "AUD/CAD": "AUDCAD",
    "GBP/AUD": "GBPAUD",
    "GBP/CHF": "GBPCHF",
    "NZD/JPY": "NZDJPY"
}
