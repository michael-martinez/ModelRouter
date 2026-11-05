from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

WORD = r"[\wÀ-ÿ'’\-]+"
QUOTED = re.compile(r"«[^»]*»|\"[^\"]*\"|“[^”]*”")
SLASH_OPTIONS = re.compile(rf"{WORD}(?:\s*/\s*{WORD})+")
OR_OPTIONS = re.compile(rf"({WORD}(?:\s*,\s*{WORD})*\s+ou\s+{WORD})$")
INVERSION = re.compile(r"\b[\wÀ-ÿ]+-(?:t-)?(?:il|elle|ils|elles|on|je|tu|nous|vous)\b")
YES_NO_STARTS = ("est-ce", "y a-t-il", "is ", "are ", "does ", "do ", "can ", "should ", "has ", "have ")


@dataclass(frozen=True)
class Verdict:
    label: str
    confidence: float

    def render(self, with_word: bool) -> str:
        percent = f"{round(self.confidence * 100)} %"
        return f"{self.label} (confiance {percent})" if with_word else f"{self.label} ({percent})"


class ClosedQuestion:
    """Question fermée à laquelle Jev peut répondre seul : oui/non, ou choix parmi des options écrites."""

    def __init__(self, options: tuple = ()):
        self._options = tuple(options)

    @classmethod
    def parse(cls, text: str) -> ClosedQuestion | None:
        question = QUOTED.sub(" ", text)
        slash = SLASH_OPTIONS.findall(question)
        if slash:
            return cls(tuple(o.strip() for o in slash[-1].split("/")))
        trimmed = question.strip(" \t\n:?!.").strip()
        listed = OR_OPTIONS.search(trimmed)
        if listed:
            return cls(tuple(o.strip() for o in re.split(r"\s*,\s*|\s+ou\s+", listed.group(1))))
        lowered = trimmed.lower()
        if lowered.startswith(YES_NO_STARTS) or INVERSION.search(lowered):
            return cls()
        return None

    def is_yes_no(self) -> bool:
        return not self._options

    def jev_question(self, instructions: str) -> dict:
        if self.is_yes_no():
            return {"type": "noul", "instructions": instructions,
                    "criteria": {"true": "Oui", "false": "Non"}}
        return {"type": "choice", "instructions": instructions,
                "criteria": {option: option for option in self._options}}

    def read(self, answer: dict) -> Verdict:
        if self.is_yes_no():
            probability = float(answer["noul"])
            return Verdict("Oui", probability) if probability >= 0.5 else Verdict("Non", 1 - probability)
        return Verdict(answer["choice"], float(answer.get("confidence", 0)))

    def render(self, verdict: Verdict) -> str:
        return verdict.render(with_word=not self.is_yes_no())

    def render_batch(self, items: list, verdicts: list) -> str:
        lines = [f"{item} → {self.render(verdict)}" for item, verdict in zip(items, verdicts)]
        counts = Counter(v.label for v in verdicts)
        summary = " · ".join(f"{label} {round(100 * n / len(verdicts))} %" for label, n in counts.most_common())
        return "\n".join(lines + ["", f"Répartition ({len(verdicts)}) : {summary}"])
