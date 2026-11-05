from __future__ import annotations

from modelrouter.adapters.ports import AccountModelLister
from modelrouter.infra.json_store import JsonInventoryStore
from modelrouter.usecases.scan_agents import ScanAgents
from tests.fakes import FakeLocalModels, FakeLocator

SKILLS = {"code": 2, "raisonnement": 2, "redaction": 2, "recherche_web": 2, "multimodal": 2,
          "classification": 2, "question_rapide": 2}

CODEX_CATALOG = {"agents": [{
    "name": "codex", "binary": "codex", "env_keys": ["OPENAI_API_KEY"],
    "command": ["{bin}", "exec", "{prompt}"], "filter_by_account": True,
    "models": [{"name": "gpt-6-luna", "cost_tier": 1, "skills": SKILLS},
               {"name": "gpt-6.1-sol", "cost_tier": 3, "skills": SKILLS}],
}]}


class FakeAccountModels(AccountModelLister):
    def __init__(self, available):
        self._available = available

    def list_available(self, agent: str):
        return self._available


def scan(tmp_path, account_models):
    store = JsonInventoryStore(tmp_path / "inventory.json")
    report = ScanAgents(CODEX_CATALOG, FakeLocator({"codex": "/b/codex"}), FakeLocalModels([]), store,
                        account_models).execute({})
    return report, store.load()


def test_models_missing_from_the_account_are_left_out_and_reported(tmp_path):
    report, inventory = scan(tmp_path, FakeAccountModels(["gpt-6-luna"]))

    assert inventory.labels() == ["codex/gpt-6-luna"]
    assert any("codex/gpt-6.1-sol" in hint and "absent de ton compte" in hint for hint in report.hints)


def test_unknown_account_list_keeps_every_catalog_model(tmp_path):
    _, inventory = scan(tmp_path, FakeAccountModels(None))

    assert inventory.labels() == ["codex/gpt-6-luna", "codex/gpt-6.1-sol"]


def test_no_account_source_keeps_every_catalog_model(tmp_path):
    store = JsonInventoryStore(tmp_path / "inventory.json")
    ScanAgents(CODEX_CATALOG, FakeLocator({"codex": "/b/codex"}), FakeLocalModels([]), store).execute({})

    assert store.load().labels() == ["codex/gpt-6-luna", "codex/gpt-6.1-sol"]
