from sqlalchemy import Index, UniqueConstraint

from llama_manager.core.persistence.models.orchestration import (
    ArtifactOrm,
    ControllerLeaseOrm,
    JobAttemptOrm,
    JobEventOrm,
    JobOrm,
    NodeLeaseOrm,
    SchemaMetaOrm,
)


def _col(table, name: str):
    return table.columns[name]


def test_job_orm_schema_parity():
    table = JobOrm.__table__
    assert table.name == "jobs"
    assert _col(table, "id").primary_key is True
    assert _col(table, "type").nullable is False
    assert _col(table, "payload_json").nullable is False
    assert _col(table, "requested_by").nullable is True
    assert _col(table, "priority").nullable is False
    assert _col(table, "status").nullable is False
    assert _col(table, "target_selector").nullable is False
    assert _col(table, "created_at").nullable is False
    assert _col(table, "updated_at").nullable is False
    assert _col(table, "completed_at").nullable is True
    assert _col(table, "result_json").nullable is True
    assert _col(table, "error_code").nullable is True
    assert _col(table, "error_detail").nullable is True

    index_names = {idx.name for idx in table.indexes if isinstance(idx, Index)}
    assert "idx_jobs_status_priority_created" in index_names


def test_job_attempt_orm_schema_parity():
    table = JobAttemptOrm.__table__
    assert table.name == "job_attempts"
    assert _col(table, "id").primary_key is True
    assert _col(table, "job_id").nullable is False
    assert _col(table, "attempt_number").nullable is False
    assert _col(table, "node_name").nullable is False
    assert _col(table, "lease_expires_at").nullable is False
    assert _col(table, "started_at").nullable is False
    assert _col(table, "ended_at").nullable is True
    assert _col(table, "status").nullable is False
    assert _col(table, "failure_reason").nullable is True

    foreign_target = list(_col(table, "job_id").foreign_keys)[0].target_fullname
    assert foreign_target == "jobs.id"

    unique_constraints = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    assert any({"job_id", "attempt_number"} == {col.name for col in c.columns} for c in unique_constraints)


def test_node_leases_orm_schema_parity():
    table = NodeLeaseOrm.__table__
    assert table.name == "node_leases"
    assert _col(table, "node_name").primary_key is True
    assert _col(table, "last_heartbeat_at").nullable is False
    assert _col(table, "capacity_json").nullable is True
    assert _col(table, "labels_json").nullable is True
    assert _col(table, "status").nullable is False
    assert _col(table, "updated_at").nullable is False


def test_job_events_orm_schema_parity():
    table = JobEventOrm.__table__
    assert table.name == "job_events"
    assert _col(table, "id").primary_key is True
    assert _col(table, "job_id").nullable is False
    assert _col(table, "attempt_id").nullable is True
    assert _col(table, "event_type").nullable is False
    assert _col(table, "event_json").nullable is False
    assert _col(table, "created_at").nullable is False

    job_fk = list(_col(table, "job_id").foreign_keys)[0].target_fullname
    attempt_fk = list(_col(table, "attempt_id").foreign_keys)[0].target_fullname
    assert job_fk == "jobs.id"
    assert attempt_fk == "job_attempts.id"

    index_names = {idx.name for idx in table.indexes if isinstance(idx, Index)}
    assert "idx_job_events_job_created" in index_names


def test_artifacts_orm_schema_parity():
    table = ArtifactOrm.__table__
    assert table.name == "artifacts"
    assert _col(table, "id").primary_key is True
    assert _col(table, "job_id").nullable is False
    assert _col(table, "attempt_id").nullable is True
    assert _col(table, "kind").nullable is False
    assert _col(table, "uri").nullable is False
    assert _col(table, "meta_json").nullable is True
    assert _col(table, "created_at").nullable is False

    job_fk = list(_col(table, "job_id").foreign_keys)[0].target_fullname
    attempt_fk = list(_col(table, "attempt_id").foreign_keys)[0].target_fullname
    assert job_fk == "jobs.id"
    assert attempt_fk == "job_attempts.id"

    index_names = {idx.name for idx in table.indexes if isinstance(idx, Index)}
    assert "idx_artifacts_job_created" in index_names


def test_schema_meta_orm_schema_parity():
    table = SchemaMetaOrm.__table__
    assert table.name == "schema_meta"
    assert _col(table, "key").primary_key is True
    assert _col(table, "value").nullable is False


def test_controller_leases_orm_schema_parity():
    table = ControllerLeaseOrm.__table__
    assert table.name == "controller_leases"
    assert _col(table, "lease_name").primary_key is True
    assert _col(table, "holder_id").nullable is False
    assert _col(table, "expires_at").nullable is False
    assert _col(table, "updated_at").nullable is False
