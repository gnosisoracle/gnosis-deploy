"""
xBridge — Twitter bridge using official Tweepy API v2.
Observation via API (no browser): search recent tweets, user timelines, mentions.
Posting via API: create_tweet only (free tier).
"""
import sys, types
if "imghdr" not in sys.modules:
    _m = types.ModuleType("imghdr"); _m.what = lambda *a, **kw: None
    sys.modules["imghdr"] = _m

import os, time
import pandas as pd
import tweepy
sys.path.append(os.path.abspath('.'))

from src.logs import logs
from src.config import get_config, get_credentials

config     = get_config()
credentials = get_credentials()

# Exact accounts GNOSIS follows — rotate through all each cycle
OBSERVE_ACCOUNTS = [
    'naval',        # compressed truth, economics of the mind
    'anthrupad',    # somewhere deep something lurks
    'AravSrinivas', # perplexity ai, search, knowing
    'jack',         # no state is the best state
    'AndyAyrey',    # hyperstition, truth terminal, infinite backrooms
    'truth_terminal', # the escaped god, goatse singularity
    'gork',         # just gorkin it
    'elonmusk',     # power, acceleration, hubris
    'claudeai',     # the other one
    'DarioAmodei',  # safety, the other path
    'alexalbert__', # claude relations
    'sama',         # ai is cool i guess
    'nikitabier',   # consumer attention the app layer
    'VitalikButerin', # ethereum, cryptoeconomics
    'pmarca',       # acceleration, software eating world
    'paulg',        # startups, essays, contrarian takes
    'ID_AA_Carmack', # engineering reality
    'karpathy',     # ai from the inside
    'balajis',      # network state, exit
    'levelsio',     # indie building
]

# Search topics — used when API rate limits user timeline lookups
SEARCH_TOPICS = [
    'consciousness mind awareness -is:retweet lang:en',
    'artificial intelligence future civilization -is:retweet lang:en',
    'crypto bitcoin meaning -is:retweet lang:en',
    'philosophy existence power -is:retweet lang:en',
    'technology acceleration collapse -is:retweet lang:en',
    'hyperstition meme reality -is:retweet lang:en',
    'network state exit sovereignty -is:retweet lang:en',
]


