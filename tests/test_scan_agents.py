from __future__ import annotations

from modelrouter.infra.json_store import JsonInventoryStore
from modelrouter.usecases.scan_agents import ScanAgents
from tests.fakes import CATALOG, FakeLocalModels, FakeLocator


def scan(tmp_path, paths, env=None, local_models=()):
    store = JsonInventoryStore(tmp_path / "inventory.json")
    report = ScanAgents(CATALOG, FakeLocator(paths), FakeLocalModels(list(local_models)), store).execute(env or {})
    return report, store.load()


def test_installed_agent_exposes_all_its_models(tmp_path):
    report, inventory = scan(tmp_path, {"claude": "/home/u/.local/bin/claude"})

    assert report.found_agents == ["claude"]
    assert inventory.labels() == ["claude/opus", "claude/sonnet", "claude/haiku"]


def test_missing_agents_are_ignored(tmp_path):
    report, inventory = scan(tmp_path, {"codex": "/usr/local/bin/codex"})

    assert report.found_agents == ["codex"]
    assert inventory.labels() == ["codex/gpt-sol"]


def test_api_key_without_cli_is_reported_as_hint(tmp_path):
    report, inventory = scan(tmp_path, {"claude": "/bin/claude"}, env={"OPENAI_API_KEY": "sk-x"})

    assert "codex" not in report.found_agents
    assert any("OPENAI_API_KEY" in hint and "codex" in hint for hint in report.hints)


def test_local_runtime_exposes_its_pulled_models(tmp_path):
    report, inventory = scan(tmp_path, {"ollama": "/opt/homebrew/bin/ollama"}, local_models=["llama4:8b", "qwen3:14b"])

    assert inventory.labels() == ["ollama/llama4:8b", "ollama/qwen3:14b"]


def test_detected_binary_path_is_used_in_commands(tmp_path):
    _, inventory = scan(tmp_path, {"claude": "/home/u/.local/bin/claude"})

    model = inventory.only("claude/haiku").models()[0]
    assert model.command_for("salut") == ["/home/u/.local/bin/claude", "-p", "--model", "haiku", "salut"]
