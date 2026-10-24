import phased_music_notes
import isla
from drivers.http_server import app


def test_package_version():
    assert phased_music_notes.__version__ == isla.__version__ == "3.1.1"


def test_http_server_version():
    assert app.version == "3.1.1"
