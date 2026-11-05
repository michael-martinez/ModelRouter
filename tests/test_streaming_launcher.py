from __future__ import annotations

import io

from modelrouter.infra.system import StreamingLauncher


def test_output_is_shown_and_captured():
    screen = io.BytesIO()

    outcome = StreamingLauncher(screen).launch(["/bin/sh", "-c", "printf 'Canberra'"])

    assert screen.getvalue() == b"Canberra"
    assert outcome.output == "Canberra"
    assert outcome.succeeded()


def test_failing_agent_reports_its_exit_code():
    outcome = StreamingLauncher(io.BytesIO()).launch(["/bin/sh", "-c", "exit 3"])

    assert outcome.exit_code == 3


def test_missing_binary_is_a_failure_not_a_crash():
    outcome = StreamingLauncher(io.BytesIO()).launch(["/nope/agent"])

    assert not outcome.succeeded()
