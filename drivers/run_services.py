"""
Unified runner to start both HTTP and gRPC microservices simultaneously inside the Docker container.
"""

import multiprocessing
import logging
import sys

import uvicorn
from drivers import grpc_server

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def run_http():
    try:
        logging.info("Starting local HTTP server on port 8080...")
        uvicorn.run("drivers.http_server:app", host="0.0.0.0", port=8080, log_level="info")
    except Exception as e:
        logging.error(f"HTTP Server failed: {e}")
        sys.exit(1)


def run_grpc():
    try:
        logging.info("Starting high-performance gRPC server on port 50051...")
        server = grpc_server.serve(port=50051)
        server.wait_for_termination()
    except Exception as e:
        logging.error(f"gRPC Server failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Use spawn or fork depending on OS
    multiprocessing.set_start_method("spawn", force=True)

    p1 = multiprocessing.Process(target=run_http, name="HTTP-Server")
    p2 = multiprocessing.Process(target=run_grpc, name="gRPC-Server")

    p1.start()
    p2.start()

    logging.info("Both ISLA services started successfully.")

    try:
        while True:
            p1.join(timeout=0.5)
            p2.join(timeout=0.5)

            if not p1.is_alive() or not p2.is_alive():
                if p1.exitcode not in (None, 0):
                    logging.error(f"HTTP server exited with code {p1.exitcode}; stopping gRPC server.")
                if p2.exitcode not in (None, 0):
                    logging.error(f"gRPC server exited with code {p2.exitcode}; stopping HTTP server.")
                p1.terminate()
                p2.terminate()
                p1.join(timeout=5)
                p2.join(timeout=5)
                sys.exit(p1.exitcode or p2.exitcode or 1)
    except KeyboardInterrupt:
        logging.info("Terminating services...")
        p1.terminate()
        p2.terminate()
        p1.join()
        p2.join()
        logging.info("All services stopped.")
