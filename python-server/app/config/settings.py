"""
Maintaining this folder for easy and repeated access of configuration file details
Basically a central place to read and store configuration values 
"""

from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.environ["MONGO_URI"]
if not MONGO_URI:
    raise ValueError("MONGO_URI is not set in .env!")
DB_NAME = os.environ["DB_NAME"]
if not DB_NAME:
    raise ValueError("DB_NAME is not set in the .env!")
