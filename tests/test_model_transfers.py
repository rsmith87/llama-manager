import asyncio
import hashlib
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from llama_manager.core.config.models import AppConfig, ModelConfig
from llama_manager.core.model_assets.library import GgufLibrary
from llama_manager.core.model_assets.transfers import TransferManager
from llama_manager.core.nodes.worker import AgentWorker
from llama_manager.main import create_app
from tests.helpers import authenticated_client
from tests.persistence_db_setup import prepare_all_persistence_dbs


def make_file(path: Path, content: bytes = b"data") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_manifest_for_directory_model_includes_selected_gguf_and_sidecars(tmp_path):
    root = tmp_path / "HFModels"
    gguf = make_file(root / "Qwen" / "qwen-Q4_K_M.gguf", b"gguf")
    make_file(root / "Qwen" / "tokenizer.json", b"tokenizer")
    make_file(root / "Qwen" / "qwen-Q8_0.gguf", b"other-quant")
    config = AppConfig(hf_models_dirs=[root])
    library = GgufLibrary(config)
    manager = TransferManager(config)

    manifest = manager.build_manifest(library.file_id(gguf))

    assert manifest["model_dir"] == "Qwen"
    assert [item["relative_path"] for item in manifest["files"]] == [
        "Qwen/qwen-Q4_K_M.gguf",
        "Qwen/tokenizer.json",
    ]


def test_manifest_for_root_level_gguf_includes_only_selected_file(tmp_path):
    root = tmp_path / "HFModels"
    gguf = make_file(root / "standalone.gguf", b"gguf")
    make_file(root / "notes.txt", b"do-not-copy")
    config = AppConfig(hf_models_dirs=[root])
    library = GgufLibrary(config)
    manager = TransferManager(config)

    manifest = manager.build_manifest(library.file_id(gguf))

    assert manifest["model_dir"] is None
    assert [item["relative_path"] for item in manifest["files"]] == ["standalone.gguf"]


def test_manifest_includes_configured_mmproj(tmp_path):
    root = tmp_path / "HFModels"
    gguf = make_file(root / "Vision" / "vision-Q4.gguf", b"gguf")
    mmproj = make_file(root / "Vision" / "mmproj.gguf", b"mmproj")
    config = AppConfig(
        hf_models_dirs=[root],
        models={"vision": ModelConfig(path=str(gguf), port=8081, mmproj=str(mmproj), vision=True)},
    )
    library = GgufLibrary(config)
    manager = TransferManager(config)

    manifest = manager.build_manifest(library.file_id(gguf))

    assert [item["relative_path"] for item in manifest["files"]] == [
        "Vision/mmproj.gguf",
        "Vision/vision-Q4.gguf",
    ]


def test_manifest_rejects_unknown_file_id(tmp_path):
    manager = TransferManager(AppConfig(hf_models_dirs=[tmp_path / "HFModels"]))

    with pytest.raises(KeyError, match="Unknown GGUF file id"):
        manager.build_manifest("missing")


def test_agent_transfer_manifest_endpoint_returns_manifest(tmp_path):
    root = tmp_path / "HFModels"
    gguf = make_file(root / "Qwen" / "qwen.gguf", b"gguf")
    config = AppConfig(mode="agent", hf_models_dirs=[root], agent_api_key="agent-key")
    client = TestClient(create_app(config))
    file_id = GgufLibrary(config).file_id(gguf)

    client.post(
        "/transfer-source/grants",
        headers={"X-Llama-Manager-Key": "agent-key"},
        json={"source_file_id": file_id, "transfer_token": "transfer-token", "destination_node": "dest"},
    )
    response = client.get(
        f"/transfer-source/ggufs/{file_id}/manifest",
        headers={"Authorization": "Bearer transfer-token"},
    )

    assert response.status_code == 200
    assert response.json()["files"][0]["relative_path"] == "Qwen/qwen.gguf"


def test_agent_transfer_content_endpoint_streams_file(tmp_path):
    root = tmp_path / "HFModels"
    gguf = make_file(root / "Qwen" / "qwen.gguf", b"gguf-content")
    config = AppConfig(mode="agent", hf_models_dirs=[root], agent_api_key="agent-key")
    manager = TransferManager(config)
    token = manager.file_token(gguf)
    client = TestClient(create_app(config))
    file_id = GgufLibrary(config).file_id(gguf)

    client.post(
        "/transfer-source/grants",
        headers={"X-Llama-Manager-Key": "agent-key"},
        json={"source_file_id": file_id, "transfer_token": "transfer-token", "destination_node": "dest"},
    )
    response = client.get(
        f"/transfer-source/files/{token}/content",
        headers={"Authorization": "Bearer transfer-token"},
    )

    assert response.status_code == 200
    assert response.content == b"gguf-content"


