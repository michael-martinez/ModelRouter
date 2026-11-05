from __future__ import annotations

from modelrouter.infra.json_store import JsonConversationStore, JsonInventoryStore
from modelrouter.usecases.route_question import RouteQuestion
from modelrouter.usecases.scan_agents import ScanAgents
from tests.fakes import CATALOG, FakeClassifier, FakeClock, FakeLocalModels, FakeLocator, RecordingLauncher, SessionIds

ALL = {"claude": "/b/claude", "codex": "/b/codex"}


class Session:
    def __init__(self, tmp_path, paths=ALL):
        inventory = JsonInventoryStore(tmp_path / "inventory.json")
        ScanAgents(CATALOG, FakeLocator(paths), FakeLocalModels([]), inventory).execute({})
        self.classifier = FakeClassifier("code", 2)
        self.launcher = RecordingLauncher()
        self.clock = FakeClock()
        self.route = RouteQuestion(inventory, self.classifier, self.launcher, CATALOG,
                                   JsonConversationStore(tmp_path / "conversation.json"), self.clock,
                                   new_session_id=SessionIds())

    def ask(self, question, answer="réponse", **options):
        self.launcher.answer = answer
        return self.route.execute(question, **options)

    def argv(self):
        return self.launcher.argv


def test_first_question_opens_a_native_session_with_the_raw_question(tmp_path):
    session = Session(tmp_path)

    session.ask("écris un parser JSON en Swift")

    assert session.argv()[-3:] == ["--session-id", "s1", "écris un parser JSON en Swift"]


def test_follow_up_resumes_the_native_session_without_reinjecting_history(tmp_path):
    session = Session(tmp_path)
    session.ask("écris un parser JSON en Swift", answer="struct Parser { ... }")

    session.ask("et en Kotlin ?")

    assert session.argv()[-3:] == ["--resume", "s1", "et en Kotlin ?"]


def test_model_changes_inside_the_same_session(tmp_path):
    session = Session(tmp_path)
    session.ask("petite fonction")
    session.classifier.answer_with("code", 4)

    result = session.ask("refactor complet du module")

    assert result.model.label() == "claude/opus"
    assert session.argv()[3] == "opus"
    assert session.argv()[-3:-1] == ["--resume", "s1"]


def test_conversation_sticks_to_its_agent_when_it_has_the_level(tmp_path):
    session = Session(tmp_path)
    session.ask("petite fonction")
    session.classifier.answer_with("code", 4)

    result = session.ask("question dure")

    assert result.model.label() == "claude/opus"
    assert "on reste sur claude" in result.reason


def test_without_conversation_the_cheapest_capable_model_wins(tmp_path):
    session = Session(tmp_path)
    session.classifier.answer_with("code", 4)

    assert session.ask("question dure").model.label() == "codex/gpt-sol"


def test_agent_switch_only_when_the_current_one_lacks_the_level_and_carries_history(tmp_path):
    session = Session(tmp_path)
    session.ask("capitale de l'Australie ?", answer="Canberra")
    session.classifier.answer_with("recherche_web", 3)

    result = session.ask("actus de la ville cette semaine ?")

    assert result.model.label() == "codex/gpt-sol"
    assert "claude n'a pas le niveau" in result.reason
    assert "Canberra" in session.launcher.prompt()


def test_agent_without_native_session_gets_history_injected(tmp_path):
    session = Session(tmp_path, paths={"codex": "/b/codex"})
    session.ask("écris un parser JSON en Swift", answer="struct Parser { ... }")

    session.ask("et en Kotlin ?")

    prompt = session.launcher.prompt()
    assert "struct Parser { ... }" in prompt
    assert prompt.rstrip().endswith("et en Kotlin ?")
    assert "--resume" not in session.argv()


