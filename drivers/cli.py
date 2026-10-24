"""
CLI driver for ISLA.

Smooth Audio Notes from the command line:
    isla --input input.wav --output output.wav --mode velvet
"""

import argparse
import sys
from pathlib import Path

from src.main import IslaMusicEngine


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

    # Required together for offline processing; no arguments opens ALIVE.
    parser.add_argument(
        "--input",
        type=str,
        help="Input audio file path (WAV guaranteed; other formats depend on libsndfile).",
    )
    parser.add_argument(
        "--output",
        type=str,
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


def main(argv=None) -> int:
    parser = create_parser()
    arguments = sys.argv[1:] if argv is None else argv
    if not arguments:
        from isla.terminal import run_terminal
        return run_terminal()
    args = parser.parse_args(arguments)
    if not args.input or not args.output:
        parser.error("offline processing requires both --input and --output; use isla without arguments for ALIVE")

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
