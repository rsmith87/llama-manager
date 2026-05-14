from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from llama_manager.core.orchestration.lifecycle import OrchestrationLifecycle
from llama_manager.core.orchestration.retention import OrchestrationRetentionQueries
from llama_manager.core.orchestration.store_orm import OrchestrationStoreOrm
from llama_manager.core.persistence.models.orchestration import ArtifactOrm, JobAttemptOrm, JobEventOrm, JobOrm


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OrchestrationRepo:
    def __init__(self, store: OrchestrationStoreOrm):
        self.store = store
        self._lifecycle = OrchestrationLifecycle(store, self)
        self._retention = OrchestrationRetentionQueries(store, self._job_row_to_dict)

    def create_job(self, job_type: str, payload: dict[str, Any], priority: int, target: str, requested_by: str | None) -> dict[str, Any]:
        job_id = str(uuid.uuid4())
        now = _now()
        with self.store.tx() as session:
            session.add(
                JobOrm(
                    id=job_id,
                    type=job_type,
                    payload_json=json.dumps(payload),
                    requested_by=requested_by,
                    priority=priority,
                    status="queued",
                    target_selector=target,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.flush()
            self._insert_event(session, job_id, None, "job_created", {"type": job_type})
        return self.get_job(job_id)

    def list_jobs(self, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        stmt = select(JobOrm)
        if status:
            stmt = stmt.where(JobOrm.status == status)
        stmt = stmt.order_by(JobOrm.created_at.desc()).limit(limit)
        with self.store.tx() as session:
            rows = session.execute(stmt).scalars().all()
        return [self._job_row_to_dict(row) for row in rows]

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self.store.tx() as session:
            row = session.get(JobOrm, job_id)
            if row is None:
                raise KeyError(f"Unknown job: {job_id}")
        job = self._job_row_to_dict(row)
        job["artifacts"] = self.list_artifacts(job_id)
        return job

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        with self.store.tx() as session:
            row = session.get(JobOrm, job_id)
            if row is None:
                raise KeyError(f"Unknown job: {job_id}")
            if row.status not in {"queued", "assigned", "running", "cancel_requested"}:
                return self.get_job(job_id)
            now = _now()
            if row.status == "queued":
                row.status = "canceled"
                row.updated_at = now
                row.completed_at = now
                self._insert_event(session, job_id, None, "job_canceled", {})
            else:
                row.status = "cancel_requested"
                row.updated_at = now
                self._insert_event(session, job_id, None, "cancel_requested", {})
        return self.get_job(job_id)

    def claim_jobs(self, node_name: str, max_jobs: int = 1, lease_seconds: int = 60, capacity: dict[str, Any] | None = None, labels: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self._lifecycle.claim_jobs(node_name=node_name, max_jobs=max_jobs, lease_seconds=lease_seconds, capacity=capacity, labels=labels)

    def attempt_progress(self, node_name: str, attempt_id: str, progress: dict[str, Any], lease_seconds: int = 60) -> None:
        self._lifecycle.attempt_progress(node_name=node_name, attempt_id=attempt_id, progress=progress, lease_seconds=lease_seconds)

    def complete_attempt(self, node_name: str, attempt_id: str, result: dict[str, Any], artifacts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return self._lifecycle.complete_attempt(node_name=node_name, attempt_id=attempt_id, result=result, artifacts=artifacts)

    def fail_attempt(self, node_name: str, attempt_id: str, error_code: str, error_detail: str | None, retryable: bool, max_attempts: int = 3) -> dict[str, Any]:
        return self._lifecycle.fail_attempt(node_name=node_name, attempt_id=attempt_id, error_code=error_code, error_detail=error_detail, retryable=retryable, max_attempts=max_attempts)

    def list_job_events(self, job_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with self.store.tx() as session:
            rows = session.execute(
                select(JobEventOrm)
                .where(JobEventOrm.job_id == job_id)
                .order_by(JobEventOrm.created_at.asc())
                .limit(limit)
            ).scalars().all()
        return [
            {
                "id": row.id,
                "job_id": row.job_id,
                "attempt_id": row.attempt_id,
                "event_type": row.event_type,
                "event_json": json.loads(row.event_json),
                "created_at": row.created_at,
            }
            for row in rows
        ]

    def sweep_expired_attempts(self, max_attempts: int = 3) -> dict[str, int]:
        return self._lifecycle.sweep_expired_attempts(max_attempts=max_attempts)

    def prune_history(self, retention_days: int = 30) -> dict[str, int]:
        return self._retention.prune_history(retention_days=retention_days)

    def list_terminal_jobs_before(self, cutoff_iso: str, limit: int = 1000) -> list[dict[str, Any]]:
        return self._retention.list_terminal_jobs_before(cutoff_iso=cutoff_iso, limit=limit)

    def list_artifacts(self, job_id: str) -> list[dict[str, Any]]:
        return self._retention.list_artifacts(job_id=job_id)

    def job_counts_by_status(self) -> dict[str, int]:
        return self._retention.job_counts_by_status()

    def _insert_artifact(self, session: Session, job_id: str, attempt_id: str | None, kind: str, uri: str, meta: dict[str, Any] | None) -> None:
        session.add(
            ArtifactOrm(
                id=str(uuid.uuid4()),
                job_id=job_id,
                attempt_id=attempt_id,
                kind=kind,
                uri=uri,
                meta_json=json.dumps(meta) if meta else None,
                created_at=_now(),
            )
        )

    def _insert_event(self, session: Session, job_id: str, attempt_id: str | None, event_type: str, payload: dict[str, Any]) -> None:
        session.add(
            JobEventOrm(
                id=str(uuid.uuid4()),
                job_id=job_id,
                attempt_id=attempt_id,
                event_type=event_type,
                event_json=json.dumps(payload),
                created_at=_now(),
            )
        )

    def _job_row_to_dict(self, row: JobOrm) -> dict[str, Any]:
        return {
            "id": row.id,
            "type": row.type,
            "payload": json.loads(row.payload_json),
            "requested_by": row.requested_by,
            "priority": row.priority,
            "status": row.status,
            "target_selector": row.target_selector,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "completed_at": row.completed_at,
            "error_code": row.error_code,
            "error_detail": row.error_detail,
            "result": json.loads(row.result_json) if row.result_json else None,
            "cancellation_requested": row.status == "cancel_requested",
        }

    def _job_matches_node(self, row: JobOrm, node_name: str, capacity: dict[str, Any] | None, labels: dict[str, Any] | None) -> bool:
        target = str(row.target_selector or "auto")
        if target.startswith("node:"):
            target_node = target.split(":", 1)[1].strip()
            if target_node and target_node != node_name:
                return False
        payload = json.loads(row.payload_json)
        requirements = payload.get("requirements")
        if not isinstance(requirements, dict):
            return True
        required_labels = requirements.get("labels", {})
        if isinstance(required_labels, dict):
            node_labels = labels or {}
            for key, expected in required_labels.items():
                if node_labels.get(key) != expected:
                    return False
        required_capacity = requirements.get("capacity", {})
        if isinstance(required_capacity, dict):
            node_capacity = capacity or {}
            for key, min_value in required_capacity.items():
                node_value = node_capacity.get(key)
                if not isinstance(min_value, (int, float)):
                    if node_value != min_value:
                        return False
                    continue
                if not isinstance(node_value, (int, float)) or node_value < min_value:
                    return False
        return True

    def _get_owned_attempt(self, session: Session, attempt_id: str, node_name: str) -> JobAttemptOrm:
        row = session.get(JobAttemptOrm, attempt_id)
        if row is None:
            raise KeyError(f"Unknown attempt: {attempt_id}")
        if row.node_name != node_name:
            raise ValueError("Attempt owner mismatch")
        return row

    def _set_attempt_status(self, session: Session, attempt: JobAttemptOrm | str, status: str, *, lease_expires_at: str | None = None, ended_at: str | None = None, failure_reason: str | None = None) -> None:
        row = attempt if isinstance(attempt, JobAttemptOrm) else session.get(JobAttemptOrm, attempt)
        if row is None:
            raise KeyError(f"Unknown attempt: {attempt}")
        row.status = status
        if lease_expires_at is not None:
            row.lease_expires_at = lease_expires_at
        if ended_at is not None:
            row.ended_at = ended_at
        if failure_reason is not None:
            row.failure_reason = failure_reason

    def _set_job_status(self, session: Session, job: JobOrm | str, status: str, updated_at: str, *, completed_at: str | None = None, result_json: str | None = None, error_code: str | None = None, error_detail: str | None = None) -> None:
        row = job if isinstance(job, JobOrm) else session.get(JobOrm, job)
        if row is None:
            raise KeyError(f"Unknown job: {job}")
        row.status = status
        row.updated_at = updated_at
        if completed_at is not None:
            row.completed_at = completed_at
        if result_json is not None:
            row.result_json = result_json
        row.error_code = error_code
        row.error_detail = error_detail
