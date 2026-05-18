from __future__ import annotations

import os
import subprocess
from pathlib import Path
from stat import S_IXUSR


ROOT_DIR = Path(__file__).resolve().parents[1]


def read_script(name: str) -> str:
    return (ROOT_DIR / "scripts" / name).read_text(encoding="utf-8")


def test_start_agent_script_uses_agent_specific_runtime_defaults() -> None:
    script = ROOT_DIR / "scripts" / "start_agent.sh"

    assert script.exists()
    contents = script.read_text(encoding="utf-8")
    assert ".llama_manager_agent.pid" in contents
    assert "llama_manager_agent_uvicorn.log" in contents
    assert "LLAMA_MANAGER_MODE=agent" in contents
    assert "Expected agent config" in contents


def test_start_server_is_deprecated_agent_wrapper() -> None:
    contents = read_script("start_server.sh")

    assert "deprecated" in contents.lower()
    assert 'exec "$ROOT_DIR/scripts/start_agent.sh"' in contents


def test_stop_server_knows_agent_controller_and_legacy_targets() -> None:
    contents = read_script("stop_server.sh")

    assert ".llama_manager_agent.pid" in contents
    assert ".llama_manager_controller.pid" in contents
    assert ".llama_manager.pid" in contents
    assert '"agent")' in contents
    assert '"controller")' in contents
    assert '"server"|"legacy")' in contents


def test_start_controller_script_uses_controller_specific_runtime_defaults() -> None:
    contents = read_script("start_controller.sh")

    assert ".llama_manager_controller.pid" in contents
    assert "llama_manager_controller_uvicorn.log" in contents
    assert "LLAMA_MANAGER_MODE=controller" in contents
    assert "Expected controller config" in contents


def test_runtime_shell_scripts_parse_cleanly() -> None:
    for script in [
        "scripts/onboard_agent.sh",
        "scripts/onboard_controller.sh",
        "scripts/start_agent.sh",
        "scripts/start_controller.sh",
        "scripts/start_server.sh",
        "scripts/stop_server.sh",
    ]:
        subprocess.run(["bash", "-n", str(ROOT_DIR / script)], check=True)


def test_runtime_shell_scripts_are_executable() -> None:
    for script in [
        "scripts/onboard_agent.sh",
        "scripts/onboard_controller.sh",
        "scripts/start_agent.sh",
        "scripts/start_controller.sh",
        "scripts/start_server.sh",
        "scripts/stop_server.sh",
    ]:
        assert (ROOT_DIR / script).stat().st_mode & S_IXUSR


def test_onboard_agent_keeps_lan_urls_in_env_not_config(tmp_path: Path) -> None:
    config = tmp_path / "agent.config.yaml"
    env_file = tmp_path / ".llama-manager.env"
    controller_url = "http://192.168.1.104:9137"
    agent_url = "http://192.168.1.205:9137"
    env = {
        **os.environ,
        "LLAMA_MANAGER_CONTROLLER_REGISTRATION_KEY_OUTBOUND": "join-key",
        "LLAMA_MANAGER_AGENT_API_KEY": "agent-key",
    }

    result = subprocess.run(
        [
            "bash",
            str(ROOT_DIR / "scripts" / "onboard_agent.sh"),
            "--config",
            str(config),
            "--env-file",
            str(env_file),
            "--controller-url",
            controller_url,
            "--agent-url",
            agent_url,
            "--node",
            "linux-2080ti",
        ],
        cwd=ROOT_DIR,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    config_text = config.read_text(encoding="utf-8")
    assert "controller_url: ${LLAMA_MANAGER_CONTROLLER_URL}" in config_text
    assert "agent_url: ${LLAMA_MANAGER_AGENT_URL}" in config_text
    assert controller_url not in config_text
    assert agent_url not in config_text

    env_text = env_file.read_text(encoding="utf-8")
    assert f"export LLAMA_MANAGER_CONTROLLER_URL={controller_url}" in env_text
    assert f"export LLAMA_MANAGER_AGENT_URL={agent_url}" in env_text

    assert "url: ${LLAMA_MANAGER_LINUX_2080TI_AGENT_URL}" in result.stdout
