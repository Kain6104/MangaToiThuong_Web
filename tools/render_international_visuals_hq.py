#!/usr/bin/env python3
"""Render imported international SR heroes with the original local runtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


WEB = Path(r"E:\MangaToiThuong_Web")
SOURCE_TOOL = Path(r"E:\MangaToiThuong-Rebuild\tools\hero_visual_export")
sys.path.insert(0, str(SOURCE_TOOL))

import render_local as source  # noqa: E402


SIZE = (1080, 1080)
FPS = 30
DEFAULT_CODES = ["H011", "H013", "H014", "H152", "H153", "H293", "H294", "H431", "H435", "H436", "H437"]


def save_webp(frames, output: Path, loop: bool) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        format="WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=round(1000 / FPS),
        loop=0 if loop else 1,
        # WebP preserves alpha losslessly. Quality 96 avoids the softening seen
        # in the old 640 px export while keeping 11 long idle clips practical.
        lossless=False,
        quality=96,
        method=3,
        exact=True,
        minimize_size=False,
    )
    return output.stat().st_size


def render(code: str) -> dict[str, object]:
    source.ANIMATION_CANVAS = SIZE
    static_path = WEB / "img" / "heros" / f"{code}.png"
    result: dict[str, object] = {"static": source.render_static(code, static_path)}
    visual_dir = WEB / "assets" / "heros" / code / "visual"
    for action in ("idle", "attack"):
        frames, metadata = source.animation_frames(code, action)
        metadata.update({
            "renderWidth": SIZE[0],
            "renderHeight": SIZE[1],
            "encoding": "webp-q96-alpha",
            "alphaMode": "straight-alpha",
            "bytes": save_webp(frames, visual_dir / f"{action}.webp", action == "idle"),
            "shaDistinctFrames": len({frame.tobytes() for frame in frames}),
        })
        result[action] = metadata
        del frames
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codes", nargs="+", default=DEFAULT_CODES)
    parser.add_argument("--result", type=Path, default=WEB / "build" / "international-import" / "visual-render.json")
    args = parser.parse_args()
    result_path = args.result
    existing = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
    for index, code in enumerate(args.codes, 1):
        print(f"[{index}/{len(args.codes)}] {code}", flush=True)
        try:
            existing[code] = render(code)
            print(json.dumps({code: existing[code]}, ensure_ascii=False), flush=True)
        except Exception as exc:
            existing[code] = {"error": str(exc)}
            print(json.dumps({code: existing[code]}, ensure_ascii=False), flush=True)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