def test_agent_transfer_grant_allows_bearer_token_manifest_access(tmp_path):
    root = tmp_path / "HFModels"
    gguf = make_file(root / "Qwen" / "qwen.gguf", b"gguf")
    config = AppConfig(mode="agent", hf_models_dirs=[root], agent_api_key="agent-key")
    client = TestClient(create_app(config))
    file_id = GgufLibrary(config).file_id(gguf)

    grant = client.post(
        "/transfer-source/grants",
        headers={"X-Llama-Manager-Key": "agent-key"},
        json={"source_file_id": file_id, "transfer_token": "transfer-token", "destination_node": "dest"},
    )
    response = client.get(
        f"/transfer-source/ggufs/{file_id}/manifest",
        headers={"Authorization": "Bearer transfer-token"},
    )

    assert grant.status_code == 200
    assert response.status_code == 200


def test_destination_copy_writes_new_file_under_first_model_root(tmp_path):
    dest_root = tmp_path / "dest"
    source_file = make_file(tmp_path / "source.gguf", b"content")
    manager = TransferManager(AppConfig(hf_models_dirs=[dest_root]))
    manifest_file = {
        "relative_path": "Qwen/qwen.gguf",
        "size_bytes": len(b"content"),
        "sha256": TransferManager.sha256(source_file),
    }

    with source_file.open("rb") as stream:
        result = manager.write_manifest_file(manifest_file, stream)

    assert result["status"] == "copied"
    assert (dest_root / "Qwen" / "qwen.gguf").read_bytes() == b"content"


def test_destination_copy_skips_identical_existing_file(tmp_path):
    dest_root = tmp_path / "dest"
    existing = make_file(dest_root / "Qwen" / "qwen.gguf", b"content")
    source_file = make_file(tmp_path / "source.gguf", b"content")
    manager = TransferManager(AppConfig(hf_models_dirs=[dest_root]))
    manifest_file = {
        "relative_path": "Qwen/qwen.gguf",
        "size_bytes": len(b"content"),
        "sha256": TransferManager.sha256(source_file),
    }

    with source_file.open("rb") as stream:
        result = manager.write_manifest_file(manifest_file, stream)

    assert result["status"] == "skipped"
    assert result["path"] == str(existing)


def test_destination_copy_fails_on_different_existing_file(tmp_path):
    dest_root = tmp_path / "dest"
    make_file(dest_root / "Qwen" / "qwen.gguf", b"different")
    source_file = make_file(tmp_path / "source.gguf", b"content")
    manager = TransferManager(AppConfig(hf_models_dirs=[dest_root]))
    manifest_file = {
        "relative_path": "Qwen/qwen.gguf",
        "size_bytes": len(b"content"),
        "sha256": TransferManager.sha256(source_file),
    }

    with source_file.open("rb") as stream:
        with pytest.raises(FileExistsError, match="Destination conflict"):
            manager.write_manifest_file(manifest_file, stream)


def test_destination_copy_rejects_path_traversal(tmp_path):
    manager = TransferManager(AppConfig(hf_models_dirs=[tmp_path / "dest"]))
    source_file = make_file(tmp_path / "source.gguf", b"content")

    with source_file.open("rb") as stream:
        with pytest.raises(ValueError, match="Unsafe relative path"):
            manager.write_manifest_file(
                {"relative_path": "../outside.gguf", "size_bytes": 7, "sha256": TransferManager.sha256(source_file)},
                stream,
            )


