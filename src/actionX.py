import os, sys
sys.path.append(os.path.abspath('.'))
from src.xBridge import xBridge
from src.logs import logs
from src.memory import memory as MemoryStore

class actionX:
    def __init__(self):
        self.xBridge_instance = xBridge()
        self.logs = logs()
        self.memory_store = MemoryStore()

    def excute(self, action: dict):
        target_tweet_id = action.get('target_tweet_id', '')
        action_type = action.get('action', '')
        content = action.get('content', '')
        if not content:
            self.logs.log_error('No content in action'); return

        # Enforce 280 char limit
        content = content[:280]

        if action_type in ('tweet', 'post'):
            self.xBridge_instance.tweet(text=content)
        elif action_type == 'reply' and target_tweet_id:
            # Replies to mentions are allowed on free tier
            self.xBridge_instance.reply(
                in_reply_to_tweet_id=target_tweet_id, text=content)
        elif action_type == 'quote' and target_tweet_id:
            self.xBridge_instance.quote(
                quote_tweet_id=target_tweet_id, text=content)
        else:
            # Fallback to plain post
            self.xBridge_instance.tweet(text=content)

        self.memory_store.add_entry(action_type, content)
        self.logs.log_info(
            f"{action_type}: {content[:120]}", "bold yellow", "Action")
