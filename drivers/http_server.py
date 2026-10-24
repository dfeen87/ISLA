"""
FastAPI HTTP server for ISLA.

Provides:
  - GET /health or /ping: Service discovery health endpoints.
  - POST /smooth: In-memory local audio file smoothing.
"""

import io
import logging
from fastapi import FastAPI, UploadFile, File, Query, HTTPException, status
from fastapi.responses import StreamingResponse, JSONResponse

from drivers.api import smooth

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(
    title="ISLA API",
    description="HTTP API for local in-memory audio smoothing with phase alignment.",
    version="3.2.0"
)


@app.get("/health", status_code=status.HTTP_200_OK)
@app.get("/ping", status_code=status.HTTP_200_OK)
def health_check():
    """Service discovery health probe endpoint."""
    return {"status": "SERVING", "service": "isla"}


@app.post("/smooth")
async def smooth_audio(
    file: UploadFile = File(...),
    mode: str = Query("velvet", description="Smoothing mode (e.g., velvet, legato, melt)")
):
    """
    Smooth an uploaded audio file entirely in-memory.

    Parameters:
    - file: UploadFile (WAV, FLAC, OGG, etc.)
    - mode: "velvet", "legato", or "melt"
    """
    logging.info(f"HTTP request received for /smooth. File: {file.filename}, Mode: {mode}")

    # Validate file format (optional extension checking)
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename missing")

    try:
        # Read uploaded bytes
        input_bytes = await file.read()
        input_buffer = io.BytesIO(input_bytes)
        output_buffer = io.BytesIO()

        # Run core DSP engine in-memory
        smooth(input_buffer, output_buffer, mode=mode)

        # Seek output buffer back to start
        output_buffer.seek(0)

        # Return the output buffer as streaming WAV response
        return StreamingResponse(
            output_buffer,
            media_type="audio/wav",
            headers={"Content-Disposition": f"attachment; filename=smooth_{file.filename}"}
        )

    except Exception as e:
        logging.error(f"Error processing audio in /smooth: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "DSP processing failed"}
        )
