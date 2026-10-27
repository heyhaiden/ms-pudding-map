import os

import pytest

from scripts.poll import load_env, write_config


def test_load_env_keeps_existing_variables(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('MAPBOX_TOKEN=from-file\n# comment\n\nexport OTHER="x"\n')
    monkeypatch.setenv("MAPBOX_TOKEN", "from-env")
    monkeypatch.delenv("OTHER", raising=False)
    load_env(env)
    assert os.environ["MAPBOX_TOKEN"] == "from-env"
    assert os.environ["OTHER"] == "x"


def test_write_config_quotes_the_token(tmp_path):
    path = tmp_path / "config.js"
    write_config("pk.abc", path)
    assert path.read_text() == 'const MAPBOX_TOKEN = "pk.abc";\n'


def test_write_config_requires_a_token(tmp_path):
    with pytest.raises(SystemExit, match="MAPBOX_TOKEN"):
        write_config("  ", tmp_path / "config.js")
