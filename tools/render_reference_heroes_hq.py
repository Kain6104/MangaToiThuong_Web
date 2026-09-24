#!/usr/bin/env python3
"""Render the three visual QA heroes from original Spine/Cocos assets at 1080p.

This is intentionally a thin wrapper around the source-of-truth native renderer in
MangaToiThuong-Rebuild. It writes only the WebP outputs in this web workspace.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_TOOL = Path(r"E:\MangaToiThuong-Rebuild\tools\hero_visual_export")
sys.path.insert(0, str(SOURCE_TOOL))

import render_local as source  # noqa: E402


SIZE = (1080, 1080)
FPS = 30

# moSkillX097.lua uses FU._frameTimeDef=0.0333 and the actor-side sequence:
# zs_2 -> wait 10f -> cu -> wait 5f. The target-side zs_1/cu, hit, projectile,
# buff, and sound remain unported, so this export must stay PARTIAL_VFX.
source.SKILL_SPECS["H286"] = {
    "effect": "mixed_07",
    "intro": "zs_2",
    "loop": "cu",
    "introFrames": 10,
    "durationFrames": 27,
    "effectPos": (0.0, -80.0),
    "heroMovement": None,
    "heroPos": (0.0, 0.0),
    "evidence": (
        "SkillRes X097 + moSkillX097.lua: actor zs_2 at (0,-80), wait 10 frames, "
        "actor cu, wait 5; target zs_1/cu and hit remain unported"
    ),
}


def save_lossless(frames, output: Path, loop: bool) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        format="WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=round(1000 / FPS),
        loop=0 if loop else 1,
        lossless=True,
        method=4,
        exact=True,
        minimize_size=False,
    )
    return output.stat().st_size


def skill_frames_camera_locked(code: str):
    """Compose original effect batches without zooming the hero to VFX bounds.

    The game camera does not zoom out when a tall aura or screen effect starts.
    Keeping the hero transform stable also prevents the full body/weapon from
    shrinking to a few pixels when a source effect extends beyond the viewport.
    """
    spec = source.SKILL_SPECS[code]
    model_dir, skeleton, atlas = source.model_paths(code)
    effect_dir = ROOT / "assets" / "shared" / "effects" / "res" / "fight" / "skills" / str(spec["effect"])
    effect_skeleton = next(effect_dir.glob("*.skel"))
    effect_atlas = next(effect_dir.glob("*.atlas"))
    controller = source.CocosArmature()
    frame_count = int(spec["durationFrames"])
    times = [index / FPS for index in range(frame_count)]
    composed = []
    with source.NativeSpine(skeleton, atlas) as hero, source.NativeSpine(effect_skeleton, effect_atlas) as effect:
        hero_animation = "stand" if "stand" in hero.animations else hero.animations[0]
        hero_movement = spec.get("heroMovement")
        for frame_index, time_seconds in enumerate(times):
            hero_batches = hero.evaluate(hero_animation, time_seconds * 0.5, True)
            if hero_movement:
                movement_name = str(hero_movement)
                if time_seconds < controller.duration(movement_name):
                    hero_batches = source.transform_batches(hero_batches, controller.transform(movement_name, time_seconds))
            hero_x, hero_y = spec["heroPos"]
            if spec.get("heroMoveTo"):
                move_frames = max(1, int(spec["heroMoveFrames"]))
                move_percent = min(1.0, frame_index / move_frames)
                target_x, target_y = spec["heroMoveTo"]
                hero_x += (float(target_x) - float(hero_x)) * move_percent
                hero_y += (float(target_y) - float(hero_y)) * move_percent
            hero_batches = source.translate_batches(hero_batches, float(hero_x), float(hero_y))

            intro_frames = int(spec["introFrames"])
            effect_animation = str(spec["intro"])
            effect_time = time_seconds
            effect_loop = False
            if spec.get("loop") and frame_index >= intro_frames:
                effect_animation = str(spec["loop"])
                effect_time = (frame_index - intro_frames) / FPS
                effect_loop = True
            effect_batches = effect.evaluate(effect_animation, effect_time, effect_loop)
            effect_x, effect_y = spec["effectPos"]
            if spec.get("effectFollowsHero"):
                effect_x += float(hero_x)
                effect_y += float(hero_y)
            effect_batches = source.translate_batches(effect_batches, float(effect_x), float(effect_y))
            composed.append((hero_batches, effect_batches))

        hero_bounds = source.frame_bounds([hero_batches for hero_batches, _ in composed])
        effect_bounds = source.frame_bounds([effect_batches for _, effect_batches in composed])
        transform = source.make_transform(hero_bounds, *SIZE, margin_ratio=0.09)
        hero_textures = source.load_textures(model_dir, composed[0][0])
        first_effect = next(effect_batches for _, effect_batches in composed if effect_batches)
        effect_textures = source.load_textures(effect_dir, first_effect)
        frames = []
        for hero_batches, effect_batches in composed:
            hero_image = source.render_frame(hero_batches, hero_textures, transform, SIZE)
            effect_image = source.render_frame(effect_batches, effect_textures, transform, SIZE)
            frames.append(source.Image.alpha_composite(hero_image, effect_image))
    return frames, {
        "durationMs": round(frame_count * 1000 / FPS),
        "fps": FPS,
        "frameCount": frame_count,
        "heroBounds": hero_bounds,
        "effectBounds": effect_bounds,
        "camera": "hero-locked-source-viewport",
        "effect": spec["effect"],
        "effectAnimation": spec["intro"],
        "evidence": spec["evidence"],
        "parity": "PARTIAL_VFX",
    }


def render(code: str, skill_only: bool = False) -> dict[str, object]:
    source.ANIMATION_CANVAS = SIZE
    visual_dir = ROOT / "assets" / "heros" / code / "visual"
    result: dict[str, object] = {}
    if not skill_only:
        for action in ("idle", "attack"):
            frames, metadata = source.animation_frames(code, action)
            metadata.update(
                {
                    "width": SIZE[0],
                    "height": SIZE[1],
                    "encoding": "lossless-webp",
                    "alphaMode": "straight-alpha",
                    "bytes": save_lossless(frames, visual_dir / f"{action}.webp", action == "idle"),
                }
            )
            result[action] = metadata

    frames, metadata = skill_frames_camera_locked(code)
    metadata.update(
        {
            "width": SIZE[0],
            "height": SIZE[1],
            "encoding": "lossless-webp",
            "alphaMode": "straight-alpha",
            "bytes": save_lossless(frames, visual_dir / "skill1.webp", False),
        }
    )
    result["skill1"] = metadata
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codes", nargs="+", default=["H286", "H001", "H007"])
    parser.add_argument("--skill-only", action="store_true")
    args = parser.parse_args()
    for code in args.codes:
        print(json.dumps({code: render(code, args.skill_only)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
