from __future__ import annotations

from dataclasses import dataclass

from modelrouter.domain.model import Model
from modelrouter.domain.task_profile import TaskProfile


class EmptyInventory(Exception):
    pass


@dataclass(frozen=True)
class Choice:
    model: Model
    reason: str


class Inventory:
    """Modèles installés, dans l'ordre de priorité du catalogue."""

    def __init__(self, models: list):
        self._models = list(models)

    @classmethod
    def from_dict(cls, data: dict) -> Inventory:
        return cls([Model.from_dict(m) for m in data["models"]])

    def to_dict(self) -> dict:
        return {"models": [m.to_dict() for m in self._models]}

    def models(self) -> list:
        return list(self._models)

    def labels(self) -> list:
        return [m.label() for m in self._models]

    def only(self, selector: str) -> Inventory:
        selected = [m for m in self._models if m.matches(selector)]
        if not selected:
            raise EmptyInventory(f"Aucun modèle installé ne correspond à « {selector} ». Installés : {', '.join(self.labels())}")
        return Inventory(selected)

    def best_for(self, profile: TaskProfile) -> Choice:
        if not self._models:
            raise EmptyInventory("Aucun modèle installé.")
        ranked = list(enumerate(self._models))
        capable = [(i, m) for i, m in ranked if m.handles(profile)]
        if capable:
            _, model = min(capable, key=lambda im: (*im[1].preference_for(profile), im[0]))
            return Choice(model, f"{profile.describe()} → le moins cher au niveau requis ({model.level_for(profile)}/4)")
        stand_ins = [(i, m) for i, m in ranked if m.can_stand_in()]
        if not stand_ins:
            raise EmptyInventory(f"Aucun modèle installé ne sait traiter : {profile.describe()}")
        _, model = min(stand_ins, key=lambda im: (*im[1].strength_for(profile), im[0]))
        return Choice(model, f"{profile.describe()} → aucun modèle au niveau requis, le plus fort installé ({model.level_for(profile)}/4)")

    def without(self, model: Model) -> Inventory:
        return Inventory([m for m in self._models if m != model])

    def can_serve(self, profile: TaskProfile) -> bool:
        return any(m.handles(profile) or m.can_stand_in() for m in self._models)

    def forced_for(self, profile: TaskProfile) -> Choice:
        """Choix sur une sélection imposée par l'utilisateur : même un spécialiste est accepté."""
        if self.can_serve(profile):
            return self.best_for(profile)
        if not self._models:
            raise EmptyInventory("Aucun modèle installé.")
        return Choice(self._models[0], f"{profile.describe()} → imposé")

    def without_agent(self, agent: str) -> Inventory:
        return Inventory([m for m in self._models if not m.belongs_to(agent)])

    def best_for_continuing(self, profile: TaskProfile, agent: str) -> Choice:
        """On reste sur l'agent de la conversation, sauf s'il n'a pas le niveau et qu'un autre l'a."""
        overall = self.best_for(profile)
        own = [(i, m) for i, m in enumerate(self._models) if m.belongs_to(agent)]
        if overall.model.is_builtin() or not own or overall.model.belongs_to(agent):
            return overall
        capable = [(i, m) for i, m in own if m.handles(profile)]
        if capable:
            _, model = min(capable, key=lambda im: (*im[1].preference_for(profile), im[0]))
            return Choice(model, f"{profile.describe()} → on reste sur {agent} ({model.level_for(profile)}/4)")
        _, strongest = min(own, key=lambda im: (*im[1].strength_for(profile), im[0]))
        if not overall.model.handles(profile):
            return Choice(strongest, f"{profile.describe()} → personne n'a le niveau, on reste sur {agent} "
                                     f"({strongest.level_for(profile)}/4)")
        return Choice(overall.model, f"{agent} n'a pas le niveau ({profile.category} "
                                     f"{strongest.level_for(profile)}/{profile.complexity}) → {overall.reason}")
