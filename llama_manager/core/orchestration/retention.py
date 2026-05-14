from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, select

from llama_manager.core.persistence.models.orchestration import ArtifactOrm, JobAttemptOrm, JobEventOrm, JobOrm


class OrchestrationRetentionQueries:
    def __init__(self, store, row_to_job):
        self.store = store
        self._row_to_job = row_to_job

    def prune_history(self, retention_days: int = 30) -> dict[str, int]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        pruned_jobs = 0
        pruned_attempts = 0
        pruned_events = 0
        terminal = ("completed", "failed", "canceled", "timed_out")
        with self.store.tx() as session:
            job_ids = list(
                session.execute(
                    select(JobOrm.id)
                    .where(JobOrm.status.in_(terminal))
                    .where(JobOrm.completed_at.is_not(None))
                    .where(JobOrm.completed_at < cutoff)
                ).scalars().all()
            )
            for chunk in self._chunks(job_ids, size=500):
                attempt_ids = select(JobAttemptOrm.id).where(JobAttemptOrm.job_id.in_(chunk))
                pruned_events += max(session.execute(delete(JobEventOrm).where(JobEventOrm.attempt_id.in_(attempt_ids))).rowcount or 0, 0)
                pruned_events += max(session.execute(delete(JobEventOrm).where(JobEventOrm.job_id.in_(chunk))).rowcount or 0, 0)
                session.execute(delete(ArtifactOrm).where(ArtifactOrm.job_id.in_(chunk)))
                pruned_attempts += max(session.execute(delete(JobAttemptOrm).where(JobAttemptOrm.job_id.in_(chunk))).rowcount or 0, 0)
                pruned_jobs += max(session.execute(delete(JobOrm).where(JobOrm.id.in_(chunk))).rowcount or 0, 0)
        return {"pruned_jobs": pruned_jobs, "pruned_attempts": pruned_attempts, "pruned_events": pruned_events}

    def list_terminal_jobs_before(self, cutoff_iso: str, limit: int = 1000) -> list[dict[str, Any]]:
        with self.store.tx() as session:
            rows = session.execute(
                select(JobOrm)
                .where(JobOrm.status.in_(("completed", "failed", "canceled", "timed_out")))
                .where(JobOrm.completed_at.is_not(None))
                .where(JobOrm.completed_at < cutoff_iso)
                .order_by(JobOrm.completed_at.asc())
                .limit(limit)
            ).scalars().all()
        out = []
        for row in rows:
            job = self._row_to_job(row)
            job["artifacts"] = self.list_artifacts(job["id"])
            out.append(job)
        return out

    def list_artifacts(self, job_id: str) -> list[dict[str, Any]]:
        with self.store.tx() as session:
            rows = session.execute(
                select(ArtifactOrm)
                .where(ArtifactOrm.job_id == job_id)
                .order_by(ArtifactOrm.created_at.asc())
            ).scalars().all()
        out = []
        for row in rows:
            item = {
                "id": row.id,
                "job_id": row.job_id,
                "attempt_id": row.attempt_id,
                "kind": row.kind,
                "uri": row.uri,
                "created_at": row.created_at,
                "meta": json.loads(row.meta_json) if row.meta_json else None,
            }
            out.append(item)
        return out

    def job_counts_by_status(self) -> dict[str, int]:
        with self.store.tx() as session:
            rows = session.execute(
                select(JobOrm.status, func.count()).group_by(JobOrm.status)
            ).all()
        return {status: int(count) for status, count in rows}

    def _chunks(self, values: list[str], size: int) -> list[list[str]]:
        return [values[i : i + size] for i in range(0, len(values), size)]
