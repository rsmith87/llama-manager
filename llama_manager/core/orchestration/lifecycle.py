from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from llama_manager.core.persistence.models.orchestration import JobAttemptOrm, JobOrm, NodeLeaseOrm


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OrchestrationLifecycle:
    def __init__(self, store, repo):
        self.store = store
        self.repo = repo

    def claim_jobs(self, node_name: str, max_jobs: int = 1, lease_seconds: int = 60, capacity: dict[str, Any] | None = None, labels: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        claimed = []
        now = now_iso()
        lease_exp = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat()
        with self.store.tx() as session:
            lease = session.get(NodeLeaseOrm, node_name)
            if lease is None:
                session.add(
                    NodeLeaseOrm(
                        node_name=node_name,
                        last_heartbeat_at=now,
                        capacity_json=json.dumps(capacity) if capacity else None,
                        labels_json=json.dumps(labels) if labels else None,
                        status="online",
                        updated_at=now,
                    )
                )
            else:
                lease.last_heartbeat_at = now
                lease.capacity_json = json.dumps(capacity) if capacity else None
                lease.labels_json = json.dumps(labels) if labels else None
                lease.status = "online"
                lease.updated_at = now
            rows = session.execute(
                select(JobOrm)
                .where(JobOrm.status == "queued")
                .order_by(JobOrm.priority.desc(), JobOrm.created_at.asc())
            ).scalars().all()
            for row in rows:
                if len(claimed) >= max_jobs:
                    break
                if not self.repo._job_matches_node(row, node_name, capacity, labels):
                    continue
                attempt_id = str(uuid.uuid4())
                attempt_number = int(
                    session.execute(
                        select(func.count())
                        .select_from(JobAttemptOrm)
                        .where(JobAttemptOrm.job_id == row.id)
                    ).scalar_one()
                ) + 1
                session.add(
                    JobAttemptOrm(
                        id=attempt_id,
                        job_id=row.id,
                        attempt_number=attempt_number,
                        node_name=node_name,
                        lease_expires_at=lease_exp,
                        started_at=now,
                        status="assigned",
                    )
                )
                session.flush()
                self.repo._set_job_status(session, row, "assigned", now)
                self.repo._insert_event(
                    session,
                    row.id,
                    attempt_id,
                    "job_assigned",
                    {"node": node_name, "labels": labels or {}, "capacity": capacity or {}},
                )
                job = self.repo._job_row_to_dict(row)
                job["status"] = "assigned"
                claimed.append({"job": job, "attempt_id": attempt_id, "lease_expires_at": lease_exp})
        return claimed

    def attempt_progress(self, node_name: str, attempt_id: str, progress: dict[str, Any], lease_seconds: int = 60) -> None:
        with self.store.tx() as session:
            row = self.repo._get_owned_attempt(session, attempt_id, node_name)
            current = session.get(JobOrm, row.job_id)
            if current is not None and current.status == "cancel_requested":
                raise ValueError("Job cancellation requested")
            lease_exp = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat()
            now = now_iso()
            self.repo._set_attempt_status(session, row, "running", lease_expires_at=lease_exp)
            self.repo._set_job_status(session, row.job_id, "running", now)
            self.repo._insert_event(session, row.job_id, attempt_id, "progress", progress)

    def complete_attempt(self, node_name: str, attempt_id: str, result: dict[str, Any], artifacts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        with self.store.tx() as session:
            row = self.repo._get_owned_attempt(session, attempt_id, node_name)
            current = session.get(JobOrm, row.job_id)
            if current is not None and current.status == "cancel_requested":
                now = now_iso()
                self.repo._set_attempt_status(session, row, "failed", ended_at=now, failure_reason="CANCELED")
                self.repo._set_job_status(session, row.job_id, "canceled", now, completed_at=now, error_code="CANCELED", error_detail="Job canceled")
                self.repo._insert_event(session, row.job_id, attempt_id, "job_canceled", {"node": node_name})
            else:
                now = now_iso()
                self.repo._set_attempt_status(session, row, "completed", ended_at=now)
                self.repo._set_job_status(session, row.job_id, "completed", now, completed_at=now, result_json=json.dumps(result))
                if artifacts:
                    for artifact in artifacts:
                        self.repo._insert_artifact(
                            session,
                            row.job_id,
                            attempt_id,
                            kind=str(artifact.get("kind", "unknown")),
                            uri=str(artifact.get("uri", "")),
                            meta=artifact.get("meta") if isinstance(artifact.get("meta"), dict) else None,
                        )
                self.repo._insert_event(session, row.job_id, attempt_id, "attempt_completed", result)
                self.repo._insert_event(session, row.job_id, attempt_id, "job_completed", {})
        return self.repo.get_job(row.job_id)

    def fail_attempt(self, node_name: str, attempt_id: str, error_code: str, error_detail: str | None, retryable: bool, max_attempts: int = 3) -> dict[str, Any]:
        with self.store.tx() as session:
            row = self.repo._get_owned_attempt(session, attempt_id, node_name)
            now = now_iso()
            self.repo._set_attempt_status(session, row, "failed", ended_at=now, failure_reason=error_detail or error_code)
            attempts = int(
                session.execute(
                    select(func.count())
                    .select_from(JobAttemptOrm)
                    .where(JobAttemptOrm.job_id == row.job_id)
                ).scalar_one()
            )
            self.repo._insert_event(session, row.job_id, attempt_id, "attempt_failed", {"error_code": error_code, "error_detail": error_detail})
            current = session.get(JobOrm, row.job_id)
            if current is not None and current.status == "cancel_requested":
                self.repo._set_job_status(session, row.job_id, "canceled", now, completed_at=now, error_code=error_code, error_detail=error_detail)
                self.repo._insert_event(session, row.job_id, attempt_id, "job_canceled", {"error_code": error_code})
            elif retryable and attempts < max_attempts:
                self.repo._set_job_status(session, row.job_id, "queued", now)
                self.repo._insert_event(session, row.job_id, attempt_id, "retry_scheduled", {"next_attempt": attempts + 1})
            else:
                self.repo._set_job_status(session, row.job_id, "failed", now, completed_at=now, error_code=error_code, error_detail=error_detail)
                self.repo._insert_event(session, row.job_id, attempt_id, "job_failed", {"error_code": error_code})
        return self.repo.get_job(row.job_id)

    def sweep_expired_attempts(self, max_attempts: int = 3) -> dict[str, int]:
        now = now_iso()
        expired = 0
        requeued = 0
        timed_out = 0
        with self.store.tx() as session:
            rows = session.execute(
                select(JobAttemptOrm)
                .where(JobAttemptOrm.status.in_(("assigned", "running")))
                .where(JobAttemptOrm.lease_expires_at < now)
            ).scalars().all()
            for attempt in rows:
                expired += 1
                self.repo._set_attempt_status(session, attempt, "expired", ended_at=now)
                self.repo._insert_event(session, attempt.job_id, attempt.id, "lease_expired", {"node": attempt.node_name})
                attempts = int(
                    session.execute(
                        select(func.count())
                        .select_from(JobAttemptOrm)
                        .where(JobAttemptOrm.job_id == attempt.job_id)
                    ).scalar_one()
                )
                if attempts < max_attempts:
                    self.repo._set_job_status(session, attempt.job_id, "queued", now, error_code=None, error_detail=None)
                    self.repo._insert_event(session, attempt.job_id, attempt.id, "retry_scheduled", {"reason": "lease_expired", "next_attempt": attempts + 1})
                    requeued += 1
                else:
                    self.repo._set_job_status(session, attempt.job_id, "timed_out", now, completed_at=now, error_code="LEASE_EXPIRED", error_detail="Lease expired and max attempts reached")
                    self.repo._insert_event(session, attempt.job_id, attempt.id, "job_failed", {"error_code": "LEASE_EXPIRED"})
                    timed_out += 1
        return {"expired": expired, "requeued": requeued, "timed_out": timed_out}
