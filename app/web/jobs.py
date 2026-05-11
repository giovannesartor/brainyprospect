"""Gerenciador in-memory de jobs assíncronos (hunts).

Para produção em múltiplos workers usar Redis/Celery.
"""
from __future__ import annotations

import threading
import time
import traceback
import uuid
from typing import Any, Callable

from app.utils.logger import get_logger

log = get_logger("jobs")


class _Job:
    __slots__ = ("id", "status", "progress", "message", "started_at", "ended_at",
                 "result", "error", "user_id", "kind", "logs")

    def __init__(self, kind: str, user_id: int | None):
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind
        self.user_id = user_id
        self.status = "pending"  # pending | running | done | error
        self.progress = 0
        self.message = ""
        self.started_at = time.time()
        self.ended_at: float | None = None
        self.result: Any = None
        self.error: str = ""
        self.logs: list[dict[str, Any]] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration": (self.ended_at or time.time()) - self.started_at,
            "result": self.result,
            "error": self.error,
            "logs": self.logs[-50:],
        }


class JobManager:
    def __init__(self):
        self._jobs: dict[str, _Job] = {}
        self._lock = threading.Lock()

    def submit(self, kind: str, target: Callable[[Callable[[str, int], None]], Any],
               user_id: int | None = None) -> str:
        job = _Job(kind=kind, user_id=user_id)
        with self._lock:
            self._jobs[job.id] = job

        def progress(msg: str, pct: int) -> None:
            job.message = msg
            try:
                job.progress = max(0, min(100, int(pct)))
            except Exception:
                pass
            job.logs.append({"t": time.time(), "msg": msg, "pct": job.progress})

        def runner():
            job.status = "running"
            try:
                res = target(progress)
                job.result = res
                job.status = "done"
                job.progress = 100
                job.message = "Concluído"
            except Exception as exc:  # noqa: BLE001
                log.error(f"Job {job.id} falhou: {exc}\n{traceback.format_exc()}")
                job.error = f"{type(exc).__name__}: {exc}"
                job.status = "error"
            finally:
                job.ended_at = time.time()

        threading.Thread(target=runner, name=f"job-{job.id}", daemon=True).start()
        return job.id

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.to_dict() if job else None

    def list_for(self, user_id: int | None = None, limit: int = 30) -> list[dict[str, Any]]:
        with self._lock:
            jobs = list(self._jobs.values())
        if user_id is not None:
            jobs = [j for j in jobs if j.user_id == user_id or j.user_id is None]
        jobs.sort(key=lambda j: j.started_at, reverse=True)
        return [j.to_dict() for j in jobs[:limit]]

    def cleanup(self, max_age_seconds: int = 3600 * 6) -> int:
        cutoff = time.time() - max_age_seconds
        removed = 0
        with self._lock:
            for jid in list(self._jobs.keys()):
                j = self._jobs[jid]
                if j.ended_at and j.ended_at < cutoff:
                    del self._jobs[jid]
                    removed += 1
        return removed


JOBS = JobManager()
