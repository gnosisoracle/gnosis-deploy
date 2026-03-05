import os
import sys
import json
from datetime import datetime
sys.path.append(os.path.abspath('.'))

from src.config import get_config
from src.utils import make_dir_not_exist
from interface.memoryInterface import memoryInterface

config = get_config()

class memory(memoryInterface):
    def __init__(self):
        self.memory_path = config.get('memory_path', '/data/memory/memory.json')
        make_dir_not_exist(self.memory_path)
        if not os.path.exists(self.memory_path):
            self._save([])

    def _load(self):
        try:
            with open(self.memory_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def _save(self, data):
        try:
            make_dir_not_exist(self.memory_path)
            with open(self.memory_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[MEMORY SAVE ERROR] {e}")

    def updat_memory(self):
        """Placeholder — extend to store decision history"""
        pass

    def quer_memory(self):
        """Return recent memory as string for LLM context"""
        memories = self._load()
        if not memories:
            return ""
        # Return last 5 entries as context
        recent = memories[-5:]
        return "\n".join([f"[{m.get('ts','')}] {m.get('action','')} — {m.get('content','')[:100]}" for m in recent])

    def add_entry(self, action: str, content: str):
        """Add a new memory entry (call after each action)"""
        memories = self._load()
        memories.append({
            "ts": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "action": action,
            "content": content
        })
        # Keep last 100 entries
        if len(memories) > 100:
            memories = memories[-100:]
        self._save(memories)
