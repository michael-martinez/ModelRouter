from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from modelrouter.adapters.ports import BinaryLocator, Launcher, LaunchOutcome, LocalModelLister

HOME = Path.home()
EXTRA_DIRS = [
    HOME / ".local/bin",
    Path("/opt/homebrew/bin"),
    Path("/usr/local/bin"),
    HOME / ".npm-global/bin",
    HOME / ".bun/bin",
    HOME / ".cargo/bin",
    HOME / ".codex/bin",
    Path("/Applications/Codex.app/Contents/Resources"),
    Path("/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin"),
    Path("/Applications/Ollama.app/Contents/Resources"),
]


class SystemBinaryLocator(BinaryLocator):
    """PATH, puis répertoires d'installation courants, puis alias du shell de l'utilisateur."""

    def locate(self, binary: str) -> str | None:
        found = shutil.which(binary)
        if found:
            return found
        for directory in EXTRA_DIRS:
            candidate = directory / binary
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
        return self._from_shell_alias(binary)

    def _from_shell_alias(self, binary: str) -> str | None:
        shell = os.environ.get("SHELL", "/bin/zsh")
        try:
            output = subprocess.run([shell, "-ic", f"whence -p {binary} || alias {binary}"],
                                    capture_output=True, text=True, timeout=5).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            return None
        target = output.split("=", 1)[-1].strip("'\" ").split(" ")[0]
        target = os.path.expanduser(target)
        return target if target and os.path.isfile(target) and os.access(target, os.X_OK) else None


class OllamaModelLister(LocalModelLister):
    def list_models(self, binary_path: str) -> list:
        try:
            output = subprocess.run([binary_path, "list"], capture_output=True, text=True, timeout=10).stdout
        except (OSError, subprocess.TimeoutExpired):
            return []
        return [line.split()[0] for line in output.splitlines()[1:] if line.strip()]


class StreamingLauncher(Launcher):
    """Affiche la sortie de l'agent au fil de l'eau et la garde pour la conversation."""

    def __init__(self, out=None):
        self._out = out or sys.stdout.buffer

    def launch(self, argv: list) -> LaunchOutcome:
        captured = bytearray()
        try:
            process = subprocess.Popen(argv, stdout=subprocess.PIPE)
        except OSError as error:
            return LaunchOutcome(str(error), 127)
        try:
            while True:
                chunk = os.read(process.stdout.fileno(), 4096)
                if not chunk:
                    break
                captured += chunk
                self._out.write(chunk)
                self._out.flush()
            exit_code = process.wait()
        except KeyboardInterrupt:
            process.terminate()
            exit_code = process.wait()
        return LaunchOutcome(captured.decode("utf-8", errors="replace"), exit_code)
