from __future__ import annotations

import json
import urllib.request

JEV_URL = "https://api.typesafe.ai/v1/systemone"
TIMEOUT_SECONDS = 2


class JevError(Exception):
    pass


def http_post(url: str, body: bytes, headers: dict, timeout: float) -> dict:
    request = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


class JevClient:
    def __init__(self, api_key: str | None, post=http_post, timeout: float = TIMEOUT_SECONDS):
        self._api_key = (api_key or "").strip()
        self._post = post
        self._timeout = timeout

    def available(self) -> bool:
        return bool(self._api_key)

    def ask(self, state: str, questions: dict) -> dict:
        """Renvoie les réponses de Jev ; toute erreur devient JevError, sans jamais exposer la clé."""
        if not self.available():
            raise JevError("JEV_API_KEY absente")
        body = json.dumps({"model": "jev-latest", "state": state, "questions": questions}).encode()
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        try:
            return self._post(JEV_URL, body, headers, self._timeout)["answers"]
        except Exception as error:
            raise JevError((str(error) or type(error).__name__).replace(self._api_key, "***")) from error
