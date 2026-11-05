from __future__ import annotations

from dataclasses import dataclass

MAX_EXCHANGES = 5
MAX_STORED = 20
MAX_ANSWER_CHARS = 1_500
EXPIRY_SECONDS = 30 * 60
PIPED_EXCERPT_CHARS = 300


@dataclass(frozen=True)
class Exchange:
    question: str
    answer: str
    model: str
    agent: str

    @classmethod
    def from_dict(cls, data: dict) -> Exchange:
        return cls(data["question"], data["answer"], data["model"], data.get("agent", data["model"].split("/")[0]))

    def to_dict(self) -> dict:
        return {"question": self.question, "answer": self.answer, "model": self.model, "agent": self.agent}

    def render(self) -> str:
        return f"Question : {self.question}\nRéponse ({self.model}) : {self.answer}"


class Conversation:
    """Fil d'une conversation : l'agent qui la porte, ses sessions natives, et les échanges pour les autres agents."""

    def __init__(self, exchanges: tuple = (), last_activity: float = 0.0, current_agent: str | None = None,
                 sessions: dict = None):
        self._exchanges = tuple(exchanges)[-MAX_STORED:]
        self._last_activity = last_activity
        self._current_agent = current_agent
        self._sessions = dict(sessions or {})

    @classmethod
    def fresh(cls) -> Conversation:
        return cls()

    @classmethod
    def from_dict(cls, data: dict) -> Conversation:
        return cls(tuple(Exchange.from_dict(e) for e in data["exchanges"]), float(data["last_activity"]),
                   data.get("current_agent"), data.get("sessions"))

    def to_dict(self) -> dict:
        return {"exchanges": [e.to_dict() for e in self._exchanges], "last_activity": self._last_activity,
                "current_agent": self._current_agent, "sessions": self._sessions}

    def active_at(self, now: float) -> Conversation:
        """Elle-même si elle est encore vivante, sinon une conversation neuve."""
        if self._exchanges and now - self._last_activity <= EXPIRY_SECONDS:
            return self
        return Conversation.fresh()

    def current_agent(self) -> str | None:
        return self._current_agent

    def session_for(self, agent: str) -> str | None:
        return self._sessions.get(agent)

    def prompt_for(self, question: str, piped: str | None = None, agent: str | None = None,
                   resuming: bool = False) -> str:
        """Session reprise : seulement ce qui s'est dit ailleurs depuis son dernier tour. Sinon : l'historique récent."""
        request = f"{question}\n\nContenu fourni :\n{piped}" if piped else question
        if resuming:
            missed = self._since_last_turn_of(agent)
            if not missed:
                return request
            return (f"Entre-temps, hors de cette session :\n\n{self._render(missed)}\n\n"
                    f"Nouvelle question : {request}")
        if not self._exchanges:
            return request
        recent = self._exchanges[-MAX_EXCHANGES:]
        questions = "\n".join(f"- {e.question}" for e in recent)
        last = recent[-1]
        return (f"Contexte : questions précédentes de cette conversation :\n{questions}\n\n"
                f"Dernière réponse ({last.model}), à ne reprendre que si la nouvelle question la concerne :\n"
                f"{last.answer}\n\nNouvelle question : {request}")

    def classification_text(self, question: str, piped: str | None = None) -> str:
        text = question
        if self._exchanges:
            text = f"Question précédente : {self._exchanges[-1].question}\nQuestion actuelle : {question}"
        if piped:
            text += f"\nContenu fourni (extrait) : {piped[:PIPED_EXCERPT_CHARS]}"
        return text

    def record(self, question: str, answer: str, model: str, agent: str, now: float,
               session: str | None = None, sticky: bool = True) -> Conversation:
        answer = answer.strip()
        if len(answer) > MAX_ANSWER_CHARS:
            answer = answer[:MAX_ANSWER_CHARS] + " [...]"
        sessions = {**self._sessions, agent: session} if session else self._sessions
        return Conversation(self._exchanges + (Exchange(question, answer, model, agent),), now,
                            agent if sticky else self._current_agent, sessions)

    def _since_last_turn_of(self, agent: str) -> tuple:
        for index in range(len(self._exchanges) - 1, -1, -1):
            if self._exchanges[index].agent == agent:
                return self._exchanges[index + 1:][-MAX_EXCHANGES:]
        return self._exchanges[-MAX_EXCHANGES:]

    @staticmethod
    def _render(exchanges: tuple) -> str:
        return "\n\n".join(e.render() for e in exchanges)
