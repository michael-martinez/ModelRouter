from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, replace

from modelrouter.adapters.ports import (Classifier, ClassifierError, ClosedAnswerer, ConversationStore, InventoryStore,
                                        LaunchOutcome, Launcher)
from modelrouter.domain.conversation import Conversation
from modelrouter.domain.inventory import Choice
from modelrouter.domain.model import Model
from modelrouter.domain.task_profile import TaskProfile

CLOSED_MAX_CHARS = 120
JEV_CANNOT_ANSWER ="Jev ne répond qu'aux questions oui/non ou à options listées (A, B ou C / A/B/C)"


class InventoryMissing(Exception):
    pass


@dataclass(frozen=True)
class RouteResult:
    model: Model
    reason: str
    fallback: bool
    elapsed_ms: int
    exit_code: int = 0
    command: tuple = ()


@dataclass(frozen=True)
class Run:
    outcome: LaunchOutcome | None
    session: str | None = None


def new_uuid() -> str:
    return str(uuid.uuid4())


class RouteQuestion:
    def __init__(self, store: InventoryStore, classifier: Classifier, launcher: Launcher, catalog: dict,
                 conversations: ConversationStore, clock=time.time, answerer: ClosedAnswerer = None,
                 new_session_id=new_uuid):
        self._store = store
        self._classifier = classifier
        self._launcher = launcher
        self._default_profile = TaskProfile.from_dict(catalog["default_profile"])
        self._conversations = conversations
        self._clock = clock
        self._answerer = answerer
        self._new_session_id = new_session_id

    def execute(self, question: str, use: str | None = None, dry_run: bool = False, on_choice=None,
                new: bool = False, piped: str | None = None, write: bool = False) -> RouteResult:
        inventory = self._store.load()
        if inventory is None:
            raise InventoryMissing("Aucun inventaire : lance d'abord `ask scan`.")
        conversation = Conversation.fresh() if new else self._conversations.load().active_at(self._clock())
        started = time.monotonic()
        if use:
            inventory = inventory.only(use)
            profile, fallback, note = self._default_profile, False, f"forcé sur {use}"
        else:
            profile, fallback, note = self._classify(conversation.classification_text(question, piped))
        sticky_agent = None if use else conversation.current_agent()
        closed_jev = None if use else self._closed_question_jev(inventory, question)
        while True:
            if use:
                choice = inventory.forced_for(profile)
            elif closed_jev is not None:
                choice = Choice(closed_jev, "question fermée → Jev")
                closed_jev = None
            elif sticky_agent:
                choice = inventory.best_for_continuing(profile, sticky_agent)
            else:
                choice = inventory.best_for(profile)
            model = choice.model
            if model.is_builtin() and not self._can_answer(question):
                remaining = inventory.without(model)
                if not remaining.can_serve(profile):
                    return RouteResult(model, JEV_CANNOT_ANSWER, fallback, 0, exit_code=1)
                inventory, note = remaining, f"repli : {JEV_CANNOT_ANSWER}"
                continue
            reason = f"{choice.reason} ({note})" if note else choice.reason
            result = RouteResult(model, reason, fallback, int((time.monotonic() - started) * 1000),
                                 command=self._preview(model, conversation, "workspace-write" if write else "read-only"))
            if on_choice:
                on_choice(result)
            if dry_run:
                return result
            run = self._run(model, conversation, question, piped, "workspace-write" if write else "read-only")
            outcome = run.outcome
            if outcome is not None and outcome.succeeded():
                self._conversations.save(conversation.record(question, outcome.output, model.label(), model.agent,
                                                             self._clock(), run.session, sticky=not model.is_builtin()))
                return replace(result, exit_code=0)
            failure = JEV_CANNOT_ANSWER if outcome is None else f"{model.label()} a échoué (code {outcome.exit_code})"
            remaining = inventory.without(model) if model.is_builtin() else inventory.without_agent(model.agent)
            retry = outcome is None or outcome.worth_retrying()
            if not (retry and remaining.can_serve(profile)):
                return replace(result, reason=failure, exit_code=1 if outcome is None else outcome.exit_code)
            inventory, note = remaining, f"repli : {failure}"

    def _preview(self, model: Model, conversation: Conversation, sandbox: str = "read-only") -> tuple:
        if model.is_builtin():
            return ()
        session = conversation.session_for(model.agent)
        resuming = bool(session) and model.supports_sessions()
        return tuple(model.command_for("…", session or "<nouvelle session>", resuming, sandbox=sandbox))

    def _run(self, model: Model, conversation: Conversation, question: str, piped: str | None,
             sandbox: str = "read-only") -> Run:
        if model.is_builtin():
            return Run(self._answerer.answer(question, piped) if self._answerer else None)
        if not model.supports_sessions():
            return Run(self._launcher.launch(
                model.command_for(conversation.prompt_for(question, piped), sandbox=sandbox)))
        session = conversation.session_for(model.agent)
        if session:
            prompt = conversation.prompt_for(question, piped, model.agent, resuming=True)
            outcome = self._launcher.launch(model.command_for(prompt, session, resuming=True, sandbox=sandbox))
            if not outcome.worth_retrying():
                return Run(outcome, session)
        session = self._new_session_id()
        prompt = conversation.prompt_for(question, piped, model.agent, resuming=False)
        return Run(self._launcher.launch(model.command_for(prompt, session, sandbox=sandbox)), session)

    def _closed_question_jev(self, inventory, question: str):
        """Une question fermée courte va d'abord à Jev, quelle que soit la catégorie donnée par le classifieur."""
        if self._answerer is None or len(question) > CLOSED_MAX_CHARS or not self._answerer.handles(question):
            return None
        return next((m for m in inventory.models() if m.is_builtin()), None)

    def _can_answer(self, question: str) -> bool:
        return self._answerer is not None and self._answerer.handles(question)

    def _classify(self, text: str) -> tuple:
        try:
            return self._classifier.profile(text), False, ""
        except ClassifierError as error:
            return self._default_profile, True, f"Jev indisponible : {error}, profil par défaut"
