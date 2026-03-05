import os
import sys
sys.path.append(os.path.abspath('.'))

from interface.actionInterface import actionInterface
from src.xBridge import xBridge
from src.logs import logs
from src.memory import memory as MemoryStore

class actionX(actionInterface):
    def __init__(self):
        self.xBridge_instance = xBridge()
        self.logs = logs()
        self.memory_store = MemoryStore()

    def excute(self, action: dict):
        target_tweet_id = action.get('target_tweet_id', '')
        action_type = action.get('action', '')
        content = action.get('content', '')

        if action_type in ('tweet', 'post'):
            self.xBridge_instance.tweet(message=content)
        elif action_type == 'reply':
            self.xBridge_instance.reply(tweet_id=target_tweet_id, message=content)
        elif action_type == 'quote':
            self.xBridge_instance.quote(tweet_id=target_tweet_id, message=content)
        else:
            self.logs.log_error(f'Unknown action type: {action_type}')
            return

        # Persist to memory
        self.memory_store.add_entry(action_type, content)

    def reply(self, tweet_id, message, image_path=None):
        self.xBridge_instance.reply(tweet_id, message, image_path)

    def quote(self, tweet_id, message, image_path=None):
        self.xBridge_instance.quote(tweet_id, message, image_path)

    def tweet(self, message, image_path=None):
        self.xBridge_instance.tweet(message, image_path=image_path)
