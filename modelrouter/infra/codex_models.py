from __future__ import annotations

import json
from pathlib import Path

from modelrouter.adapters.ports import AccountModelLister

CODEX_MODELS_CACHE = Path.home() / ".codex" / "models_cache.json"


class CodexAccountModels(AccountModelLister):
    """Lit le cache de modèles de la CLI Codex, qui reflète le compte ChatGPT connecté."""

    def __init__(self, path: Path = CODEX_MODELS_CACHE):
        self._path = path

    def list_available(self, agent: str) -> list | None:
        if agent != "codex":
            return None
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        models = data.get("models", []) if isinstance(data, dict) else data
        return [m["slug"] for m in models if isinstance(m, dict) and m.get("visibility") == "list" and "slug" in m]
