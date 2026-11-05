from __future__ import annotations

from dataclasses import dataclass

from modelrouter.domain.model import Model


@dataclass(frozen=True)
class AgentSpec:
    """Un agent du catalogue : comment le détecter et comment le lancer."""

    name: str
    binary: str
    env_keys: tuple
    command: tuple
    models: tuple
    local_models: dict = None
    builtin: bool = False
    session: dict = None
    filter_by_account: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> AgentSpec:
        return cls(
            data["name"],
            data.get("binary", ""),
            tuple(data.get("env_keys", [])),
            tuple(data.get("command", [])),
            tuple(data.get("models", [])),
            data.get("local_models"),
            bool(data.get("builtin", False)),
            data.get("session"),
            bool(data.get("filter_by_account", False)),
        )

    def is_builtin(self) -> bool:
        return self.builtin

    def needs_local_listing(self) -> bool:
        return self.local_models is not None

    def key_in(self, env: dict) -> str | None:
        return next((key for key in self.env_keys if env.get(key)), None)

    def models_at(self, binary_path: str, local_names: list = ()) -> list:
        command = tuple(part.replace("{bin}", binary_path) for part in self.command)
        specs = list(self.models)
        if self.needs_local_listing():
            specs += [{"name": name, **self.local_models} for name in local_names]
        session = self.session or {}
        start, resume = tuple(session.get("start", ())), tuple(session.get("resume", ()))
        return [Model(self.name, spec["name"], int(spec["cost_tier"]), dict(spec["skills"]), command, self.builtin,
                      start, resume)
                for spec in specs]
