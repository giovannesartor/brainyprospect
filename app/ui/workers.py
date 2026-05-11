"""Workers QThread para tarefas longas (não travar a UI)."""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QThread, Signal


class Worker(QObject):
    progress = Signal(str, int)        # (mensagem, percentual)
    finished = Signal(object)          # resultado
    failed = Signal(str)               # mensagem de erro

    def __init__(self, fn: Callable[..., Any], *args, with_progress: bool = False, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._with_progress = with_progress

    def run(self) -> None:
        try:
            if self._with_progress:
                result = self._fn(*self._args, progress=self.progress.emit, **self._kwargs)
            else:
                result = self._fn(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as e:  # noqa: BLE001
            from app.utils.logger import get_logger
            get_logger("worker").exception(f"Tarefa falhou: {e}")
            self.failed.emit(str(e))


def run_in_thread(parent: QObject, worker: Worker,
                  on_finished: Callable[[Any], None] | None = None,
                  on_failed: Callable[[str], None] | None = None,
                  on_progress: Callable[[str, int], None] | None = None) -> QThread:
    thread = QThread(parent)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    if on_finished:
        worker.finished.connect(on_finished)
    if on_failed:
        worker.failed.connect(on_failed)
    if on_progress:
        worker.progress.connect(on_progress)
    worker.finished.connect(thread.quit)
    worker.failed.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread
