from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from modelrouter.domain.conversation import Conversation
from modelrouter.domain.inventory import Inventory
from modelrouter.domain.task_profile import TaskProfile


class ClassifierError(Exception):
    pass


class Classifier(ABC):
    @abstractmethod
    def profile(self, question: str) -> TaskProfile:
        """Lève ClassifierError si la classification est impossible."""


class BinaryLocator(ABC):
    @abstractmethod
    def locate(self, binary: str) -> str | None:
        ...


class LocalModelLister(ABC):
    @abstractmethod
    def list_models(self, binary_path: str) -> list:
        ...


class AccountModelLister(ABC):
    @abstractmethod
    def list_available(self, agent: str) -> list | None:
        """Modèles que le compte connecté peut utiliser ; None si on ne sait pas."""


@dataclass(frozen=True)
class LaunchOutcome:
    output: str
    exit_code: int

    def succeeded(self) -> bool:
        return self.exit_code == 0

    def worth_retrying(self) -> bool:
        """L'agent a échoué avant de répondre (auth, binaire cassé) : un autre modèle peut prendre le relais."""
        return self.exit_code > 0 and not self.output.strip()


class Launcher(ABC):
    @abstractmethod
    def launch(self, argv: list) -> LaunchOutcome:
        """Lance l'agent en affichant sa sortie en direct, et la renvoie."""


class InventoryStore(ABC):
    @abstractmethod
    def load(self) -> Inventory | None:
        ...

    @abstractmethod
    def save(self, inventory: Inventory) -> None:
        ...


class ConversationStore(ABC):
    @abstractmethod
    def load(self) -> Conversation:
        ...

    @abstractmethod
    def save(self, conversation: Conversation) -> None:
        ...


class ClosedAnswerer(ABC):
    @abstractmethod
    def handles(self, question: str) -> bool:
        """Vrai si la question a une forme fermée exploitable (oui/non ou options listées)."""

    @abstractmethod
    def answer(self, question: str, piped: str | None = None) -> LaunchOutcome | None:
        """Répond à une question fermée, ou None si elle ne l'est pas ou si la réponse est impossible."""
