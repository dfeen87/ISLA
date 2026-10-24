from pathlib import Path

import phased_music_notes
import isla
from drivers.http_server import app


def test_package_version():
    assert phased_music_notes.__version__ == isla.__version__ == "4.0.0"


def test_http_server_version():
    assert app.version == "4.0.0"


def test_build_metadata_matches_public_version():
    root = Path(__file__).resolve().parents[1]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    cmake = (root / "CMakeLists.txt").read_text(encoding="utf-8")
    assert 'version = "4.0.0"' in pyproject
    assert "project(ISLA VERSION 4.0.0)" in cmake
