"""
CLI driver for ISLA.

Smooth Audio Notes from the command line:
    isla --input input.wav --output output.wav --mode velvet
"""

import argparse
import sys
from pathlib import Path

from src.main import IslaMusicEngine  # adjust import if needed


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="isla",
        description="Smooth Audio Notes with phase-aligned transitions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  isla --input input.wav --output output.wav --mode velvet
  isla --input piano.wav --output piano_soft.wav --mode melt
        """,
    )

    # Required
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Input audio file path (e.g., WAV, FLAC, MP3).",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output audio file path (e.g., output.wav).",
    )

    # Optional
    parser.add_argument(
        "--mode",
        type=str,
        default="velvet",
        help="Smoothing mode (e.g., velvet, legato, melt).",
    )

    return parser


def main() -> int:
    parser = create_parser()
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 1

    try:
        engine = IslaMusicEngine(mode=args.mode)
        engine.smooth_file(str(input_path), str(output_path))
    except Exception as e:
        print(f"Error during processing: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
