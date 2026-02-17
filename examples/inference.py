#!/usr/bin/env python3
"""
Cosmos inference: run image-style transfer over a video from a JSON config.

Reads a config (e.g. demo/image_style.json) and writes the result under the
given output directory.

Usage:
  export NVIDIA_API_KEY="nvapi-YOUR_KEY"

  python examples/inference.py -i demo/image_style.json -o outputs/greenhouse_style

Outputs:
  outputs/greenhouse_style/result.mp4   (or <name>.mp4 from config)
"""

import argparse
import json
import os
import sys
import tempfile

# Allow importing from scripts when run from repo root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.cosmos_transfer import call_cosmos_transfer, image_to_video


def resolve_path(path: str, root: str) -> str:
    """Return absolute path; if path is relative, join with root."""
    return path if os.path.isabs(path) else os.path.join(root, path)


def main():
    parser = argparse.ArgumentParser(
        description="Cosmos inference: image style transfer over video from JSON config"
    )
    parser.add_argument(
        "-i", "--input",
        required=True,
        metavar="CONFIG.json",
        help="Path to JSON config (name, prompt, video_path, image_context_path, seed)",
    )
    parser.add_argument(
        "-o", "--output-dir",
        required=True,
        metavar="DIR",
        help="Output directory (e.g. outputs/greenhouse_style)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not api_key:
        print("Error: Set NVIDIA_API_KEY environment variable", file=sys.stderr)
        print("Get one at: https://build.nvidia.com/nvidia/cosmos-transfer1-7b", file=sys.stderr)
        sys.exit(1)

    config_path = resolve_path(args.input, PROJECT_ROOT)
    if not os.path.isfile(config_path):
        print(f"Error: Config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    with open(config_path, "r") as f:
        config = json.load(f)

    name = config.get("name", "result")
    prompt = config.get("prompt", "")
    video_path = config.get("video_path", "")
    image_context_path = config.get("image_context_path", "")
    seed = int(config.get("seed", 1))

    if not prompt:
        print("Error: config must set 'prompt'", file=sys.stderr)
        sys.exit(1)

    video_abs = resolve_path(video_path, PROJECT_ROOT) if video_path else ""
    image_abs = resolve_path(image_context_path, PROJECT_ROOT) if image_context_path else ""

    # Use existing video if present; otherwise build video from image
    if video_path and os.path.isfile(video_abs):
        input_video = video_abs
        print(f"Using input video: {input_video}")
    elif image_context_path and os.path.isfile(image_abs):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            input_video = tmp.name
        try:
            image_to_video(image_abs, input_video)
        except Exception as e:
            if os.path.exists(input_video):
                os.unlink(input_video)
            raise e
    else:
        print(
            "Error: config must provide an existing 'video_path' or 'image_context_path'",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        print(f"\n=== Cosmos inference: {name} ===\n")
        video_bytes = call_cosmos_transfer(input_video, prompt, api_key, seed=seed)

        output_dir = resolve_path(args.output_dir, PROJECT_ROOT)
        os.makedirs(output_dir, exist_ok=True)
        out_name = f"{name}.mp4" if name else "result.mp4"
        output_path = os.path.join(output_dir, out_name)
        with open(output_path, "wb") as f:
            f.write(video_bytes)
        print(f"\nSaved: {output_path}")
    finally:
        if input_video != video_abs and os.path.exists(input_video):
            os.unlink(input_video)


if __name__ == "__main__":
    main()
