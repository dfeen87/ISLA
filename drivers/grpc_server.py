"""
gRPC Server for ISLA.

Provides:
  - SmoothBlock: Processes a full audio block.
  - SmoothAudioStream: Bidirectional stream of real-time audio chunks (AI-DJ ready).
  - Health checking: Standard gRPC service discovery health check.
"""

import logging
import sys
from concurrent import futures
import grpc
from grpc_health.v1 import health
from grpc_health.v1 import health_pb2
from grpc_health.v1 import health_pb2_grpc
import numpy as np

# Import generated classes
from phased_music_notes.proto import audio_processor_pb2
from phased_music_notes.proto import audio_processor_pb2_grpc
from drivers.api import IslaBuffer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class AudioProcessorServicer(audio_processor_pb2_grpc.AudioProcessorServicer):
    """gRPC Service implementation of AudioProcessor."""

    def SmoothBlock(self, request, context):
        """Processes a single complete block of audio."""
        logging.info(f"Received SmoothBlock request. Mode: {request.mode}, SR: {request.sample_rate}, Channels: {request.channels}")
        try:
            # Parse raw float32 audio bytes
            raw_data = np.frombuffer(request.audio_data, dtype=np.float32)

            if request.channels == 1:
                # Mono input -> upmix to stereo (num_samples, 2)
                mono = raw_data
                stereo = np.column_stack((mono, mono))
            elif request.channels == 2:
                if raw_data.size % 2 != 0:
                    context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                    context.set_details("Stereo audio_data must contain an even number of float32 samples")
                    return audio_processor_pb2.SmoothBlockResponse()
                # Stereo input -> reshape to (num_samples, 2)
                stereo = raw_data.reshape(-1, 2)
            else:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details(f"Unsupported channel count: {request.channels}")
                return audio_processor_pb2.SmoothBlockResponse()

            # Initialize DSP Buffer engine
            buffer_processor = IslaBuffer(mode=request.mode, sr=request.sample_rate)
            processed_stereo = buffer_processor.process_buffer(stereo)

            if request.channels == 1:
                # Downmix back to mono for the response to match original channels
                processed_final = processed_stereo.mean(axis=1).astype(np.float32)
            else:
                processed_final = processed_stereo.astype(np.float32)

            return audio_processor_pb2.SmoothBlockResponse(
                audio_data=processed_final.tobytes(),
                sample_rate=request.sample_rate,
                channels=request.channels
            )

        except Exception as e:
            logging.error(f"Error in SmoothBlock: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return audio_processor_pb2.SmoothBlockResponse()

    def SmoothAudioStream(self, request_iterator, context):
        """Bidirectional streaming of audio chunks (AI-DJ)."""
        logging.info("Starting bidirectional SmoothAudioStream session.")
        buffer_processors = {}  # Cache processors by (mode, sample_rate) for performance

        try:
            for chunk in request_iterator:
                raw_data = np.frombuffer(chunk.audio_data, dtype=np.float32)
                if len(raw_data) == 0:
                    # Empty chunk, skip or yield empty
                    yield audio_processor_pb2.AudioStreamChunk(
                        audio_data=b"",
                        sample_rate=chunk.sample_rate,
                        channels=chunk.channels,
                        mode=chunk.mode,
                        end_of_stream=chunk.end_of_stream
                    )
                    continue

                # Get or initialize the processor
                key = (chunk.mode, chunk.sample_rate)
                if key not in buffer_processors:
                    buffer_processors[key] = IslaBuffer(mode=chunk.mode, sr=chunk.sample_rate)
                processor = buffer_processors[key]

                # Upmix/convert to stereo
                if chunk.channels == 1:
                    mono = raw_data
                    stereo = np.column_stack((mono, mono))
                elif chunk.channels == 2:
                    if raw_data.size % 2 != 0:
                        context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                        context.set_details("Stereo audio_data must contain an even number of float32 samples")
                        return
                    stereo = raw_data.reshape(-1, 2)
                else:
                    context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                    context.set_details(f"Unsupported channel count in stream: {chunk.channels}")
                    return

                # Run core DSP
                processed_stereo = processor.process_buffer(stereo)

                if chunk.channels == 1:
                    processed_final = processed_stereo.mean(axis=1).astype(np.float32)
                else:
                    processed_final = processed_stereo.astype(np.float32)

                yield audio_processor_pb2.AudioStreamChunk(
                    audio_data=processed_final.tobytes(),
                    sample_rate=chunk.sample_rate,
                    channels=chunk.channels,
                    mode=chunk.mode,
                    end_of_stream=chunk.end_of_stream
                )

                if chunk.end_of_stream:
                    logging.info("Received end of stream signal from client.")
                    break

        except Exception as e:
            logging.error(f"Error in SmoothAudioStream: {e}", exc_info=True)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))


def serve(port: int = 50051) -> grpc.Server:
    """Start and run the gRPC server."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    # Add AudioProcessor service
    audio_processor_pb2_grpc.add_AudioProcessorServicer_to_server(AudioProcessorServicer(), server)

    # Add Health Checking service for service discovery
    health_servicer = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)
    health_servicer.set("audio_processor.AudioProcessor", health_pb2.HealthCheckResponse.SERVING)

    bound_port = server.add_insecure_port(f"[::]:{port}")
    if bound_port == 0:
        raise RuntimeError(f"Failed to bind gRPC server to port {port}")
    logging.info(f"Starting ISLA gRPC server on port {bound_port}...")
    server.start()
    return server


if __name__ == "__main__":
    server = serve()
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logging.info("Shutting down gRPC server gracefully...")
        server.stop(0)
