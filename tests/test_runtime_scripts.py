from __future__ import annotations

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
        "scripts/start_agent.sh",
        "scripts/start_controller.sh",
        "scripts/start_server.sh",
        "scripts/stop_server.sh",
    ]:
        subprocess.run(["bash", "-n", str(ROOT_DIR / script)], check=True)


def test_runtime_shell_scripts_are_executable() -> None:
    for script in [
        "scripts/start_agent.sh",
        "scripts/start_controller.sh",
        "scripts/start_server.sh",
        "scripts/stop_server.sh",
    ]:
        assert (ROOT_DIR / script).stat().st_mode & S_IXUSR
