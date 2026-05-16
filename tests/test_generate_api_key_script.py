import importlib.util
import re
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_api_key.py"


def load_key_module():
    spec = importlib.util.spec_from_file_location("generate_api_key", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_generate_api_key_uses_urlsafe_material_with_default_prefix():
    keygen = load_key_module()

    key = keygen.generate_api_key(token_bytes=32, prefix="llm")

    assert key.startswith("llm_")
    assert re.fullmatch(r"llm_[A-Za-z0-9_-]{43}", key)


def test_generate_api_key_can_emit_unprefixed_key():
    keygen = load_key_module()

    key = keygen.generate_api_key(token_bytes=16, prefix="")

    assert re.fullmatch(r"[A-Za-z0-9_-]{22}", key)


def test_main_prints_one_key_per_line(capsys):
    keygen = load_key_module()

    result = keygen.main(["--count", "2", "--bytes", "16", "--prefix", "test"])

    assert result == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    assert all(re.fullmatch(r"test_[A-Za-z0-9_-]{22}", line) for line in lines)
    assert lines[0] != lines[1]
