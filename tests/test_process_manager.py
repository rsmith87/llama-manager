from pathlib import Path

from llama_manager.core.config import load_config
from llama_manager.core.runtime.process_manager import ProcessManager


class FakeProcess:
    def __init__(self, pid=1234):
        self.pid = pid
        self._returncode = None
        self.terminated = False
        self.killed = False

    def poll(self):
        return self._returncode

    def terminate(self):
        self.terminated = True
        self._returncode = 0

    def wait(self, timeout=None):
        return self._returncode

    def kill(self):
        self.killed = True
        self._returncode = -9


def test_process_manager_start_stop_status_and_log_tail(tmp_path):
    spawned = []

    def fake_popen(command, stdout, stderr, cwd):
        spawned.append((command, stdout, stderr, cwd))
        return FakeProcess()

    config = load_config(
        {
            "mode": "agent",
            "llama_server_bin": "llama-server",
            "log_dir": str(tmp_path / "logs"),
            "models": {
                "qwen": {
                    "path": "/models/qwen.gguf",
                    "port": 8081,
                    "ctx": 4096,
                    "gpu_layers": 99,
                }
            },
        }
    )
    manager = ProcessManager(config, popen=fake_popen)

    started = manager.start("qwen")

    assert started.running is True
    assert started.pid == 1234
    assert started.port == 8081
    assert spawned[0][0][:3] == ["llama-server", "--model", "/models/qwen.gguf"]

    log_path = Path(started.log_path)
    log_path.write_text("one\ntwo\nthree\n", encoding="utf-8")
    assert manager.tail_logs("qwen", lines=2) == "two\nthree\n"

    stopped = manager.stop("qwen")
    assert stopped.running is False
    assert stopped.pid is None


def test_process_manager_rejects_unknown_model(tmp_path):
    manager = ProcessManager(load_config({"mode": "agent", "log_dir": str(tmp_path)}))

    try:
        manager.start("missing")
    except KeyError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("expected KeyError")

