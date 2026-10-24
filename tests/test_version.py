from pathlib import Path
from importlib.metadata import PackageNotFoundError, version as package_version

import pytest
import phased_music_notes
import isla
from drivers.http_server import app
from drivers.cli import main as cli_main


def test_package_version():
    assert phased_music_notes.__version__ == isla.__version__ == "4.0.0"


def test_http_server_version():
    assert app.version == isla.__version__ == "4.0.0"


def test_build_metadata_matches_public_version():
    root = Path(__file__).resolve().parents[1]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    cmake = (root / "CMakeLists.txt").read_text(encoding="utf-8")
    assert 'version = "4.0.0"' in pyproject
    assert "project(ISLA VERSION 4.0.0)" in cmake


def test_installed_distribution_matches_public_api():
    """When installed, the packaged release metadata must match source identity."""
    try:
        installed = package_version("isla-audio")
    except PackageNotFoundError:
        pytest.skip("Source checkout without an installed isla-audio distribution")
    assert installed == isla.__version__


def test_cli_version_reports_v4_without_opening_audio(capsys):
    with pytest.raises(SystemExit) as result:
        cli_main(["--version"])
    assert result.value.code == 0
    assert capsys.readouterr().out.strip() == f"isla {isla.__version__}"
