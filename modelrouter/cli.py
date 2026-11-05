from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from modelrouter.adapters.ports import (AccountModelLister, BinaryLocator, Classifier, ClosedAnswerer, ConversationStore,
                                        InventoryStore, Launcher, LocalModelLister)
from modelrouter.domain.conversation import Conversation
from modelrouter.domain.inventory import EmptyInventory
from modelrouter.usecases.route_question import InventoryMissing, RouteQuestion
from modelrouter.usecases.scan_agents import ScanAgents

CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.json"

USAGE = """ask scan                      détecte les agents et modèles installés
ask [--why] [--use X] [--new] QUESTION  route la question vers le modèle le plus adapté
cat f | ask "classe en A/B/C"   Jev classe chaque ligne et donne la répartition
                              (reprend la session de l'agent 30 min par dossier, --new repart de zéro)"""


@dataclass
class Dependencies:
    catalog: dict
    store: InventoryStore
    classifier: Classifier
    launcher: Launcher
    locator: BinaryLocator
    local_models: LocalModelLister
    env: dict
    conversations: ConversationStore
    answerer: ClosedAnswerer = None
    read_piped: object = field(default=lambda: None)
    account_models: AccountModelLister = None


def default_dependencies() -> Dependencies:
    from modelrouter.infra.codex_models import CodexAccountModels
    from modelrouter.infra.jev_answerer import JevAnswerer
    from modelrouter.infra.jev_classifier import JevClassifier
    from modelrouter.infra.json_store import JsonConversationStore, JsonInventoryStore
    from modelrouter.infra.system import OllamaModelLister, StreamingLauncher, SystemBinaryLocator

    return Dependencies(
        catalog=json.loads(CATALOG_PATH.read_text(encoding="utf-8")),
        store=JsonInventoryStore(),
        classifier=JevClassifier(os.environ.get("JEV_API_KEY")),
        launcher=StreamingLauncher(),
        locator=SystemBinaryLocator(),
        local_models=OllamaModelLister(),
        env=dict(os.environ),
        conversations=JsonConversationStore.for_directory(os.getcwd()),
        answerer=JevAnswerer(os.environ.get("JEV_API_KEY")),
        read_piped=read_stdin,
        account_models=CodexAccountModels(),
    )


def read_stdin() -> str | None:
    if sys.stdin is None or sys.stdin.isatty():
        return None
    return sys.stdin.read() or None


def run_scan(deps: Dependencies, out) -> int:
    report = ScanAgents(deps.catalog, deps.locator, deps.local_models, deps.store, deps.account_models).execute(deps.env)
    print(f"Agents trouvés : {', '.join(report.found_agents) or 'aucun'}", file=out)
    for label in report.inventory.labels():
        print(f"  • {label}", file=out)
    for hint in report.hints:
        print(f"  ⚠ {hint}", file=out)
    return 0 if report.found_agents else 1


def run_ask(deps: Dependencies, argv: list, out) -> int:
    parser = argparse.ArgumentParser(prog="ask", usage=USAGE)
    parser.add_argument("--why", action="store_true", help="affiche le choix sans lancer l'agent")
    parser.add_argument("--use", help="force un agent (claude) ou un modèle (claude/opus)")
    parser.add_argument("--new", action="store_true", help="démarre une nouvelle conversation")
    parser.add_argument("--write", action="store_true", help="autorise l'agent à modifier les fichiers du dossier (Codex)")
    parser.add_argument("question", nargs="+")
    args = parser.parse_args(argv)
    route = RouteQuestion(deps.store, deps.classifier, deps.launcher, deps.catalog, deps.conversations,
                         answerer=deps.answerer)
    try:
        result = route.execute(" ".join(args.question), use=args.use, dry_run=args.why, new=args.new, write=args.write,
                               piped=None if args.why else deps.read_piped(),
                               on_choice=lambda r: print(f"→ {r.model.label()} · {r.elapsed_ms} ms · {r.reason}", file=out, flush=True))
    except (InventoryMissing, EmptyInventory) as error:
        print(error, file=out)
        return 1
    if args.why and result.command:
        print(f"  $ {' '.join(result.command)}", file=out)
    if result.exit_code:
        print(f"✗ {result.reason}", file=out)
    return result.exit_code


def main(argv: list = None, deps: Dependencies = None, out=sys.stderr) -> int:
    argv = sys.argv[1:] if argv is None else argv
    deps = deps or default_dependencies()
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE, file=out)
        return 0
    if argv == ["scan"]:
        return run_scan(deps, out)
    if argv == ["--reset"]:
        deps.conversations.save(Conversation.fresh())
        print("Conversation réinitialisée pour ce dossier.", file=out)
        return 0
    return run_ask(deps, argv, out)


if __name__ == "__main__":
    sys.exit(main())
