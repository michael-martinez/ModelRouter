from __future__ import annotations

import io
import json

import pytest

from modelrouter.infra.jev_answerer import JevAnswerer
from modelrouter.infra.json_store import JsonConversationStore, JsonInventoryStore
from modelrouter.usecases.route_question import RouteQuestion
from modelrouter.usecases.scan_agents import ScanAgents
from tests.fakes import CATALOG, FakeClassifier, FakeClock, FakeLocalModels, FakeLocator, RecordingLauncher


class FakeJev:
    """Frontière HTTP de Jev : enregistre les requêtes, répond selon le type de question."""

    def __init__(self, noul=0.87, choice=None, confidence=0.92, error=None):
        self.requests = []
        self._noul, self._choice, self._confidence, self._error = noul, choice, confidence, error

    def __call__(self, url, body, headers, timeout):
        request = json.loads(body)
        self.requests.append(request)
        if self._error:
            raise self._error
        question = request["questions"]["reponse"]
        if question["type"] == "noul":
            answer = {"noul": self._noul}
        else:
            options = list(question["criteria"])
            choice = self._choice(request["state"], options) if callable(self._choice) else (self._choice or options[0])
            answer = {"choice": choice, "confidence": self._confidence}
        return {"answers": {"reponse": answer}, "usage": {"input_tokens": 30}}


class Session:
    def __init__(self, tmp_path, jev=None, env=None, classifier=None):
        inventory = JsonInventoryStore(tmp_path / "inventory.json")
        paths = {"claude": "/b/claude", "codex": "/b/codex"}
        ScanAgents(CATALOG, FakeLocator(paths), FakeLocalModels([]), inventory).execute(
            {"JEV_API_KEY": "k"} if env is None else env)
        self.jev = jev or FakeJev()
        self.screen = io.StringIO()
        self.classifier = classifier or FakeClassifier("classification", 1)
        self.launcher = RecordingLauncher()
        self.conversations = JsonConversationStore(tmp_path / "conversation.json")
        self.route = RouteQuestion(inventory, self.classifier, self.launcher, CATALOG, self.conversations,
                                   FakeClock(), answerer=JevAnswerer("k", post=self.jev, out=self.screen))
        self.announces = []

    def ask(self, question, **options):
        return self.route.execute(question, on_choice=lambda r: self.announces.append(r), **options)


def test_yes_no_question_is_answered_by_jev_without_launching_an_agent(tmp_path):
    session = Session(tmp_path)

    result = session.ask("Cet avis est-il une plainte : « livraison en retard, colis abîmé »")

    assert result.model.label() == "jev/jev-latest"
    assert session.launcher.calls == []
    assert session.jev.requests[0]["questions"]["reponse"]["type"] == "noul"
    assert "Oui (87 %)" in session.screen.getvalue()


def test_short_choice_question_goes_to_jev_even_when_classified_as_quick_question(tmp_path):
    session = Session(tmp_path, classifier=FakeClassifier("question_rapide", 0))

    result = session.ask("Pâtes ou riz ?")

    assert result.model.label() == "jev/jev-latest"
    assert session.launcher.calls == []


def test_long_question_with_or_is_not_sent_to_jev(tmp_path):
    session = Session(tmp_path, classifier=FakeClassifier("raisonnement", 2))
    question = "Pour une application de 50 écrans avec synchronisation hors ligne et partage multi-appareils, faut-il choisir SwiftUI ou UIKit ?"

    result = session.ask(question)

    assert result.model.label() != "jev/jev-latest"


def test_low_probability_reads_as_no(tmp_path):
    session = Session(tmp_path, jev=FakeJev(noul=0.1))

    session.ask("Est-ce que ce message est du spam : « réunion demain 10h »")

    assert "Non (90 %)" in session.screen.getvalue()


@pytest.mark.parametrize("question, options", [
    ("Cet avis est-il positif, négatif ou neutre : « appli correcte »", ["positif", "négatif", "neutre"]),
    ("Classe ce ticket en bug/ux/paiement : « le bouton payer ne répond pas »", ["bug", "ux", "paiement"]),
    ("« le bouton payer ne répond pas » : bug ou demande ?", ["bug", "demande"]),
])
def test_listed_options_become_jev_choices(tmp_path, question, options):
    session = Session(tmp_path, jev=FakeJev(choice=lambda state, opts: opts[-1]))

    session.ask(question)

    assert list(session.jev.requests[0]["questions"]["reponse"]["criteria"]) == options
    assert f"{options[-1]} (confiance 92 %)" in session.screen.getvalue()


