from __future__ import annotations

import hashlib
import json
from pathlib import Path

from modelrouter.adapters.ports import ConversationStore, InventoryStore
from modelrouter.domain.conversation import Conversation
from modelrouter.domain.inventory import Inventory

CONFIG_DIR = Path.home() / ".config" / "model-router"
DEFAULT_PATH = CONFIG_DIR / "inventory.json"


class JsonInventoryStore(InventoryStore):
    def __init__(self, path: Path = DEFAULT_PATH):
        self._path = Path(path)

    def load(self) -> Inventory | None:
        if not self._path.exists():
            return None
        return Inventory.from_dict(json.loads(self._path.read_text(encoding="utf-8")))

    def save(self, inventory: Inventory) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(inventory.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


class JsonConversationStore(ConversationStore):
    def __init__(self, path: Path):
        self._path = Path(path)

    @classmethod
    def for_directory(cls, directory: str) -> JsonConversationStore:
        key = hashlib.sha1(str(Path(directory).resolve()).encode()).hexdigest()[:16]
        return cls(CONFIG_DIR / "conversations" / f"{key}.json")

    def load(self) -> Conversation:
        if not self._path.exists():
            return Conversation.fresh()
        return Conversation.from_dict(json.loads(self._path.read_text(encoding="utf-8")))

    def save(self, conversation: Conversation) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(conversation.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
