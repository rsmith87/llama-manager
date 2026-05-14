from llama_manager.auth import main
from llama_manager.core.config import load_config
from llama_manager.core.persistence.auth_store_orm import AuthStoreOrm
from llama_manager.core.persistence.db_infra import resolve_persistence_urls
from tests.persistence_db_setup import prepare_auth_db


def test_create_admin_cli_prints_one_time_key_and_stores_hash(tmp_path, capsys):
    prepare_auth_db(tmp_path / "logs" / "auth_store.db")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
mode: agent
log_dir: {tmp_path / "logs"}
""",
        encoding="utf-8",
    )

    result = main(["--config", str(config_path), "create-admin", "alice"])

    assert result == 0
    out = capsys.readouterr().out
    assert "Created admin key for alice" in out
    key_line = next(line for line in out.splitlines() if line.startswith("API key: "))
    raw_key = key_line.removeprefix("API key: ")
    config = load_config(config_path)
    resolved = AuthStoreOrm(db_url=resolve_persistence_urls(config).auth).resolve_key(raw_key)
    assert resolved is not None
    assert resolved["username"] == "alice"
    assert resolved["role"] == "admin"
