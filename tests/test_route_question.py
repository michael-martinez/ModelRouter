from __future__ import annotations

import json

import pytest

from modelrouter.domain.inventory import EmptyInventory
from modelrouter.infra.jev_classifier import JevClassifier
from modelrouter.infra.json_store import JsonConversationStore, JsonInventoryStore
from modelrouter.usecases.route_question import InventoryMissing, RouteQuestion
from modelrouter.usecases.scan_agents import ScanAgents
from tests.fakes import CATALOG, FakeClassifier, FakeClock, FakeLocalModels, FakeLocator, RecordingLauncher

ALL = {"claude": "/b/claude", "codex": "/b/codex", "ollama": "/b/ollama"}


def router(tmp_path, classifier, paths=ALL, local_models=("llama:8b",)):
    store = JsonInventoryStore(tmp_path / "inventory.json")
    ScanAgents(CATALOG, FakeLocator(paths), FakeLocalModels(list(local_models)), store).execute({})
    launcher = RecordingLauncher()
    conversations = JsonConversationStore(tmp_path / "conversation.json")
    return RouteQuestion(store, classifier, launcher, CATALOG, conversations, FakeClock()), launcher


def test_complex_code_question_goes_to_cheapest_model_at_top_code_level(tmp_path):
    route, launcher = router(tmp_path, FakeClassifier("code", 4))

    result = route.execute("refactor ce module")

    assert result.model.label() == "codex/gpt-sol"
    assert launcher.argv == ["/b/codex", "exec", "-m", "gpt-sol", "refactor ce module"]


def test_quick_question_goes_to_cheapest_capable_model(tmp_path):
    route, _ = router(tmp_path, FakeClassifier("question_rapide", 2))

    assert route.execute("capitale de l'Australie ?").model.label() == "ollama/llama:8b"


def test_on_equal_cost_the_more_skilled_model_wins(tmp_path):
    route, _ = router(tmp_path, FakeClassifier("code", 3), local_models=())

    assert route.execute("q").model.label() == "codex/gpt-sol"


def test_no_capable_model_falls_back_to_strongest_installed(tmp_path):
    route, _ = router(tmp_path, FakeClassifier("raisonnement", 4), paths={"ollama": "/b/ollama"}, local_models=("a", "b"))

    result = route.execute("prouve ce théorème")

    assert result.model.label() == "ollama/a"
    assert "aucun modèle" in result.reason


def test_classifier_failure_uses_default_profile_and_still_launches(tmp_path):
    route, launcher = router(tmp_path, FakeClassifier(error=True))

    result = route.execute("q")

    assert result.fallback
    assert result.model.label() == "claude/sonnet"
    assert launcher.argv is not None


def test_use_bypasses_classifier(tmp_path):
    classifier = FakeClassifier("question_rapide", 0)
    route, launcher = router(tmp_path, classifier)

    result = route.execute("q", use="claude/opus")

    assert classifier.calls == 0
    assert result.model.label() == "claude/opus"


def test_use_agent_name_picks_best_model_of_that_agent(tmp_path):
    route, _ = router(tmp_path, FakeClassifier())

    assert route.execute("q", use="claude").model.label() == "claude/sonnet"


def test_use_unknown_agent_is_rejected(tmp_path):
    route, _ = router(tmp_path, FakeClassifier())

    with pytest.raises(EmptyInventory):
        route.execute("q", use="mistral")


def test_why_explains_without_launching(tmp_path):
    route, launcher = router(tmp_path, FakeClassifier("code", 4))

    result = route.execute("q", dry_run=True)

    assert launcher.argv is None
    assert "code" in result.reason and "4/4" in result.reason


def test_missing_inventory_asks_to_scan(tmp_path):
    route = RouteQuestion(JsonInventoryStore(tmp_path / "none.json"), FakeClassifier(), RecordingLauncher(), CATALOG,
                          JsonConversationStore(tmp_path / "c.json"))

    with pytest.raises(InventoryMissing, match="ask scan"):
        route.execute("q")


def jev_transport(answers=None, error=None):
    sent = {}

    def post(url, body, headers, timeout):
        sent.update(url=url, body=json.loads(body), headers=headers, timeout=timeout)
        if error:
            raise error
        return {"answers": answers, "usage": {"input_tokens": 40}}

    return post, sent


def test_jev_answers_drive_the_choice(tmp_path):
    post, sent = jev_transport({"tache": {"choice": "code", "confidence": 0.9}, "complexite": {"score": 4}})
    route, _ = router(tmp_path, JevClassifier("key", post=post))

    result = route.execute("refactor")

    assert result.model.label() == "codex/gpt-sol"
    assert sent["body"]["state"] == "refactor"
    assert sent["headers"]["Authorization"] == "Bearer key"
    assert sent["timeout"] <= 2


def test_jev_network_error_falls_back(tmp_path):
    post, _ = jev_transport(error=TimeoutError("slow"))
    route, launcher = router(tmp_path, JevClassifier("key", post=post))

    result = route.execute("q")

    assert result.fallback
    assert launcher.argv is not None


def test_missing_jev_key_falls_back(tmp_path):
    route, _ = router(tmp_path, JevClassifier(None))

    assert route.execute("q").fallback


def test_jev_errors_never_reveal_the_api_key(tmp_path):
    post, _ = jev_transport(error=ValueError("Invalid header value b'Bearer secret-key'"))
    route, _ = router(tmp_path, JevClassifier("secret-key", post=post))

    result = route.execute("q")

    assert "secret-key" not in result.reason
    assert "***" in result.reason
