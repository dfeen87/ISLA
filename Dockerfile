FROM python:3.12-slim

# Install system dependencies for audio reading and compiling if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install standard Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install production API dependencies (FastAPI, uvicorn, gRPC)
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn \
    python-multipart \
    grpcio \
    grpcio-tools \
    grpcio-health-checking \
    protobuf

# Copy the entire workspace
COPY . .

# Install ISLA (legacy phased-music-notes Python distribution retained for compatibility)
RUN pip install --no-cache-dir -e .

# Expose HTTP port (8080) and gRPC port (50051)
EXPOSE 8080 50051

# Default runner starting both services
CMD ["python", "drivers/run_services.py"]
