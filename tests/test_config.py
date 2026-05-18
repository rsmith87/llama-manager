from pathlib import Path

from llama_manager.core.config import load_config
from llama_manager.providers.llama_cpp import build_llama_server_command


def test_load_config_reads_models_nodes_and_env_override(tmp_path, monkeypatch):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
mode: agent
llama_server_bin: /opt/llama.cpp/llama-server
log_dir: ./agent-logs
models:
  qwen-coder:
    path: /models/qwen.gguf
    port: 8081
    ctx: 16384
    gpu_layers: 999
    host: 0.0.0.0
nodes:
  mac-mini:
    url: http://127.0.0.1:9000
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("LLAMA_MANAGER_MODE", "controller")

    config = load_config(config_file)

    assert config.mode == "controller"
    assert config.llama_server_bin == "/opt/llama.cpp/llama-server"
    assert config.log_dir == Path("./agent-logs")
    assert config.models["qwen-coder"].port == 8081
    assert config.nodes["mac-mini"].url == "http://127.0.0.1:9000"
    assert config.node_heartbeat_timeout_seconds == 90


def test_example_network_configs_use_env_placeholders_for_lan_urls():
    root = Path(__file__).resolve().parents[1]
    config_files = [
        root / "config.example.yaml",
        root / "linux-agent.config.example.yaml",
        root / "raspberry-pi-controller.config.example.yaml",
    ]

    for config_file in config_files:
        text = config_file.read_text(encoding="utf-8")
        assert "192.168." not in text, config_file.name
        assert "MAC_MINI_IP" not in text, config_file.name
        assert "LINUX_2080TI_IP" not in text, config_file.name


def test_load_config_expands_env_var_placeholders_in_nested_values(tmp_path, monkeypatch):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
mode: controller
agent_api_key: ${AGENT_API_KEY}
controller_registration_key: prefix-${JOIN_KEY}
hf_models_dirs:
  - ${MODEL_ROOT}
nodes:
  linux:
    url: ${LINUX_AGENT_URL}
    api_key: ${LINUX_AGENT_KEY}
models:
  gemma:
    path: ${MODEL_ROOT}/gemma.gguf
    port: 8080
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGENT_API_KEY", "agent-secret")
    monkeypatch.setenv("JOIN_KEY", "join-secret")
    monkeypatch.setenv("MODEL_ROOT", "/models")
    monkeypatch.setenv("LINUX_AGENT_URL", "http://linux:9137")
    monkeypatch.setenv("LINUX_AGENT_KEY", "node-secret")

    config = load_config(config_file)

    assert config.agent_api_key == "agent-secret"
    assert config.controller_registration_key == "prefix-join-secret"
    assert config.hf_models_dirs == [Path("/models")]
    assert config.nodes["linux"].url == "http://linux:9137"
    assert config.nodes["linux"].api_key == "node-secret"
    assert config.models["gemma"].path == "/models/gemma.gguf"


def test_build_llama_server_command_uses_configured_model_options():
    config = load_config(
        {
            "mode": "agent",
            "llama_server_bin": "llama-server",
            "models": {
                "gemma": {
                    "path": r"C:\models\gemma.gguf",
                    "port": 8080,
                    "ctx": 8192,
                    "gpu_layers": 999,
                    "host": "0.0.0.0",
                }
            },
        }
    )

    command = build_llama_server_command(config.llama_server_bin, config.models["gemma"])

    assert command == [
        "llama-server",
        "--model",
        r"C:\models\gemma.gguf",
        "--host",
        "0.0.0.0",
        "--port",
        "8080",
        "--ctx-size",
        "8192",
        "--n-gpu-layers",
        "999",
    ]


def test_default_config_does_not_embed_machine_specific_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LLAMA_MANAGER_CONFIG", raising=False)
    config = load_config()

    assert config.llama_cpp_dir == Path("./llama.cpp")
    assert not str(config.llama_cpp_dir).startswith("/Users/")


def test_load_config_prefers_local_config_yaml_when_env_unset(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LLAMA_MANAGER_CONFIG", raising=False)
    (tmp_path / "config.yaml").write_text(
        """
mode: agent
llama_server_bin: C:/local/llama-server.exe
""",
        encoding="utf-8",
    )
    (tmp_path / "config.example.yaml").write_text(
        """
mode: agent
llama_server_bin: /Users/stale/llama-server
""",
        encoding="utf-8",
    )

    config = load_config()

    assert config.llama_server_bin == "C:/local/llama-server.exe"
    assert config.config_source == str((tmp_path / "config.yaml").resolve())


def test_load_config_falls_back_to_local_example_when_config_yaml_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LLAMA_MANAGER_CONFIG", raising=False)
    (tmp_path / "config.example.yaml").write_text(
        """
mode: agent
llama_server_bin: C:/fallback/llama-server.exe
""",
        encoding="utf-8",
    )

    config = load_config()

    assert config.llama_server_bin == "C:/fallback/llama-server.exe"
    assert config.config_source == str((tmp_path / "config.example.yaml").resolve())


def test_build_llama_server_command_uses_reasoning_options():
    config = load_config(
        {
            "mode": "agent",
            "llama_server_bin": "llama-server",
            "models": {
                "gemma": {
                    "path": "/models/gemma.gguf",
                    "port": 8080,
                    "reasoning": "auto",
                    "reasoning_budget": 2048,
                }
            },
        }
    )

    command = build_llama_server_command(config.llama_server_bin, config.models["gemma"])

    assert "--reasoning" in command
    assert command[command.index("--reasoning") + 1] == "auto"
    assert "--reasoning-budget" in command
    assert command[command.index("--reasoning-budget") + 1] == "2048"


def test_build_llama_server_command_includes_mmproj_sidecar_when_configured():
    config = load_config(
        {
            "mode": "agent",
            "llama_server_bin": "llama-server",
            "models": {
                "gemma-vision": {
                    "path": "/models/gemma.gguf",
                    "port": 8080,
                    "vision": True,
                    "mmproj": "/models/mmproj-gemma.gguf",
                }
            },
        }
    )

    command = build_llama_server_command(config.llama_server_bin, config.models["gemma-vision"])
    assert "--mmproj" in command
    assert command[command.index("--mmproj") + 1] == "/models/mmproj-gemma.gguf"


def test_load_config_accepts_legacy_hf_models_dir_list():
    config = load_config(
        {
            "hf_models_dir": [
                "/Volumes/4TB/HFModels",
                "/Users/robertsmith/.cache/huggingface/hub",
            ]
        }
    )

    assert [str(path) for path in config.model_roots] == [
        "/Volumes/4TB/HFModels",
        "/Users/robertsmith/.cache/huggingface/hub",
    ]


def test_load_config_controller_retention_days_default():
    config = load_config({"mode": "controller"})
    assert config.controller_retention_days == 30


def test_load_config_controller_phase3_defaults():
    config = load_config({"mode": "controller"})
    assert config.controller_db_url is None
    assert config.controller_instance_id == "controller-default"
    assert config.controller_leader_lease_seconds == 30