def test_piped_lines_are_classified_one_by_one_with_a_summary(tmp_path):
    jev = FakeJev(choice=lambda state, opts: "bug" if "plante" in state else "ux")
    session = Session(tmp_path, jev=jev)

    session.ask("classe en bug/ux/paiement", piped="l'app plante au lancement\n\nmenu illisible\nça plante encore\n")

    states = [r["state"] for r in jev.requests]
    assert states == ["l'app plante au lancement", "menu illisible", "ça plante encore"]
    screen = session.screen.getvalue()
    assert "menu illisible → ux" in screen
    assert "bug 67 %" in screen and "ux 33 %" in screen


def test_open_classification_request_falls_back_to_an_llm(tmp_path):
    session = Session(tmp_path)

    result = session.ask("Propose une taxonomie pour ces avis")

    assert session.jev.requests == []
    assert result.model.agent != "jev"
    assert session.launcher.calls
    assert "repli" in result.reason


def test_jev_error_falls_back_to_an_llm(tmp_path):
    session = Session(tmp_path, jev=FakeJev(error=TimeoutError("slow")))

    result = session.ask("Cet avis est-il une plainte : « nul »")

    assert result.model.agent != "jev"
    assert session.launcher.calls


def test_forcing_jev_on_an_open_question_fails_cleanly(tmp_path):
    session = Session(tmp_path)

    result = session.ask("Propose une taxonomie", use="jev")

    assert result.exit_code == 1
    assert session.launcher.calls == []


def test_jev_answers_are_kept_in_the_conversation(tmp_path):
    session = Session(tmp_path)
    session.ask("Cet avis est-il une plainte : « colis abîmé »")
    session.classifier.answer_with("redaction", 2)

    session.ask("rédige une réponse à cet avis")

    assert "Oui (87 %)" in session.launcher.prompt()


def test_jev_is_only_available_with_its_key(tmp_path):
    session = Session(tmp_path, env={})

    result = session.ask("Cet avis est-il une plainte : « nul »")

    assert result.model.agent != "jev"


def test_piped_content_is_given_to_the_llm(tmp_path):
    session = Session(tmp_path, classifier=FakeClassifier("redaction", 2))

    session.ask("résume ce texte", piped="Le module X gère la synchro.")

    assert "Le module X gère la synchro." in session.launcher.prompt()
    assert "résume ce texte" in session.launcher.prompt()


def test_agent_failing_without_output_hands_over_to_the_next_model(tmp_path):
    session = Session(tmp_path, classifier=FakeClassifier("code", 4))
    session.launcher.then("", 41).then("voici", 0)

    result = session.ask("refactor")

    assert [argv[0] for argv in session.launcher.calls] == ["/b/codex", "/b/claude"]
    assert result.exit_code == 0
    assert "repli" in session.announces[-1].reason


def test_agent_failing_after_answering_is_not_retried(tmp_path):
    session = Session(tmp_path, classifier=FakeClassifier("code", 4))
    session.launcher.then("moitié de réponse", 1)

    result = session.ask("refactor")

    assert len(session.launcher.calls) == 1
    assert result.exit_code == 1


def test_interrupted_agent_is_not_retried(tmp_path):
    session = Session(tmp_path, classifier=FakeClassifier("code", 4))
    session.launcher.then("", -15)

    session.ask("refactor")

    assert len(session.launcher.calls) == 1


def test_why_on_an_open_question_announces_the_llm_not_jev(tmp_path):
    session = Session(tmp_path)

    result = session.ask("Propose une taxonomie pour ces avis", dry_run=True)

    assert [r.model.agent for r in session.announces] == [result.model.agent]
    assert result.model.agent != "jev"


def test_trivial_non_classification_question_never_considers_jev(tmp_path):
    session = Session(tmp_path, classifier=FakeClassifier("question_rapide", 0))

    result = session.ask("capitale de l'Australie ?")

    assert result.model.agent != "jev"
    assert "repli" not in result.reason
