from __future__ import annotations

from dataclasses import dataclass

CATEGORIES = {
    "code": "Écrire, corriger, relire ou refactorer du code",
    "raisonnement": "Maths, logique, architecture, debug difficile, décision argumentée",
    "redaction": "Rédiger, reformuler, traduire, résumer un texte",
    "recherche_web": "Besoin d'informations récentes ou de sources sur le web",
    "multimodal": "Analyser ou produire des images, PDF, audio ou vidéo",
    "question_rapide": "Question factuelle courte ou conversation simple",
    "classification": "Classer, trier ou étiqueter un texte, ou répondre par oui/non à une question fermée sur un texte",
}

MAX_COMPLEXITY = 4


@dataclass(frozen=True)
class TaskProfile:
    category: str
    complexity: int

    def __post_init__(self):
        if self.category not in CATEGORIES:
            raise ValueError(f"Catégorie inconnue : {self.category}")
        if not 0 <= self.complexity <= MAX_COMPLEXITY:
            raise ValueError(f"Complexité hors de 0..{MAX_COMPLEXITY} : {self.complexity}")

    @classmethod
    def from_dict(cls, data: dict) -> TaskProfile:
        return cls(data["category"], int(data["complexity"]))

    def describe(self) -> str:
        return f"{self.category}, complexité {self.complexity}/{MAX_COMPLEXITY}"
