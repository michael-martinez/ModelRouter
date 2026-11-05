from __future__ import annotations

from dataclasses import dataclass, field

from modelrouter.domain.task_profile import TaskProfile


@dataclass(frozen=True)
class Model:
    agent: str
    name: str
    cost_tier: int
    skills: dict = field(hash=False)
    command: tuple = field(hash=False)
    builtin: bool = False
    session_start: tuple = field(default=(), hash=False)
    session_resume: tuple = field(default=(), hash=False)

    @classmethod
    def from_dict(cls, data: dict) -> Model:
        return cls(data["agent"], data["name"], int(data["cost_tier"]), dict(data["skills"]), tuple(data["command"]),
                   bool(data.get("builtin", False)), tuple(data.get("session_start", ())),
                   tuple(data.get("session_resume", ())))

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "name": self.name,
            "cost_tier": self.cost_tier,
            "skills": self.skills,
            "command": list(self.command),
            "builtin": self.builtin,
            "session_start": list(self.session_start),
            "session_resume": list(self.session_resume),
        }

    def label(self) -> str:
        return f"{self.agent}/{self.name}"

    def matches(self, selector: str) -> bool:
        return selector in (self.agent, self.label())

    def level_for(self, profile: TaskProfile) -> int:
        return int(self.skills.get(profile.category, 0))

    def is_builtin(self) -> bool:
        """Répondu par ModelRouter lui-même (Jev), sans lancer de CLI."""
        return self.builtin

    def can_stand_in(self) -> bool:
        """Peut répondre à n'importe quoi en dernier recours : pas un spécialiste comme Jev."""
        return not self.builtin

    def handles(self, profile: TaskProfile) -> bool:
        """Niveau 0 = ne sait pas faire, même pour une demande triviale."""
        level = self.level_for(profile)
        return level > 0 and level >= profile.complexity

    def preference_for(self, profile: TaskProfile) -> tuple:
        """Clé de tri parmi les modèles capables : le moins cher, puis le plus compétent."""
        return self.cost_tier, -self.level_for(profile)

    def strength_for(self, profile: TaskProfile) -> tuple:
        """Clé de tri quand aucun modèle n'est capable : le plus compétent, puis le moins cher."""
        return -self.level_for(profile), self.cost_tier

    def supports_sessions(self) -> bool:
        """L'agent sait reprendre une session précise par son id (claude --resume <uuid>)."""
        return bool(self.session_start)

    def belongs_to(self, agent: str) -> bool:
        return self.agent == agent

    def command_for(self, prompt: str, session: str | None = None, resuming: bool = False,
                    sandbox: str = "read-only") -> list:
        session_args = []
        if session and self.supports_sessions():
            session_args = [p.replace("{session}", session) for p in (self.session_resume if resuming else self.session_start)]
        argv = []
        for part in self.command:
            if part == "{prompt}":
                argv += session_args + [prompt]
            else:
                argv.append(part.replace("{model}", self.name).replace("{sandbox}", sandbox))
        return argv
