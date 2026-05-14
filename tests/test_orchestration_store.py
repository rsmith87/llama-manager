from sqlalchemy import inspect, update

from llama_manager.core.persistence.models.orchestration import JobOrm
from llama_manager.core.orchestration.store_orm import OrchestrationStoreOrm
from tests.persistence_db_setup import prepare_controller_db


def test_orchestration_store_orm_sets_schema_version(tmp_path):
    prepare_controller_db(tmp_path / "controller_state.db")
    store = OrchestrationStoreOrm(tmp_path / "controller_state.db")
    assert inspect(store.engine).has_table("schema_meta")


from llama_manager.core.orchestration.repo import OrchestrationRepo
from llama_manager.core.orchestration.orchestrator import Orchestrator


def test_orchestrator_leader_lease_single_holder(tmp_path):
    prepare_controller_db(tmp_path / "controller_state.db")
    store = OrchestrationStoreOrm(tmp_path / "controller_state.db")
    repo = OrchestrationRepo(store)
    a = Orchestrator(repo, controller_instance_id="a", leader_lease_seconds=30)
    b = Orchestrator(repo, controller_instance_id="b", leader_lease_seconds=30)
    assert a.try_acquire_leader_lease() is True
    assert b.try_acquire_leader_lease() is False


def test_prune_history_scales_with_many_terminal_jobs(tmp_path):
    prepare_controller_db(tmp_path / "controller_state.db")
    store = OrchestrationStoreOrm(tmp_path / "controller_state.db")
    repo = OrchestrationRepo(store)

    total_jobs = 650
    for idx in range(total_jobs):
        job = repo.create_job(
            job_type="chat",
            payload={"prompt": f"p{idx}"},
            priority=idx % 3,
            target="auto",
            requested_by="test",
        )
        claim = repo.claim_jobs(node_name=f"node-{idx % 7}", max_jobs=1)
        attempt_id = claim[0]["attempt_id"]
        repo.attempt_progress(node_name=f"node-{idx % 7}", attempt_id=attempt_id, progress={"pct": 50})
        repo.complete_attempt(
            node_name=f"node-{idx % 7}",
            attempt_id=attempt_id,
            result={"ok": True, "job_id": job["id"]},
            artifacts=[{"kind": "log", "uri": f"s3://bucket/{job['id']}.log"}],
        )

    with store.tx() as session:
        session.execute(update(JobOrm).values(completed_at="1970-01-01T00:00:00+00:00"))

    outcome = repo.prune_history(retention_days=0)

    assert outcome["pruned_jobs"] == total_jobs
    assert outcome["pruned_attempts"] == total_jobs
    # minimum expected: one job_created + one job_assigned + one progress + one attempt_completed + one job_completed per job
    assert outcome["pruned_events"] >= (total_jobs * 5)
    assert repo.list_jobs(limit=5) == []
