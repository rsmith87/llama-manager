from pathlib import Path

from llama_manager.core.config import load_config
from llama_manager.core.model_assets.library import GgufLibrary


def test_gguf_library_lists_files_with_stable_ids(tmp_path):
    hf_dir = tmp_path / "HFModels"
    model_dir = hf_dir / "gemma"
    model_dir.mkdir(parents=True)
    gguf_path = model_dir / "model.gguf"
    gguf_path.write_bytes(b"x" * 1536)

    library = GgufLibrary(load_config({"hf_models_dir": str(hf_dir)}))

    files = library.list_files()

    assert files == [
        {
            "id": library.file_id(gguf_path),
            "name": "model",
            "filename": "model.gguf",
            "model_dir": "gemma",
            "path": str(gguf_path),
            "size_bytes": 1536,
            "size_gb": 0.0,
            "registered": False,
            "registered_as": None,
        }
    ]


def test_gguf_library_adds_file_as_runtime_model(tmp_path):
    hf_dir = tmp_path / "HFModels"
    model_dir = hf_dir / "gemma"
    model_dir.mkdir(parents=True)
    gguf_path = model_dir / "model.gguf"
    gguf_path.write_text("", encoding="utf-8")
    config = load_config({"hf_models_dir": str(hf_dir)})
    library = GgufLibrary(config)

    model = library.add_model(
        library.file_id(gguf_path),
        name="gemma-local",
        port=8088,
        ctx=8192,
        gpu_layers=999,
        host="0.0.0.0",
        reasoning="auto",
        reasoning_budget=2048,
        prompt_template="gemma",
        favorite=False,
    )

    assert model == {
        "name": "gemma-local",
        "path": str(gguf_path),
        "port": 8088,
        "ctx": 8192,
        "gpu_layers": 999,
        "host": "0.0.0.0",
        "reasoning": "auto",
        "reasoning_budget": 2048,
        "prompt_template": "gemma",
        "favorite": False
    }
    assert config.models["gemma-local"].path == str(gguf_path)
    assert config.models["gemma-local"].reasoning == "auto"
    assert config.models["gemma-local"].reasoning_budget == 2048
    assert config.models["gemma-local"].prompt_template == "gemma"


def test_gguf_library_lists_files_from_multiple_roots(tmp_path):
    first_root = tmp_path / "HFModelsA"
    second_root = tmp_path / "HFModelsB"
    first_model = first_root / "gemma"
    second_model = second_root / "qwen"
    first_model.mkdir(parents=True)
    second_model.mkdir(parents=True)
    first_path = first_model / "gemma.gguf"
    second_path = second_model / "qwen.gguf"
    first_path.write_text("", encoding="utf-8")
    second_path.write_text("", encoding="utf-8")

    library = GgufLibrary(
        load_config({"hf_models_dirs": [str(first_root), str(second_root)]})
    )

    assert [file["path"] for file in library.list_files()] == [
        str(first_path),
        str(second_path),
    ]


def test_gguf_library_add_model_persists_to_file_backed_config(tmp_path):
    hf_dir = tmp_path / "HFModels"
    model_dir = hf_dir / "gemma"
    model_dir.mkdir(parents=True)
    gguf_path = model_dir / "model.gguf"
    gguf_path.write_text("", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
hf_models_dir: {hf_dir}
models: {{}}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    config = load_config(config_path)
    library = GgufLibrary(config)

    library.add_model(
        library.file_id(gguf_path),
        name="gemma-local",
        port=8088,
        ctx=8192,
        gpu_layers=999,
        host="0.0.0.0",
        reasoning="auto",
        reasoning_budget=2048,
        prompt_template="llama3",
    )

    reloaded = load_config(config_path)
    assert "gemma-local" in reloaded.models
    assert reloaded.models["gemma-local"].path == str(gguf_path)
    assert reloaded.models["gemma-local"].reasoning == "auto"
    assert reloaded.models["gemma-local"].reasoning_budget == 2048
    assert reloaded.models["gemma-local"].prompt_template == "llama3"


def test_gguf_library_deletes_file_and_unregisters_model(tmp_path):
    hf_dir = tmp_path / "HFModels"
    model_dir = hf_dir / "gemma"
    model_dir.mkdir(parents=True)
    gguf_path = model_dir / "model.gguf"
    gguf_path.write_text("", encoding="utf-8")
    config = load_config(
        {
            "hf_models_dir": str(hf_dir),
            "models": {"gemma-local": {"path": str(gguf_path), "port": 8088}},
        }
    )
    library = GgufLibrary(config)

    deleted = library.delete_file(library.file_id(gguf_path))

    assert deleted == {
        "deleted": True,
        "id": library.file_id(gguf_path),
        "filename": "model.gguf",
        "path": str(gguf_path),
        "unregistered_models": ["gemma-local"],
    }
    assert not gguf_path.exists()
    assert "gemma-local" not in config.models
