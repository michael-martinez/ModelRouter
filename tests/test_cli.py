from __future__ import annotations

import io
import json

from modelrouter.cli import CATALOG_PATH, Dependencies, main
from modelrouter.infra.json_store import JsonConversationStore, JsonInventoryStore
from tests.fakes import FakeClassifier, FakeLocalModels, FakeLocator, RecordingLauncher


def deps(tmp_path, classifier=None, paths=None, env=None):
    return Dependencies(
        catalog=json.loads(CATALOG_PATH.read_text(encoding="utf-8")),
        store=JsonInventoryStore(tmp_path / "inventory.json"),
        classifier=classifier or FakeClassifier("code", 4),
        launcher=RecordingLauncher(),
        locator=FakeLocator(paths if paths is not None else {"claude": "/b/claude", "gemini": "/b/gemini"}),
        local_models=FakeLocalModels([]),
        env=env or {},
        conversations=JsonConversationStore(tmp_path / "conversation.json"),
    )


def run(argv, dependencies):
    out = io.StringIO()
    code = main(argv, dependencies, out)
    return code, out.getvalue()


def test_scan_then_why_shows_choice_without_launching(tmp_path):
    d = deps(tmp_path)

    assert run(["scan"], d)[0] == 0
    code, output = run(["--why", "refactor", "ce", "module"], d)

    assert code == 0
    assert "claude/opus" in output and "/b/claude -p --model opus" in output
    assert d.launcher.argv is None


def test_ask_launches_the_chosen_agent_with_the_whole_question(tmp_path):
    d = deps(tmp_path, FakeClassifier("question_rapide", 1))
    run(["scan"], d)

    code, output = run(["capitale", "de", "l'Australie", "?"], d)

    assert code == 0
    assert d.launcher.argv[:4] == ["/b/claude", "-p", "--model", "haiku"]
    assert d.launcher.prompt() == "capitale de l'Australie ?"
    assert "→ claude/haiku" in output


def test_ask_before_scan_explains_what_to_do(tmp_path):
    code, output = run(["salut"], deps(tmp_path))

    assert code == 1
    assert "ask scan" in output


def test_scan_without_any_agent_fails_with_hints(tmp_path):
    code, output = run(["scan"], deps(tmp_path, paths={}, env={"OPENAI_API_KEY": "sk"}))

    assert code == 1
    assert "OPENAI_API_KEY" in output


def test_follow_up_through_cli_keeps_the_thread(tmp_path):
    d = deps(tmp_path, FakeClassifier("question_rapide", 1))
    run(["scan"], d)
    d.launcher.answer = "Canberra"
    run(["capitale", "de", "l'Australie", "?"], d)

    session = d.launcher.argv[-2]
    run(["et", "sa", "population", "?"], d)

    assert d.launcher.argv[-3:] == ["--resume", session, "et sa population ?"]


def test_new_flag_drops_the_thread(tmp_path):
    d = deps(tmp_path, FakeClassifier("question_rapide", 1))
    run(["scan"], d)
    run(["capitale", "de", "l'Australie", "?"], d)

    run(["--new", "bonjour"], d)

    assert d.launcher.prompt() == "bonjour"


def test_agent_failure_is_reported_as_exit_code(tmp_path):
    d = deps(tmp_path, FakeClassifier("question_rapide", 1))
    run(["scan"], d)
    d.launcher.exit_code = 2

    assert run(["salut"], d)[0] == 2
