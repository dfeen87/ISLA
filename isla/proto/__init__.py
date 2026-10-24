"""Compatibility exports for ISLA's existing gRPC/protobuf Python stubs.

The protobuf wire package remains audio_processor for interoperability.
"""
from phased_music_notes.proto import audio_processor_pb2, audio_processor_pb2_grpc

__all__ = ["audio_processor_pb2", "audio_processor_pb2_grpc"]
