#!/usr/bin/env python3
"""
Cosmos Transfer: Convert 3D greenhouse renders into photorealistic video.

Uses NVIDIA's Cosmos Transfer API (build.nvidia.com) to transform
OpenUSD renders into realistic greenhouse imagery.

Usage:
  export NVIDIA_API_KEY="nvapi-YOUR_KEY"

  # Default (warm daylight greenhouse)
  python scripts/cosmos_transfer.py --image demo/frame.png

  # Rainy morning
  python scripts/cosmos_transfer.py --image demo/frame.png --condition rainy

  # Night with grow lights
  python scripts/cosmos_transfer.py --image demo/frame.png --condition night

  # Custom prompt
  python scripts/cosmos_transfer.py --image demo/frame.png --prompt "A foggy greenhouse at dawn..."
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile

# Predefined conditions for the greenhouse
CONDITIONS = {
    "daylight": (
        "A photorealistic greenhouse interior seen from the front. "
        "Rows of lush green leafy vegetables grow in raised wooden beds on dark rich soil. "
        "A white translucent plastic tunnel covers the greenhouse, letting warm natural sunlight filter through. "
        "The atmosphere is slightly humid with a warm golden tone. "
        "Photorealistic, high detail, natural lighting, 4K quality."
    ),
    "rainy": (
        "A photorealistic greenhouse interior during a rainy day. "
        "Water droplets stream down the translucent plastic tunnel walls. "
        "Rows of green leafy plants grow in raised beds with dark moist soil. "
        "Diffused grey light filters through the wet plastic panels creating soft shadows. "
        "The atmosphere is very humid and moody. Photorealistic, cinematic, 4K."
    ),
    "night": (
        "A photorealistic greenhouse interior at night illuminated by purple and pink LED grow lights. "
        "Rows of green plants in raised beds glow under the artificial lighting. "
        "The translucent tunnel walls are dark with a faint purple reflection. "
        "Warm pockets of light create dramatic contrast. "
        "Photorealistic, cinematic night scene, 4K quality."
    ),
    "morning": (
        "A photorealistic greenhouse interior at early morning sunrise. "
        "Golden dawn light streams through the translucent tunnel walls from the east side. "
        "Rows of green vegetables with morning dew droplets on their leaves grow in raised wooden beds. "
        "Mist hangs in the air catching the warm orange light rays. "
        "Photorealistic, beautiful golden hour, 4K quality."
    ),
    "harvest": (
        "A photorealistic greenhouse interior full of mature ready-to-harvest vegetables. "
        "Large heads of lettuce, kale, and leafy greens overflow from raised wooden beds. "
        "The tunnel structure has warm diffused sunlight. Workers' tools rest nearby. "
        "Rich green colors, abundant crop, photorealistic detail, 4K quality."
    ),
}


def image_to_video(image_path: str, output_path: str, num_frames: int = 121, fps: int = 24):
    """Create a short MP4 video by repeating a single image frame."""
    duration = num_frames / fps
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-c:v", "libx264",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        "-vf", f"scale=1024:-2,fps={fps}",
        "-preset", "fast",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print(f"Created video: {output_path} ({num_frames} frames, {duration:.1f}s)")


def call_cosmos_transfer(video_path: str, prompt: str, api_key: str, seed: int = 42):
    """Send video to Cosmos Transfer API and return photorealistic video."""
    try:
        import requests
    except ImportError:
        print("pip install requests", file=sys.stderr)
        sys.exit(1)

    # Try multiple possible endpoint URLs
    urls = [
        "https://ai.api.nvidia.com/v1/cosmos/nvidia/cosmos-transfer1-7b",
        "https://integrate.api.nvidia.com/v1/cosmos/nvidia/cosmos-transfer1-7b",
    ]
    url = os.environ.get("COSMOS_TRANSFER_URL", "").strip() or urls[0]

    with open(video_path, "rb") as f:
        video_b64 = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "prompt": prompt,
        "video": video_b64,
        "seed": seed,
        "guidance_scale": 7,
        "edge": {"control_weight": 0.8},
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    print(f"Sending to Cosmos Transfer API...")
    print(f"Prompt: {prompt[:100]}...")
    print(f"Video size: {len(video_b64) // 1024}KB (base64)")
    print("This may take 1-5 minutes...")

    response = None
    for try_url in ([url] if url not in urls else urls):
        print(f"Trying: {try_url}")
        response = requests.post(try_url, headers=headers, json=payload, timeout=600)
        if response.status_code != 404:
            break
        print(f"  Got 404, trying next URL...")

    if response.status_code != 200:
        print(f"API error {response.status_code}: {response.text[:500]}", file=sys.stderr)
        sys.exit(1)

    result = response.json()
    video_bytes = base64.b64decode(result["b64_video"])
    print(f"Received {len(video_bytes) // 1024}KB video")

    if result.get("upsampled_prompt"):
        print(f"Upsampled prompt: {result['upsampled_prompt'][:200]}")

    return video_bytes


def main():
    parser = argparse.ArgumentParser(description="Cosmos Transfer: 3D render → photorealistic video")
    parser.add_argument("--image", required=True, help="Path to greenhouse render (PNG/JPG)")
    parser.add_argument("--condition", choices=list(CONDITIONS.keys()), default="daylight",
                        help="Lighting/weather condition")
    parser.add_argument("--prompt", default=None, help="Custom prompt (overrides --condition)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--output", default=None, help="Output video path (default: demo/transfer_<condition>.mp4)")
    args = parser.parse_args()

    api_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not api_key:
        print("Error: Set NVIDIA_API_KEY environment variable", file=sys.stderr)
        print("Get one at: https://build.nvidia.com/nvidia/cosmos-transfer1-7b", file=sys.stderr)
        sys.exit(1)

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    image_path = args.image if os.path.isabs(args.image) else os.path.join(project_root, args.image)

    if not os.path.isfile(image_path):
        print(f"Error: Image not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    prompt = args.prompt or CONDITIONS[args.condition]
    output_path = args.output or os.path.join(project_root, "demo", f"transfer_{args.condition}.mp4")

    # Step 1: Convert image to video
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_video = tmp.name

    try:
        print(f"\n=== Cosmos Transfer: {args.condition.upper()} ===\n")
        image_to_video(image_path, tmp_video)

        # Step 2: Send to Cosmos Transfer
        video_bytes = call_cosmos_transfer(tmp_video, prompt, api_key, args.seed)

        # Step 3: Save output
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(video_bytes)
        print(f"\nSaved: {output_path}")
        print("Open the video to see your photorealistic greenhouse!")

    finally:
        if os.path.exists(tmp_video):
            os.unlink(tmp_video)


if __name__ == "__main__":
    main()
