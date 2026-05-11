"""Notificações nativas multiplataforma (com fallback silencioso)."""
from __future__ import annotations

import platform
import shlex
import subprocess


def notify(title: str, message: str, sound: bool = True) -> None:
    """Envia notificação. No macOS usa osascript; demais SOs: noop."""
    try:
        if platform.system() == "Darwin":
            safe_title = title.replace('"', "'")
            safe_msg = message.replace('"', "'")
            script = (f'display notification "{safe_msg}" with title "{safe_title}"'
                      + (' sound name "Glass"' if sound else ''))
            subprocess.Popen(["osascript", "-e", script],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:  # noqa: BLE001
        pass
