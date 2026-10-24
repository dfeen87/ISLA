"""
Lightweight test client for ISLA gRPC service.
Allows developers to query SmoothBlock or stream data via SmoothAudioStream.
"""

import sys
import grpc
import numpy as np

from phased_music_notes.proto import audio_processor_pb2
from phased_music_notes.proto import audio_processor_pb2_grpc


def smooth_block_grpc(audio: np.ndarray, mode: str = "velvet", sr: int = 44100, host: str = "localhost", port: int = 50051) -> np.ndarray:
    """
    Sends a complete block of audio to the gRPC server and returns the processed audio.
    """
    channel = grpc.insecure_channel(f"{host}:{port}")
    stub = audio_processor_pb2_grpc.AudioProcessorStub(channel)

    channels = 1 if audio.ndim == 1 else audio.shape[1]

    # Raw float32 bytes representation
    audio_data_bytes = audio.astype(np.float32).tobytes()

    request = audio_processor_pb2.SmoothBlockRequest(
        audio_data=audio_data_bytes,
        sample_rate=sr,
        channels=channels,
        mode=mode
    )

    try:
        response = stub.SmoothBlock(request)
        processed = np.frombuffer(response.audio_data, dtype=np.float32)
        if response.channels == 2:
            processed = processed.reshape(-1, 2)
        channel.close()
        return processed
    except grpc.RpcError as e:
        channel.close()
        print(f"gRPC Error: {e.code()} - {e.details()}", file=sys.stderr)
        raise


def smooth_stream_grpc(audio: np.ndarray, chunk_size: int = 4096, mode: str = "velvet", sr: int = 44100, host: str = "localhost", port: int = 50051):
    """
    Streams audio to the gRPC server chunk-by-chunk and yields the processed chunks.
    """
    channel = grpc.insecure_channel(f"{host}:{port}")
    stub = audio_processor_pb2_grpc.AudioProcessorStub(channel)

    channels = 1 if audio.ndim == 1 else audio.shape[1]

    def request_generator():
        num_samples = len(audio)
        for start in range(0, num_samples, chunk_size):
            end = min(start + chunk_size, num_samples)
            chunk_slice = audio[start:end].astype(np.float32)
            end_of_stream = (end == num_samples)

            yield audio_processor_pb2.AudioStreamChunk(
                audio_data=chunk_slice.tobytes(),
                sample_rate=sr,
                channels=channels,
                mode=mode,
                end_of_stream=end_of_stream
            )

    try:
        response_iterator = stub.SmoothAudioStream(request_generator())
        for response in response_iterator:
            chunk_data = np.frombuffer(response.audio_data, dtype=np.float32)
            if response.channels == 2:
                chunk_data = chunk_data.reshape(-1, 2)
            yield chunk_data
    except grpc.RpcError as e:
        print(f"gRPC Stream Error: {e.code()} - {e.details()}", file=sys.stderr)
        raise
