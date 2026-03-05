import os
import sys
sys.path.append(os.path.abspath('.'))
import json
from dotenv import load_dotenv

# /data is the persistent disk mount on Render
DATA_DIR = os.getenv("DATA_DIR", "/data")

def ensure_data_dirs():
    """Create all required /data subdirectories on startup"""
    dirs = [
        os.path.join(DATA_DIR, "logs"),
        os.path.join(DATA_DIR, "dialog"),
        os.path.join(DATA_DIR, "tweets"),
        os.path.join(DATA_DIR, "cookies"),
        os.path.join(DATA_DIR, "memory"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)

def get_config():
    with open("config.json") as f:
        cfg = json.load(f)
    # Override paths to use DATA_DIR (works locally too)
    cfg["log_path"]    = os.path.join(DATA_DIR, "logs", "gnosis.log")
    cfg["dialog_path"] = os.path.join(DATA_DIR, "dialog", "dialog.jsonl")
    cfg["tweets_path"] = os.path.join(DATA_DIR, "tweets")
    cfg["cookies_path"]= os.path.join(DATA_DIR, "cookies")
    cfg["memory_path"] = os.path.join(DATA_DIR, "memory", "memory.json")
    return cfg

def get_credentials():
    load_dotenv()
    return {
        "ANTHROPIC_API_KEY":              os.getenv("ANTHROPIC_API_KEY"),
        "OPENAI_API_KEY":                 os.getenv("OPENAI_API_KEY"),
        "TWITTER_API_CONSUMER_KEY":       os.getenv("TWITTER_API_CONSUMER_KEY"),
        "TWITTER_API_CONSUMER_SECRET":    os.getenv("TWITTER_API_CONSUMER_SECRET"),
        "TWITTER_API_BEARER_TOKEN":       os.getenv("TWITTER_API_BEARER_TOKEN"),
        "TWITTER_API_ACCESS_TOKEN":       os.getenv("TWITTER_API_ACCESS_TOKEN"),
        "TWITTER_API_ACCESS_TOKEN_SECRET":os.getenv("TWITTER_API_ACCESS_TOKEN_SECRET"),
        "TWITTER_user_name": os.getenv("TWITTER_user_name"),
        "TWITTER_email":     os.getenv("TWITTER_email"),
        "TWITTER_pwd":       os.getenv("TWITTER_pwd"),
        "TWITTER_phone":     os.getenv("TWITTER_phone", ""),
    }

def get_prompt():
    with open("data/prompt.json") as f:
        return json.load(f)
