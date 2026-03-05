import sys, types
# Python 3.13+ removed imghdr — shim it before tweepy import
if "imghdr" not in sys.modules:
    _m = types.ModuleType("imghdr"); _m.what = lambda *a, **kw: None
    sys.modules["imghdr"] = _m

import os
import tweepy
sys.path.append(os.path.abspath('.'))

import lib.twAuto as twAuto
from src.logs import logs
from lib.scraper.twitter_scraper import Twitter_Scraper
from src.config import get_config, get_credentials

config = get_config()
credentials = get_credentials()


def _find_chrome_binary():
    """Auto-detect Chrome/Chromium binary — exhaustive search for Render"""
    import subprocess

    # Check env first
    env_path = os.environ.get("CHROME_BINARY_PATH", "")
    if env_path and os.path.exists(env_path):
        return env_path

    # Known fixed paths
    candidates = [
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
        "/opt/google/chrome/google-chrome",
        "/opt/google/chrome/chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
    ]
    for path in candidates:
        if os.path.exists(path):
            print(f"[CHROME] Found at: {path}")
            return path

    # Try which command
    for name in ["google-chrome-stable","google-chrome","chromium","chromium-browser"]:
        try:
            result = subprocess.run(["which", name], capture_output=True, text=True)
            if result.returncode == 0:
                path = result.stdout.strip()
                print(f"[CHROME] which found: {path}")
                return path
        except Exception:
            pass

    # Last resort: find command
    try:
        result = subprocess.run(
            ["find", "/usr", "/opt", "-name", "google-chrome*", "-type", "f"],
            capture_output=True, text=True, timeout=10
        )
        lines = [l.strip() for l in result.stdout.strip().split("
") if l.strip()]
        if lines:
            print(f"[CHROME] find located: {lines[0]}")
            return lines[0]
    except Exception:
        pass

    print("[CHROME] WARNING: no binary found — selenium will try system default")
    return ""


class xBridge:
    def __init__(self):
        self.logs = logs()

        # Set CHROME_BINARY_PATH env so scraper + twAuto both pick it up
        chrome = _find_chrome_binary()
        if chrome:
            os.environ["CHROME_BINARY_PATH"] = chrome
            self.logs.log_info(f"Chrome binary: {chrome}")
        else:
            self.logs.log_info("Chrome binary: using system default")

        cookies_dir = config.get('cookies_path', '/data/cookies')
        os.makedirs(cookies_dir, exist_ok=True)
        self._cookies_file = os.path.join(cookies_dir, 'cookies.pkl')

        # Change working dir so twAuto finds cookies.pkl in /data
        self._orig_dir = os.getcwd()

        self.client_selenium_action = twAuto.twAuto(
            username=credentials["TWITTER_user_name"],
            email=credentials["TWITTER_email"],
            password=credentials["TWITTER_pwd"],
            chromeDriverMode="auto",
            pathType="xPath",
            headless=config.get('headless', True),
            debugMode=False,
            createCookies=True,
        )

        self.client_official = tweepy.Client(
            bearer_token=credentials["TWITTER_API_BEARER_TOKEN"],
            access_token=credentials["TWITTER_API_ACCESS_TOKEN"],
            access_token_secret=credentials["TWITTER_API_ACCESS_TOKEN_SECRET"],
            consumer_key=credentials["TWITTER_API_CONSUMER_KEY"],
            consumer_secret=credentials["TWITTER_API_CONSUMER_SECRET"],
        )
        self.client_selenium_read = None
        self.logs.log_info("xBridge initialized")

    def _init_read_client(self):
        self.client_selenium_read = Twitter_Scraper(
            mail=None,
            username=credentials['TWITTER_user_name'],
            password=credentials['TWITTER_pwd'],
            headless=config.get('headless', True),
        )

    def get_tweet_core(self, username=None, hashtag=None, count=5):
        def scrape():
            self.client_selenium_read.scrape_tweets(
                max_tweets=count,
                scrape_username=username,
                scrape_hashtag=hashtag,
            )
            return self.client_selenium_read.get_tweets_csv()

        if self.client_selenium_read is None or not self.client_selenium_read.login_bool:
            self._init_read_client()
            self.client_selenium_read.login()
            return scrape()
        else:
            try:
                return scrape()
            except Exception as e:
                self.logs.log_error("Scraper error, reinitializing: " + str(e))
                self._init_read_client()
                self.client_selenium_read.login()
                return scrape()

    def get_home_timeline(self, count=5):
        return self.get_tweet_core(count=count)

    def get_tweet_via_username(self, username, count=5):
        return self.get_tweet_core(username=username, count=count)

    def get_tweet_via_hashtag(self, hashtag, count=5):
        return self.get_tweet_core(hashtag=hashtag, count=count)

    def tweet_core(self, text, in_reply_to_tweet_id=None, quote_tweet_id=None):
        try:
            self.client_official.create_tweet(
                text=text,
                in_reply_to_tweet_id=in_reply_to_tweet_id,
                quote_tweet_id=quote_tweet_id
            )
        except Exception as e:
            self.logs.log_error("Fail to create tweet: " + str(e))

    def reply(self, in_reply_to_tweet_id, text, image_path=""):
        self.tweet_core(text, in_reply_to_tweet_id=in_reply_to_tweet_id)
        self.logs.log_info(f"Replied to {in_reply_to_tweet_id}: {text}", "bold red", "Action")

    def quote(self, quote_tweet_id, text, image_path=""):
        self.tweet_core(text, quote_tweet_id=quote_tweet_id)
        self.logs.log_info(f"Quoted {quote_tweet_id}: {text}", "bold red", "Action")

    def like(self, url):
        self.client_selenium_action.start()
        self.client_selenium_action.login()
        self.client_selenium_action.like(url=url)
        self.client_selenium_action.close()
        self.logs.log_info(f"Liked: {url}", "bold red", "Action")

    def tweet(self, text, in_reply_to_tweet_id=None, image_path="", quote_tweet_id=None):
        self.tweet_core(text, in_reply_to_tweet_id=in_reply_to_tweet_id, quote_tweet_id=quote_tweet_id)
        self.logs.log_info(f"Tweeted: {text}", "bold red", "Action")
