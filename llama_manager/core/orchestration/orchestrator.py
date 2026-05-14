from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from llama_manager.core.orchestration.repo import OrchestrationRepo
from llama_manager.core.persistence.models.orchestration import ControllerLeaseOrm


class Orchestrator:
    def __init__(self, repo: OrchestrationRepo, lease_timeout_seconds: int = 60, max_attempts: int = 3, retention_days: int = 30, archive_retention_days: int = 90, controller_instance_id: str = "controller-default", leader_lease_seconds: int = 30):
        self.repo = repo
        self.lease_timeout_seconds = lease_timeout_seconds
        self.max_attempts = max_attempts
        self.retention_days = retention_days
        self.last_sweep_stats: dict[str, int | str | bool] | None = None
        self.archive_retention_days = archive_retention_days
        self.controller_instance_id = controller_instance_id
        self.leader_lease_seconds = leader_lease_seconds

    def create_job(self, job_type: str, payload: dict, priority: int = 0, target: str = "auto", requested_by: str | None = None):
        return self.repo.create_job(job_type, payload, priority, target, requested_by)

    def list_jobs(self, status: str | None = None, limit: int = 50):
        return self.repo.list_jobs(status=status, limit=limit)

    def get_job(self, job_id: str):
        return self.repo.get_job(job_id)

    def cancel_job(self, job_id: str):
        return self.repo.cancel_job(job_id)

    def list_events(self, job_id: str, limit: int = 200):
        return self.repo.list_job_events(job_id, limit=limit)

    def claim_jobs(
        self,
        node_name: str,
        max_jobs: int = 1,
        capacity: dict | None = None,
        labels: dict | None = None,
    ):
        return self.repo.claim_jobs(
            node_name,
            max_jobs=max_jobs,
            lease_seconds=self.lease_timeout_seconds,
            capacity=capacity,
            labels=labels,
        )

    def progress(self, node_name: str, attempt_id: str, progress: dict):
        self.repo.attempt_progress(node_name, attempt_id, progress, lease_seconds=self.lease_timeout_seconds)

    def complete(self, node_name: str, attempt_id: str, result: dict, artifacts: list[dict] | None = None):
        return self.repo.complete_attempt(node_name, attempt_id, result, artifacts=artifacts)

    def fail(self, node_name: str, attempt_id: str, error_code: str, error_detail: str | None, retryable: bool):
        return self.repo.fail_attempt(node_name, attempt_id, error_code, error_detail, retryable, max_attempts=self.max_attempts)

    def sweep_expired_leases(self):
        stats = self.repo.sweep_expired_attempts(max_attempts=self.max_attempts)
        retention = self.repo.prune_history(retention_days=self.retention_days)
        self.last_sweep_stats = {
            "ok": True,
            "swept_at": datetime.now(timezone.utc).isoformat(),
            **stats,
            **retention,
        }
        return self.last_sweep_stats

    def controller_stats(self) -> dict:
        return {
            "last_sweep": self.last_sweep_stats,
            "job_counts": self.repo.job_counts_by_status(),
            "retention_days": self.retention_days,
            "lease_timeout_seconds": self.lease_timeout_seconds,
            "max_attempts": self.max_attempts,
        }


    def archive_snapshot(self, archive_path: str, retention_days: int | None = None, limit: int = 1000) -> dict:
        days = retention_days if retention_days is not None else self.archive_retention_days
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        jobs = self.repo.list_terminal_jobs_before(cutoff, limit=limit)
        lines = []
        for job in jobs:
            events = self.repo.list_job_events(job["id"], limit=5000)
            record = {"job": job, "events": events}
            lines.append(json.dumps(record))
        Path = __import__('pathlib').Path
        path = Path(archive_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return {"archive_path": str(path), "jobs_exported": len(jobs), "cutoff": cutoff}


    def try_acquire_leader_lease(self, lease_name: str = "controller_sweeper") -> bool:
        now = datetime.now(timezone.utc)
        exp = (now + timedelta(seconds=self.leader_lease_seconds)).isoformat()
        now_iso = now.isoformat()
        with self.repo.store.tx() as session:
            row = session.get(ControllerLeaseOrm, lease_name)
            if row is None:
                session.add(
                    ControllerLeaseOrm(
                        lease_name=lease_name,
                        holder_id=self.controller_instance_id,
                        expires_at=exp,
                        updated_at=now_iso,
                    )
                )
                return True
            holder = row.holder_id
            expires_at = row.expires_at
            if holder == self.controller_instance_id or expires_at < now_iso:
                row.holder_id = self.controller_instance_id
                row.expires_at = exp
                row.updated_at = now_iso
                return True
            return False
