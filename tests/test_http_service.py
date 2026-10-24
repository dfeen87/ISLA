import io
import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from drivers.http_server import app


def test_health_and_ping():
    client = TestClient(app)

    # Test GET /health
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "SERVING", "service": "isla"}

    # Test GET /ping
    response = client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"status": "SERVING", "service": "isla"}


def test_smooth_endpoint():
    client = TestClient(app)

    # Create dummy in-memory WAV file
    sr = 44100
    audio = np.sin(2 * np.pi * 440 * np.linspace(0, 0.2, int(sr * 0.2))).astype(np.float32)
    stereo = np.column_stack((audio, audio))

    input_buf = io.BytesIO()
    sf.write(input_buf, stereo, sr, format="WAV")
    input_buf.seek(0)

    # Post to FastAPI /smooth endpoint
    response = client.post(
        "/smooth?mode=velvet",
        files={"file": ("piano_test.wav", input_buf, "audio/wav")}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert "smooth_piano_test.wav" in response.headers["content-disposition"]

    # Verify returned WAV content
    out_buf = io.BytesIO(response.content)
    out_audio, out_sr = sf.read(out_buf)

    assert out_sr == sr
    assert out_audio.shape[1] == 2
    assert len(out_audio) == len(stereo)
