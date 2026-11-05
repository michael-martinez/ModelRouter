from __future__ import annotations

from modelrouter.adapters.ports import BinaryLocator, Classifier, ClassifierError, Launcher, LaunchOutcome, LocalModelLister
from modelrouter.domain.task_profile import TaskProfile


class FakeLocator(BinaryLocator):
    def __init__(self, paths: dict[str, str]):
        self._paths = paths

    def locate(self, binary: str) -> str | None:
        return self._paths.get(binary)


class FakeLocalModels(LocalModelLister):
    def __init__(self, names: list[str]):
        self._names = names

    def list_models(self, binary_path: str) -> list[str]:
        return self._names


class FakeClassifier(Classifier):
    def __init__(self, category: str = "code", complexity: int = 2, error: bool = False):
        self._profile = TaskProfile(category, complexity)
        self._error = error
        self.calls = 0
        self.texts = []

    def answer_with(self, category: str, complexity: int) -> None:
        self._profile = TaskProfile(category, complexity)

    def profile(self, question: str) -> TaskProfile:
        self.calls += 1
        self.texts.append(question)
        if self._error:
            raise ClassifierError("timeout")
        return self._profile


class RecordingLauncher(Launcher):
    def __init__(self, answer: str = "réponse", exit_code: int = 0):
        self.argv: list[str] | None = None
        self.calls: list = []
        self.answer = answer
        self.exit_code = exit_code
        self.queued: list = []

    def then(self, answer: str, exit_code: int) -> RecordingLauncher:
        self.queued.append(LaunchOutcome(answer, exit_code))
        return self

    def launch(self, argv: list[str]) -> LaunchOutcome:
        self.argv = argv
        self.calls.append(argv)
        if self.queued:
            return self.queued.pop(0)
        return LaunchOutcome(self.answer, self.exit_code)

    def prompt(self) -> str:
        return self.argv[-1]


class FakeClock:
    def __init__(self, now: float = 1_000_000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance_minutes(self, minutes: float) -> None:
        self.now += minutes * 60


CATALOG = {
    "default_profile": {"category": "raisonnement", "complexity": 3},
    "agents": [
        {
            "name": "claude",
            "binary": "claude",
            "env_keys": ["ANTHROPIC_API_KEY"],
            "command": ["{bin}", "-p", "--model", "{model}", "{prompt}"],
            "session": {"start": ["--session-id", "{session}"], "resume": ["--resume", "{session}"]},
            "models": [
                {"name": "opus", "cost_tier": 4, "skills": {"code": 4, "raisonnement": 4, "question_rapide": 4, "classification": 4}},
                {"name": "sonnet", "cost_tier": 2, "skills": {"code": 3, "raisonnement": 3, "question_rapide": 4, "classification": 4}},
                {"name": "haiku", "cost_tier": 1, "skills": {"code": 2, "raisonnement": 2, "question_rapide": 4, "classification": 3}},
            ],
        },
        {
            "name": "codex",
            "binary": "codex",
            "env_keys": ["OPENAI_API_KEY"],
            "command": ["{bin}", "exec", "-m", "{model}", "{prompt}"],
            "models": [
                {"name": "gpt-sol", "cost_tier": 2, "skills": {"code": 4, "raisonnement": 3, "question_rapide": 4, "recherche_web": 3}},
            ],
        },
        {
            "name": "ollama",
            "binary": "ollama",
            "env_keys": [],
            "command": ["{bin}", "run", "{model}", "{prompt}"],
            "local_models": {"cost_tier": 0, "skills": {"code": 1, "raisonnement": 1, "question_rapide": 2}},
        },
        {
            "name": "jev",
            "builtin": True,
            "env_keys": ["JEV_API_KEY"],
            "models": [{"name": "jev-latest", "cost_tier": 0, "skills": {"classification": 4}}],
        },
    ],
}


class SessionIds:
    def __init__(self):
        self.count = 0

    def __call__(self) -> str:
        self.count += 1
        return f"s{self.count}"
