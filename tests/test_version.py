import phased_music_notes
import isla
from drivers.http_server import app


def test_package_version():
    assert phased_music_notes.__version__ == isla.__version__ == "2.1.0"


def test_http_server_version():
    assert app.version == "2.1.0"
