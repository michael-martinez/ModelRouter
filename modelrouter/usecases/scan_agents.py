from __future__ import annotations

from dataclasses import dataclass, field

from modelrouter.adapters.ports import AccountModelLister, BinaryLocator, InventoryStore, LocalModelLister
from modelrouter.domain.agent_spec import AgentSpec
from modelrouter.domain.inventory import Inventory


@dataclass
class ScanReport:
    found_agents: list = field(default_factory=list)
    hints: list = field(default_factory=list)
    inventory: Inventory = None


class ScanAgents:
    def __init__(self, catalog: dict, locator: BinaryLocator, local_models: LocalModelLister, store: InventoryStore,
                 account_models: AccountModelLister = None):
        self._agents = [AgentSpec.from_dict(a) for a in catalog["agents"]]
        self._locator = locator
        self._local_models = local_models
        self._store = store
        self._account_models = account_models

    def _available_on_account(self, agent: AgentSpec, models: list, report: ScanReport) -> list:
        """Écarte les modèles du catalogue que le compte ne peut pas utiliser, en le signalant."""
        if not agent.filter_by_account or self._account_models is None:
            return models
        available = self._account_models.list_available(agent.name)
        if available is None:
            return models
        kept = [m for m in models if m.name in available]
        for model in models:
            if model.name not in available:
                report.hints.append(f"{model.label()} ignoré : absent de ton compte")
        return kept

    def execute(self, env: dict) -> ScanReport:
        report = ScanReport()
        models = []
        for agent in self._agents:
            if agent.is_builtin():
                if agent.key_in(env):
                    report.found_agents.append(agent.name)
                    models += agent.models_at("")
                else:
                    report.hints.append(f"{' ou '.join(agent.env_keys)} absente : {agent.name} ne répondra pas lui-même")
                continue
            path = self._locator.locate(agent.binary)
            if path is None:
                key = agent.key_in(env)
                if key:
                    report.hints.append(f"{key} présente mais CLI « {agent.binary} » introuvable : installe {agent.name} pour l'utiliser")
                continue
            local_names = self._local_models.list_models(path) if agent.needs_local_listing() else []
            report.found_agents.append(agent.name)
            models += self._available_on_account(agent, agent.models_at(path, local_names), report)
        report.inventory = Inventory(models)
        self._store.save(report.inventory)
        return report
