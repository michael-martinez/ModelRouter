from __future__ import annotations

from modelrouter.domain.model import Model

SKILLS = {"code": 4, "raisonnement": 3, "redaction": 3, "recherche_web": 3, "multimodal": 3,
          "classification": 4, "question_rapide": 4}
CODEX_COMMAND = ("/b/codex", "exec", "-s", "{sandbox}", "-m", "{model}", "{prompt}")


def codex_model():
    return Model("codex", "gpt-6-luna", 1, SKILLS, CODEX_COMMAND, False, (), ())


def test_codex_runs_read_only_by_default():
    argv = codex_model().command_for("explique")

    assert argv[argv.index("-s") + 1] == "read-only"


def test_codex_can_be_given_write_access_for_a_modification_request():
    argv = codex_model().command_for("corrige le bug", sandbox="workspace-write")

    assert argv[argv.index("-s") + 1] == "workspace-write"
    assert argv[-1] == "corrige le bug"