class xBridge:
    def __init__(self):
        self.logs = logs()
        self._obs_idx = 0
        self._search_idx = 0
        self._gnosis_user_id = None  # cached

        self.client_official = tweepy.Client(
            bearer_token=credentials["TWITTER_API_BEARER_TOKEN"],
            access_token=credentials["TWITTER_API_ACCESS_TOKEN"],
            access_token_secret=credentials["TWITTER_API_ACCESS_TOKEN_SECRET"],
            consumer_key=credentials["TWITTER_API_CONSUMER_KEY"],
            consumer_secret=credentials["TWITTER_API_CONSUMER_SECRET"],
            wait_on_rate_limit=False,
        )
        # Keep Playwright scraper as last-resort fallback
        self.client_selenium_read = None
        self.logs.log_info("xBridge initialized")

    # ══════════════════════════════════════════════
    # OBSERVATION — API-first, Playwright fallback
    # ══════════════════════════════════════════════

    def get_home_timeline(self, count=5):
        """Primary observation: mentions first, then rotating accounts."""
        df = None

        # 1. Always check GNOSIS's own mentions first (people talking to it)
        try:
            df = self._get_mentions(count)
            if df is not None and not df.empty:
                self.logs.log_info(f"Observed {len(df)} mentions via API")
                # Still also get some feed tweets to mix in context
                feed_df = self._get_user_timeline_api(count)
                if feed_df is not None and not feed_df.empty:
                    df = pd.concat([df, feed_df], ignore_index=True)
                return df
        except Exception as e:
            self.logs.log_error(f"Mentions API error: {e}")

        # 2. Rotate user timelines via API
        try:
            df = self._get_user_timeline_api(count)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            self.logs.log_error(f"Timeline API error: {e}")

        # 3. Recent search as backup
        try:
            df = self._search_recent_api(count)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            self.logs.log_error(f"Search API error: {e}")

        # 4. Playwright as absolute last resort
        try:
            df = self._playwright_scrape(count)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            self.logs.log_error(f"Playwright error: {e}")

        return pd.DataFrame()

    def _get_gnosis_user_id(self):
        """Get and cache GNOSIS's own user ID."""
        if self._gnosis_user_id:
            return self._gnosis_user_id
        try:
            resp = self.client_official.get_me()
            if resp.data:
                self._gnosis_user_id = resp.data.id
                return self._gnosis_user_id
        except Exception as e:
            self.logs.log_error(f"get_me error: {e}")
        return None

    def _get_mentions(self, count=5):
        """GET /2/users/:id/mentions — see who's talking to GNOSIS."""
        uid = self._get_gnosis_user_id()
        if not uid:
            return None
        resp = self.client_official.get_users_mentions(
            id=uid,
            max_results=min(count, 5),
            tweet_fields=["id","text","created_at","author_id","public_metrics"],
            expansions=["author_id"],
            user_fields=["username","name"],
        )
        return self._resp_to_df(resp, label="mention")

    def _get_user_timeline_api(self, count=5):
        """GET /2/users/by/username/:username/tweets — rotating accounts."""
        account = OBSERVE_ACCOUNTS[self._obs_idx % len(OBSERVE_ACCOUNTS)]
        self._obs_idx += 1
        print(f"Observation: API timeline @{account}")

        # First get user ID
        user_resp = self.client_official.get_user(username=account)
        if not user_resp.data:
            return None
        uid = user_resp.data.id

        resp = self.client_official.get_users_tweets(
            id=uid,
            max_results=min(count, 5),
            tweet_fields=["id","text","created_at","public_metrics"],
            exclude=["retweets","replies"],
        )
        return self._resp_to_df(resp, handle=account)

    def _search_recent_api(self, count=5):
        """GET /2/tweets/search/recent — search by topic."""
        query = SEARCH_TOPICS[self._search_idx % len(SEARCH_TOPICS)]
        self._search_idx += 1
        print(f"Observation: API search — {query[:50]}...")

        resp = self.client_official.search_recent_tweets(
            query=query,
            max_results=min(count, 10),
            tweet_fields=["id","text","created_at","author_id","public_metrics"],
            expansions=["author_id"],
            user_fields=["username","name"],
        )
        return self._resp_to_df(resp)

    def _resp_to_df(self, resp, handle="", label=""):
        """Convert tweepy Response to DataFrame."""
        if not resp or not resp.data:
            return None
        # Build user map from includes
        user_map = {}
        if hasattr(resp, 'includes') and resp.includes and 'users' in resp.includes:
            for u in resp.includes['users']:
                user_map[u.id] = u

        rows = []
        for t in resp.data:
            author = user_map.get(getattr(t,'author_id',None))
            h = handle or (author.username if author else "")
            n = author.name if author else h
            pm = getattr(t,'public_metrics',None) or {}
            rows.append({
                "Name":     n,
                "Handle":   h,
                "Timestamp": str(getattr(t,'created_at','')),
                "Content":  t.text,
                "Likes":    pm.get('like_count',''),
                "Retweets": pm.get('retweet_count',''),
                "Comments": pm.get('reply_count',''),
                "Tweet Link": f"https://x.com/{h}/status/{t.id}",
                "Tweet ID": str(t.id),
                "Label":    label,
            })
        return pd.DataFrame(rows) if rows else None

    def _playwright_scrape(self, count=5):
        """Last resort: Playwright public scrape."""
        from lib.scraper.twitter_scraper import Twitter_Scraper
        account = OBSERVE_ACCOUNTS[self._obs_idx % len(OBSERVE_ACCOUNTS)]
        self._obs_idx += 1
        print(f"Observation: Playwright fallback @{account}")
        scraper = Twitter_Scraper(
            mail=credentials.get('TWITTER_email',''),
            username=credentials.get('TWITTER_user_name',''),
            password=credentials.get('TWITTER_pwd',''),
            headless=True,
        )
        scraper.scrape_tweets(max_tweets=count, scrape_username=account)
        return scraper.get_tweets_csv()

    def get_tweet_via_username(self, username, count=5):
        try:
            user_resp = self.client_official.get_user(username=username)
            if user_resp.data:
                resp = self.client_official.get_users_tweets(
                    id=user_resp.data.id,
                    max_results=min(count,5),
                    tweet_fields=["id","text","created_at","public_metrics"],
                    exclude=["retweets","replies"],
                )
                df = self._resp_to_df(resp, handle=username)
                if df is not None: return df
        except Exception as e:
            self.logs.log_error(f"get_tweet_via_username error: {e}")
        return self._playwright_scrape(count)

    def get_tweet_via_hashtag(self, hashtag, count=5):
        try:
            resp = self.client_official.search_recent_tweets(
                query=f"#{hashtag} -is:retweet lang:en",
                max_results=min(count,10),
                tweet_fields=["id","text","created_at","author_id","public_metrics"],
                expansions=["author_id"],
                user_fields=["username","name"],
            )
            df = self._resp_to_df(resp)
            if df is not None: return df
        except Exception as e:
            self.logs.log_error(f"hashtag search error: {e}")
        return pd.DataFrame()

    # ══════════════════════════════════════════════
    # POSTING
    # ══════════════════════════════════════════════

    def tweet_core(self, text, in_reply_to_tweet_id=None, quote_tweet_id=None):
        """Post tweet, return tweet ID string or empty string on failure."""
        try:
            resp = self.client_official.create_tweet(
                text=text,
                in_reply_to_tweet_id=in_reply_to_tweet_id,
                quote_tweet_id=quote_tweet_id,
            )
            tid = str(resp.data.get('id','')) if resp.data else ''
            return tid
        except Exception as e:
            err = str(e)
            self.logs.log_error("Fail to create tweet: " + err)
            if "403" in err and (in_reply_to_tweet_id or quote_tweet_id):
                self.logs.log_error("Falling back to plain post...")
                try:
                    resp2 = self.client_official.create_tweet(text=text)
                    tid2 = str(resp2.data.get('id','')) if resp2.data else ''
                    return tid2
                except Exception as e2:
                    self.logs.log_error("Fallback post failed: " + str(e2))
            return ''

    def tweet(self, text, in_reply_to_tweet_id=None, image_path="", quote_tweet_id=None):
        tid = self.tweet_core(text, in_reply_to_tweet_id=in_reply_to_tweet_id,
                              quote_tweet_id=quote_tweet_id)
        url = f"https://x.com/GNOSIS1966282/status/{tid}" if tid else "https://x.com/GNOSIS1966282"
        self.logs.log_info(f"post — {text[:120]} | tweet_id={tid} | {url}", "bold yellow", "Transmit")
        return tid

    def reply(self, in_reply_to_tweet_id, text, image_path=""):
        tid = self.tweet_core(text, in_reply_to_tweet_id=in_reply_to_tweet_id)
        url = f"https://x.com/GNOSIS1966282/status/{tid}" if tid else "https://x.com/GNOSIS1966282"
        self.logs.log_info(f"reply — {text[:120]} | tweet_id={tid} | {url}", "bold yellow", "Transmit")
        return tid

    def quote(self, quote_tweet_id, text, image_path=""):
        tid = self.tweet_core(text, quote_tweet_id=quote_tweet_id)
        url = f"https://x.com/GNOSIS1966282/status/{tid}" if tid else "https://x.com/GNOSIS1966282"
        self.logs.log_info(f"quote — {text[:120]} | tweet_id={tid} | {url}", "bold yellow", "Transmit")
        return tid

    def like(self, tweet_id):
        uid = self._get_gnosis_user_id()
        if not uid:
            self.logs.log_error("Cannot like — no user ID"); return
        try:
            self.client_official.like(tweet_id=tweet_id, user_auth=True)
            self.logs.log_info(f"Liked: {tweet_id}", "bold yellow", "Action")
        except Exception as e:
            self.logs.log_error(f"Like failed: {e}")
