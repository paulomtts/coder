# tests/test_config.py
from coder.config.loader import SessionConfig, load_config


def test_config_defaults():
    config = SessionConfig()
    assert config.history_limit == 50
    assert config.compaction_threshold == 0.8
    assert config.keep_recent_tokens == 20000


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "claude-sonnet-4-5")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    config = SessionConfig.from_env()
    assert config.model == "claude-sonnet-4-5"
    assert config.api_key == "test-key"


def test_load_config_from_yaml(tmp_path):
    config_file = tmp_path / ".coder" / "config.yaml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("history_limit: 100\ncompaction_threshold: 0.9\n")
    config = load_config(cwd=str(tmp_path))
    assert config.history_limit == 100
    assert config.compaction_threshold == 0.9


def test_load_config_no_file(tmp_path):
    config = load_config(cwd=str(tmp_path))
    assert config.history_limit == 50
