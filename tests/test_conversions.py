from pathlib import Path

from llama_manager.core.config import load_config
from llama_manager.core.model_assets.conversions import ConversionManager


class FakeProcess:
    def __init__(self, pid=4321):
        self.pid = pid
        self._returncode = None

    def poll(self):
        return self._returncode


def make_hf_model(path: Path):
    path.mkdir()
    (path / "config.json").write_text("{}", encoding="utf-8")
    (path / "tokenizer.json").write_text("{}", encoding="utf-8")
    (path / "model.safetensors").write_text("", encoding="utf-8")


def test_conversion_manager_lists_hf_models_and_existing_gguf(tmp_path):
    hf_dir = tmp_path / "HFModels"
    model_dir = hf_dir / "qwen"
    hf_dir.mkdir()
    make_hf_model(model_dir)
    (model_dir / "qwen-Q4_K_M.gguf").write_text("", encoding="utf-8")
    (model_dir / "qwen-f16.gguf").write_text("", encoding="utf-8")
    (hf_dir / "notes").mkdir()

    manager = ConversionManager(
        load_config(
                {
                    "hf_models_dir": str(hf_dir),
                    "llama_cpp_dir": "/Users/robertsmith/Apps/llama.cpp",
                    "log_dir": str(tmp_path / "logs"),
                }
            )
        )

    models = manager.list_models()

    assert models == [
        {
            "name": "qwen",
            "path": str(model_dir),
            "convertible": True,
            "output_path": str(model_dir / "qwen.gguf"),
            "gguf_exists": True,
            "gguf_files": [
                str(model_dir / "qwen-f16.gguf"),
                str(model_dir / "qwen-Q4_K_M.gguf"),
            ],
            "converter_path": "/Users/robertsmith/Apps/llama.cpp/convert_hf_to_gguf.py",
            "python_bin": "python3",
            "running": False,
            "pid": None,
            "returncode": None,
            "log_path": str(tmp_path / "logs" / "conversions" / "qwen.log"),
        }
    ]


def test_conversion_manager_starts_conversion_inside_model_directory(tmp_path):
    spawned = []
    hf_dir = tmp_path / "HFModels"
    model_dir = hf_dir / "qwen"
    hf_dir.mkdir()
    make_hf_model(model_dir)
    llama_cpp_dir = tmp_path / "llama.cpp"
    llama_cpp_dir.mkdir()
    (llama_cpp_dir / "convert_hf_to_gguf.py").write_text("", encoding="utf-8")

    def fake_popen(command, stdout, stderr, cwd):
        spawned.append((command, stdout, stderr, cwd))
        return FakeProcess()

    manager = ConversionManager(
        load_config(
            {
                "hf_models_dir": str(hf_dir),
                "llama_cpp_dir": str(llama_cpp_dir),
                "python_bin": "python3",
                "log_dir": str(tmp_path / "logs"),
            }
        ),
        popen=fake_popen,
    )

    status = manager.start("qwen")

    assert status["running"] is True
    assert status["pid"] == 4321
    assert spawned[0][0] == [
        "python3",
        str(llama_cpp_dir / "convert_hf_to_gguf.py"),
        str(model_dir),
        "--outfile",
        str(model_dir / "qwen.gguf"),
    ]


def test_conversion_manager_lists_models_from_multiple_roots(tmp_path):
    first_root = tmp_path / "HFModelsA"
    second_root = tmp_path / "HFModelsB"
    first_root.mkdir()
    second_root.mkdir()
    make_hf_model(first_root / "gemma")
    make_hf_model(second_root / "qwen")

    manager = ConversionManager(
        load_config(
            {
                "hf_models_dirs": [str(first_root), str(second_root)],
                "llama_cpp_dir": "/Users/robertsmith/Apps/llama.cpp",
                "log_dir": str(tmp_path / "logs"),
            }
        )
    )

    assert [model["name"] for model in manager.list_models()] == ["gemma", "qwen"]
