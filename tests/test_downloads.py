from pathlib import Path

from llama_manager.core.config import load_config
from llama_manager.core.model_assets.downloads import DownloadManager


class FakeStore:
    def __init__(self):
        self.created = []
        self.updated = {}

    def list_downloads(self, *, status=None, limit=100):
        return []

    def create_download(self, **kwargs):
        record = {
            "id": "download-1",
            "status": "queued",
            "pid": None,
            "returncode": None,
            "error_detail": None,
            **kwargs,
        }
        self.created.append(record)
        return record

    def get_download(self, download_id):
        return {**self.created[-1], **self.updated.get(download_id, {})}

    def update_status(self, download_id, **kwargs):
        self.updated[download_id] = {**self.updated.get(download_id, {}), **kwargs}
        return self.get_download(download_id)

    def delete_download(self, download_id):
        return None


class FakeProcess:
    pid = 1234

    def poll(self):
        return None


class FakeHfApi:
    def __init__(self, files):
        self.files = files
        self.calls = []

    def list_repo_tree(self, repo_id, path_in_repo=None, *, recursive=False, expand=False, revision=None, repo_type=None, token=None):
        self.calls.append(
            {
                "repo_id": repo_id,
                "path_in_repo": path_in_repo,
                "recursive": recursive,
                "expand": expand,
                "revision": revision,
                "repo_type": repo_type,
            }
        )
        return self.files


class FakeRepoFile:
    def __init__(self, path, size):
        self.path = path
        self.size = size


def make_manager(tmp_path, *, files=None, popen=None):
    config = load_config(
        {
            "mode": "agent",
            "hf_models_dirs": [str(tmp_path / "models")],
            "log_dir": str(tmp_path / "logs"),
            "python_bin": "python-test",
        }
    )
    store = FakeStore()
    api = FakeHfApi(files or [])
    manager = DownloadManager(config, store, popen=popen or (lambda *args, **kwargs: FakeProcess()), hf_api=api)
    return manager, store, api


def test_download_manager_lists_remote_gguf_quants(tmp_path):
    manager, _store, api = make_manager(
        tmp_path,
        files=[
            FakeRepoFile("README.md", 42),
            FakeRepoFile("model-Q4_K_M.gguf", 1024),
            FakeRepoFile("nested/model-Q5_K_M.gguf", 2048),
            FakeRepoFile("mmproj-F16.gguf", 128),
            FakeRepoFile("model.safetensors", 4096),
        ],
    )

    quants = manager.list_remote_quants("owner/model", revision="main")

    assert quants == [
        {
            "filename": "model-Q4_K_M.gguf",
            "path": "model-Q4_K_M.gguf",
            "size_bytes": 1024,
            "quant": "Q4_K_M",
            "mmproj": {"filename": "mmproj-F16.gguf", "path": "mmproj-F16.gguf", "size_bytes": 128, "quant": "F16"},
        },
        {
            "filename": "model-Q5_K_M.gguf",
            "path": "nested/model-Q5_K_M.gguf",
            "size_bytes": 2048,
            "quant": "Q5_K_M",
            "mmproj": {"filename": "mmproj-F16.gguf", "path": "mmproj-F16.gguf", "size_bytes": 128, "quant": "F16"},
        },
    ]
    assert api.calls == [
        {
            "repo_id": "owner/model",
            "path_in_repo": None,
            "recursive": True,
            "expand": True,
            "revision": "main",
            "repo_type": "model",
        }
    ]


def test_download_manager_prefers_quant_directory_over_model_name(tmp_path):
    manager, _store, _api = make_manager(
        tmp_path,
        files=[
            FakeRepoFile("BF16/Qwen3.6-35B-A3B-BF16-00001-of-00002.gguf", 1024),
            FakeRepoFile("Q4_K_M/Qwen3.6-35B-A3B-Q4_K_M.gguf", 2048),
            FakeRepoFile("Qwen3.6-35B-A3B-MXFP4_MOE.gguf", 4096),
            FakeRepoFile("Qwen3.6-35B-A3B-Q8_0.gguf", 8192),
            FakeRepoFile("Qwen3.6-35B-A3B-UD-IQ1_M.gguf", 16384),
        ],
    )

    quants = manager.list_remote_quants("owner/model")

    quant_by_path = {item["path"]: item["quant"] for item in quants}
    assert quant_by_path == {
        "BF16/Qwen3.6-35B-A3B-BF16-00001-of-00002.gguf": "BF16",
        "Q4_K_M/Qwen3.6-35B-A3B-Q4_K_M.gguf": "Q4_K_M",
        "Qwen3.6-35B-A3B-MXFP4_MOE.gguf": "MXFP4_MOE",
        "Qwen3.6-35B-A3B-Q8_0.gguf": "Q8_0",
        "Qwen3.6-35B-A3B-UD-IQ1_M.gguf": "IQ1_M",
    }


def test_download_manager_links_mmproj_files_to_matching_quants(tmp_path):
    manager, _store, _api = make_manager(
        tmp_path,
        files=[
            FakeRepoFile("BF16/Qwen3.6-35B-A3B-BF16-00001-of-00002.gguf", 1024),
            FakeRepoFile("F16/Qwen3.6-35B-A3B-F16.gguf", 2048),
            FakeRepoFile("mmproj-F16.gguf", 128),
        ],
    )

    quants = manager.list_remote_quants("owner/model")

    by_quant = {item["quant"]: item for item in quants}
    assert by_quant["BF16"]["mmproj"] == {
        "filename": "mmproj-F16.gguf",
        "path": "mmproj-F16.gguf",
        "size_bytes": 128,
        "quant": "F16",
    }
    assert by_quant["F16"]["mmproj"]["path"] == "mmproj-F16.gguf"
    assert "mmproj" not in [item["filename"] for item in quants]


def test_download_manager_starts_selected_remote_quant(tmp_path):
    captured = {}

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

    manager, store, _api = make_manager(tmp_path, popen=fake_popen)

    manager.start("owner/model", revision="main", include_file="nested/model-Q5_K_M.gguf", triggered_by="tester")

    assert captured["command"] == [
        "python-test",
        "-m",
        "huggingface_hub.cli.hf",
        "download",
        "owner/model",
        "--local-dir",
        str(tmp_path / "models" / "owner__model"),
        "--revision",
        "main",
        "--include",
        "nested/model-Q5_K_M.gguf",
    ]
    assert store.created[0]["command"].endswith("--include nested/model-Q5_K_M.gguf")
