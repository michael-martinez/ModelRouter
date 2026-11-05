from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor

from modelrouter.adapters.ports import ClosedAnswerer, LaunchOutcome
from modelrouter.domain.closed_question import ClosedQuestion
from modelrouter.infra.jev_client import JevClient, JevError, http_post

SINGLE_INSTRUCTIONS = "Réponds à la question posée dans ce texte."
MAX_LINES = 1_000
BATCH_TIMEOUT_SECONDS = 10


class JevAnswerer(ClosedAnswerer):
    """Jev répond seul aux questions fermées, une par ligne quand un contenu est fourni par pipe."""

    def __init__(self, api_key: str | None, post=http_post, out=None):
        self._client = JevClient(api_key, post, timeout=BATCH_TIMEOUT_SECONDS)
        self._out = out

    def handles(self, question: str) -> bool:
        return self._client.available() and ClosedQuestion.parse(question) is not None

    def answer(self, question: str, piped: str | None = None) -> LaunchOutcome | None:
        closed = ClosedQuestion.parse(question)
        if closed is None or not self._client.available():
            return None
        items = [line.strip() for line in (piped or "").splitlines() if line.strip()][:MAX_LINES]
        try:
            if items:
                jev_question = {"reponse": closed.jev_question(question)}
                with ThreadPoolExecutor(max_workers=8) as pool:
                    answers = list(pool.map(lambda item: self._client.ask(item, jev_question), items))
                text = closed.render_batch(items, [closed.read(a["reponse"]) for a in answers])
            else:
                answers = self._client.ask(question, {"reponse": closed.jev_question(SINGLE_INSTRUCTIONS)})
                text = closed.render(closed.read(answers["reponse"]))
        except (JevError, KeyError, TypeError, ValueError):
            return None
        out = self._out or sys.stdout
        print(text, file=out, flush=True)
        return LaunchOutcome(text, 0)
