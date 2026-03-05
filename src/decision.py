import os, sys, json
import pandas as pd
sys.path.append(os.path.abspath('.'))

from src.config import get_config, get_prompt
from interface.decisionInterface import decisionInterface
from interface.aiBridgeInterface import aiBridgeInterface

config = get_config()

class decision(decisionInterface):
    def __init__(self, ai_instance: aiBridgeInterface):
        self.ai = ai_instance
        self.prompt_config = get_prompt()["gnosis"]

    def make_decision(self, observation: pd.DataFrame, memory: str, dialog: str) -> dict:
        feed_lines = []
        has_mention = False
        try:
            for _, row in observation.iterrows():
                handle  = str(row.get('Handle','') or row.get('Name',''))
                content = str(row.get('Content',''))
                tid     = str(row.get('Tweet ID',''))
                label   = str(row.get('Label',''))
                if content:
                    is_mention = (label == 'mention')
                    if is_mention:
                        has_mention = True
                    prefix  = "[MENTION - they spoke to you directly] " if is_mention else ""
                    tid_str = (" [tweet_id:" + tid + "]") if tid else ""
                    feed_lines.append(prefix + "@" + handle + tid_str + ": " + content)
        except Exception:
            feed_lines = [str(observation)]

        feed_str = "\n\n".join(feed_lines) if feed_lines else "the stream is quiet"

        mention_note = ""
        if has_mention:
            mention_note = "\n\nNOTE: there is a direct mention above. reply to that person using their tweet_id."

        context = ""
        if memory:
            context += "\n\nwhat you have said before (memory):\n" + str(memory)
        if dialog and dialog != "None":
            context += "\n\nrecent dialog:\n" + str(dialog)

        prompt_user = (
            "the stream right now:\n\n" + feed_str +
            mention_note + context +
            "\n\n" + self.prompt_config['user']
        )

        raw = self.ai.call_llm(
            prompt_system=self.prompt_config['system'],
            prompt_user=prompt_user
        )
        return self._parse(raw)

    def _parse(self, raw: str) -> dict:
        clean = raw.strip()
        if "```" in clean:
            parts = clean.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    clean = part
                    break
        start = clean.find("{")
        end   = clean.rfind("}")
        if start != -1 and end != -1:
            clean = clean[start:end+1]
        return json.loads(clean)