def test_back_on_native_session_only_missed_exchanges_are_injected(tmp_path):
    session = Session(tmp_path)
    session.ask("capitale de l'Australie ?", answer="Canberra")
    session.classifier.answer_with("recherche_web", 3)
    session.ask("actus de la ville ?", answer="Floriade ouvre samedi")
    session.classifier.answer_with("code", 4)
    session.ask("et un script pour scraper ça ?", use="claude")

    prompt = session.launcher.prompt()
    assert session.argv()[-3:-1] == ["--resume", "s1"]
    assert "Floriade ouvre samedi" in prompt
    assert "Canberra" not in prompt


def test_lost_session_restarts_with_a_fresh_one_and_history(tmp_path):
    session = Session(tmp_path)
    session.ask("capitale de l'Australie ?", answer="Canberra")
    session.launcher.then("", 1)

    result = session.ask("et sa population ?")

    assert result.exit_code == 0
    assert session.argv()[-3:-1] == ["--session-id", "s2"]
    assert "Canberra" in session.launcher.prompt()
    assert session.launcher.calls[-2][-3:-1] == ["--resume", "s1"]


def test_failing_agent_is_dropped_as_a_whole(tmp_path):
    session = Session(tmp_path)
    session.launcher.then("", 41).then("ok", 0)

    session.ask("petite fonction")

    assert [argv[0] for argv in session.launcher.calls] == ["/b/claude", "/b/codex"]


def test_jev_classifies_the_follow_up_with_the_previous_question(tmp_path):
    session = Session(tmp_path)
    session.ask("prouve que racine de 2 est irrationnelle")

    session.ask("et pour racine de 3 ?")

    assert "prouve que racine de 2 est irrationnelle" in session.classifier.texts[-1]
    assert "et pour racine de 3 ?" in session.classifier.texts[-1]


def test_conversation_expires_after_30_minutes_of_inactivity(tmp_path):
    session = Session(tmp_path)
    session.ask("première question", answer="première réponse")
    session.clock.advance_minutes(31)

    session.ask("nouvelle question")

    assert session.argv()[-3:] == ["--session-id", "s2", "nouvelle question"]


def test_new_option_starts_a_fresh_conversation(tmp_path):
    session = Session(tmp_path)
    session.ask("première question")

    session.ask("autre sujet", new=True)
    session.ask("suite")

    assert session.argv()[-3:] == ["--resume", "s2", "suite"]


def test_failed_answers_are_not_remembered(tmp_path):
    session = Session(tmp_path)
    session.launcher.exit_code = 1
    session.ask("question qui plante", answer="erreur")
    session.launcher.exit_code = 0

    session.ask("suite")

    assert session.argv()[-3:-1] == ["--session-id", "s2"]


def test_why_does_not_touch_the_conversation(tmp_path):
    session = Session(tmp_path)
    session.ask("première question")

    preview = session.ask("simulation", dry_run=True)
    session.ask("suite")

    assert "--resume" in preview.command
    assert session.argv()[-3:] == ["--resume", "s1", "suite"]


def test_only_the_last_five_exchanges_are_injected(tmp_path):
    session = Session(tmp_path, paths={"codex": "/b/codex"})
    for i in range(1, 8):
        session.ask(f"question {i}")

    session.ask("suite")

    assert "question 2" not in session.launcher.prompt()
    assert "question 3" in session.launcher.prompt()


def test_long_answers_are_truncated_in_the_injected_context(tmp_path):
    session = Session(tmp_path, paths={"codex": "/b/codex"})
    session.ask("raconte", answer="x" * 10_000)

    session.ask("suite")

    assert len(session.launcher.prompt()) < 3_000


def test_only_the_last_answer_is_injected_so_a_bad_one_cannot_be_copied_for_long(tmp_path):
    session = Session(tmp_path, paths={"codex": "/b/codex"})
    session.ask("première", answer="Alpha")
    session.ask("deuxième", answer="Beta")
    session.ask("troisième", answer="Gamma")

    session.ask("suite")

    prompt = session.launcher.prompt()
    assert "Alpha" not in prompt
    assert "Beta" not in prompt
    assert "Gamma" in prompt
    assert "deuxième" in prompt
