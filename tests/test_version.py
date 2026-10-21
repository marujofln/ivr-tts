import tomllib

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_version_matches_pyproject():
    from ivr_tts import __version__

    with open(ROOT / "pyproject.toml", "rb") as f:
        assert __version__ == tomllib.load(f)["project"]["version"]
