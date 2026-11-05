from __future__ import annotations

from modelrouter.adapters.ports import Classifier, ClassifierError
from modelrouter.domain.task_profile import CATEGORIES, MAX_COMPLEXITY, TaskProfile
from modelrouter.infra.jev_client import JevClient, JevError, http_post

QUESTIONS = {
    "tache": {
        "type": "choice",
        "instructions": "Quel type de tâche cette demande adressée à un assistant IA représente-t-elle ?",
        "criteria": CATEGORIES,
    },
    "complexite": {
        "type": "score",
        "instructions": "Quel niveau de modèle IA faut-il pour répondre de façon correcte et rigoureuse ? "
                        "Juge l'effort de raisonnement nécessaire, pas la longueur de la demande : "
                        "une demande courte peut exiger une démonstration rigoureuse.",
        "criteria": [
            "Trivial : fait connu, traduction d'un mot, conversion, réponse immédiate",
            "Simple : tâche courante en une étape (petite fonction, résumé, reformulation)",
            "Moyen : plusieurs étapes ou contexte à prendre en compte (feature isolée, email délicat)",
            "Difficile : démonstration mathématique, raisonnement logique rigoureux, refactoring ou conception multi-fichiers",
            "Expert : architecture distribuée, debug de concurrence ou de crash en production, problème ouvert",
        ],
    },
}


class JevClassifier(Classifier):
    def __init__(self, api_key: str | None, post=http_post):
        self._client = JevClient(api_key, post)

    def profile(self, question: str) -> TaskProfile:
        try:
            answers = self._client.ask(question, QUESTIONS)
        except JevError as error:
            raise ClassifierError(str(error)) from error
        try:
            complexity = min(MAX_COMPLEXITY, max(0, round(float(answers["complexite"]["score"]))))
            return TaskProfile(answers["tache"]["choice"], complexity)
        except (KeyError, TypeError, ValueError) as error:
            raise ClassifierError(f"réponse Jev inattendue : {error}") from error
