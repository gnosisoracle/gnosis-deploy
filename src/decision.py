import os
import sys
import json
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
        try:
            cols = [c for c in ['Name','Handle','Content','Verified','Comments',
                                 'Retweets','Likes','Analytics','Tags','Mentions','Tweet ID']
                    if c in observation.columns]
            obs_filtered = observation[cols]
        except Exception:
            obs_filtered = observation

        # Build user prompt with memory & dialog context
        context = ""
        if memory:
            context += f"\n\nPast memory:\n{memory}"
        if dialog and dialog != "None":
            context += f"\n\nRecent dialog:\n{dialog}"

        prompt_user = f"```\n{obs_filtered.to_string()}\n```{context}\n\n{self.prompt_config['user']}"

        raw = self.ai.call_llm(
            prompt_system=self.prompt_config['system'],
            prompt_user=prompt_user
        )
        return self._parse(raw)

    def _parse(self, raw: str) -> dict:
        clean = raw.strip()
        # Strip markdown fences
        if "```" in clean:
            parts = clean.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    clean = part
                    break
        return json.loads(clean)
