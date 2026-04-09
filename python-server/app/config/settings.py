"""
Central place to read and store configuration values.
"""

from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.environ.get("MONGO_URI", "")
DB_NAME = os.environ.get("DB_NAME", "crypto_wallet_analyzer")