def test_controller_create_transfer_creates_model_transfer_job(tmp_path):
    prepare_all_persistence_dbs(tmp_path)
    grant_calls = []

    async def controller_request(method, url, api_key, verify_tls, json_body=None):
        grant_calls.append((method, url, api_key, verify_tls, json_body))
        return {"ok": True}

    config = AppConfig(
        mode="controller",
        log_dir=tmp_path,
        nodes={
            "source": {"url": "http://source", "api_key": "source-key"},
            "dest": {"url": "http://dest", "api_key": "dest-key"},
        },
    )
    app = create_app(config, controller_request=controller_request)
    client = authenticated_client(app)

    response = client.post(
        "/nodes/source/transfers",
        json={"destination_node": "dest", "source_file_id": "abc123", "include": "selected_with_sidecars"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["type"] == "model.transfer"
    assert payload["target_selector"] == "node:dest"
    assert payload["payload"]["source_node"] == "source"
    assert payload["payload"]["source_url"] == "http://source"
    assert len(payload["payload"]["transfer_token"]) >= 32
    assert grant_calls[0][0] == "POST"
    assert grant_calls[0][1] == "http://source/transfer-source/grants"


def test_controller_create_transfer_rejects_unknown_destination(tmp_path):
    prepare_all_persistence_dbs(tmp_path)
    config = AppConfig(
        mode="controller",
        log_dir=tmp_path,
        nodes={"source": {"url": "http://source", "api_key": "source-key"}},
    )
    client = authenticated_client(create_app(config))

    response = client.post(
        "/nodes/source/transfers",
        json={"destination_node": "missing", "source_file_id": "abc123", "include": "selected_with_sidecars"},
    )

    assert response.status_code == 404


def test_agent_worker_executes_model_transfer(tmp_path):
    dest_root = tmp_path / "dest"
    source_bytes = b"gguf-content"
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    calls = []

    async def fake_request(method, url, payload=None, headers=None):
        calls.append((method, url, payload))
        if url.endswith("/work/claim"):
            return [
                {
                    "attempt_id": "attempt-1",
                    "job": {
                        "id": "job-1",
                        "type": "model.transfer",
                        "payload": {
                            "source_node": "source",
                            "destination_node": "dest",
                            "source_file_id": "file-1",
                            "include": "selected_with_sidecars",
                            "source_url": "http://source",
                            "transfer_token": "transfer-token",
                        },
                    },
                }
            ]
        if url.endswith("/jobs/job-1"):
            return {"id": "job-1", "cancellation_requested": False}
        if url.endswith("/progress") or url.endswith("/complete"):
            return {"ok": True}
        raise AssertionError(url)

    async def fake_stream(url, headers):
        assert headers == {"Authorization": "Bearer transfer-token"}
        if url.endswith("/manifest"):
            return {
                "files": [
                    {
                        "id": "manifest-file-1",
                        "relative_path": "Qwen/qwen.gguf",
                        "size_bytes": len(source_bytes),
                        "sha256": source_hash,
                    }
                ]
            }
        if url.endswith("/content"):
            return io.BytesIO(source_bytes)
        raise AssertionError(url)

    worker = AgentWorker(
        AppConfig(
            mode="agent",
            node_name="dest",
            controller_url="http://controller",
            controller_registration_key_outbound="controller-key",
            agent_worker_enabled=True,
            hf_models_dirs=[dest_root],
        ),
        request=fake_request,
        transfer_stream=fake_stream,
    )

    count = asyncio.run(worker.run_once())

    assert count == 1
    assert (dest_root / "Qwen" / "qwen.gguf").read_bytes() == source_bytes
    assert any(call[0] == "POST" and call[1].endswith("/complete") for call in calls)


def test_transfer_list_returns_model_transfer_jobs(tmp_path):
    prepare_all_persistence_dbs(tmp_path)
    config = AppConfig(mode="controller", log_dir=tmp_path)
    app = create_app(config)
    app.state.orchestrator.create_job(
        job_type="model.transfer",
        payload={
            "source_node": "source",
            "destination_node": "dest",
            "source_file_id": "abc123",
            "include": "selected_with_sidecars",
        },
        target="node:dest",
    )
    client = authenticated_client(app)

    response = client.get("/transfers")

    assert response.status_code == 200
    assert response.json()[0]["source_node"] == "source"
    assert response.json()[0]["destination_node"] == "dest"


def test_library_marks_recently_received_file(tmp_path):
    root = tmp_path / "HFModels"
    gguf = make_file(root / "Qwen" / "qwen.gguf", b"gguf")
    library = GgufLibrary(AppConfig(hf_models_dirs=[root]))
    received = [
        {
            "id": "transfer-1",
            "source_node": "source",
            "completed_at": "2026-05-18T12:00:00+00:00",
            "copied": [{"path": str(gguf)}],
        }
    ]

    files = library.list_files(recent_transfers=received)

    assert files[0]["recently_received"] is True
    assert files[0]["received_from_node"] == "source"
    assert files[0]["received_transfer_id"] == "transfer-1"


def test_model_status_includes_file_id_for_library_transfer(tmp_path):
    prepare_all_persistence_dbs(tmp_path)
    root = tmp_path / "HFModels"
    gguf = make_file(root / "Qwen" / "qwen.gguf", b"gguf")
    config = AppConfig(
        mode="agent",
        log_dir=tmp_path,
        hf_models_dirs=[root],
        models={"qwen": ModelConfig(path=str(gguf), port=8081)},
    )
    client = authenticated_client(create_app(config))

    response = client.get("/models")

    assert response.status_code == 200
    model = response.json()[0]
    assert model["name"] == "qwen"
    assert model["file_id"] == GgufLibrary(config).file_id(gguf)
