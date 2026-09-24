from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_IDS = {
    1261449521, 1261449523, 1261449524, 1261450034, 1261450035, 1261450547,
    1261450548, 1261451057, 1261451061, 1261451062, 1261451063,
}
EXPECTED_ORDER = ["SSR", "SR", "SSS", "SS", "S", "A", "B"]


def contains_full_effect(value) -> bool:
    if isinstance(value, dict):
        return any(contains_full_effect(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_full_effect(item) for item in value)
    return value == "FULL_EFFECT"


def main() -> None:
    data = json.loads((ROOT / "data" / "heroes.json").read_text(encoding="utf-8"))
    html = (ROOT / "heroes.html").read_text(encoding="utf-8")
    heroes = [hero for hero in data["heroes"] if hero.get("sourceRegion") == "international"]
    errors = []
    image_rows = []
    if {int(hero["id"]) for hero in heroes} != EXPECTED_IDS:
        errors.append("international OnlyId set mismatch")
    if data["meta"].get("rarityOrder") != EXPECTED_ORDER:
        errors.append("rarity order mismatch")
    if any(hero.get("rarity") != "SR" for hero in heroes):
        errors.append("non-SR deduplicated identity present")
    if any(hero.get("evidence", {}).get("progressionLeaders") != [15, 16] for hero in heroes):
        errors.append("progression leader evidence mismatch")

    for hero in heroes:
        code = hero["code"]
        png = ROOT / hero["image"].removeprefix("./")
        with Image.open(png) as image:
            rgba = image.convert("RGBA")
            bbox = rgba.getchannel("A").getbbox()
            if image.size != (1024, 1280) or not bbox:
                errors.append(f"{code}: invalid static render")
            elif bbox[0] <= 0 or bbox[1] <= 0 or bbox[2] >= image.width or bbox[3] >= image.height:
                errors.append(f"{code}: static artwork touches/crops at canvas edge")

        manifest_path = ROOT / hero["visual"]["manifest"].removeprefix("./")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        actions = list(manifest.get("visuals", {}))
        if actions != ["idle", "attack"]:
            errors.append(f"{code}: unexpected action set {actions}")
        if manifest.get("effectParity") != "PARTIAL_VFX" or contains_full_effect(manifest):
            errors.append(f"{code}: VFX status is overstated")
        motion_meta = {}
        for action in ("idle", "attack"):
            entry = manifest.get("visuals", {}).get(action, {})
            motion = ROOT / str(entry.get("src", "")).removeprefix("./")
            if not motion.is_file():
                errors.append(f"{code}: missing {action}")
                continue
            with Image.open(motion) as image:
                motion_meta[action] = {"size": list(image.size), "frames": getattr(image, "n_frames", 1)}
                if image.size != (1080, 1080) or getattr(image, "n_frames", 1) < 2:
                    errors.append(f"{code}: invalid {action} resolution/frames")
        image_rows.append({"code": code, "staticBbox": list(bbox) if bbox else None, **motion_meta})

        if len(hero.get("skills", [])) != 4 or any(skill.get("vfxStatus") != "PARTIAL_VFX" for skill in hero.get("skills", [])):
            errors.append(f"{code}: skill localization/VFX status mismatch")
        progression = hero.get("progression", {})
        if len(progression.get("weaponSkins", [])) != 4 or not progression.get("awakening"):
            errors.append(f"{code}: progression evidence incomplete")

    required_html = [
        "SSR: 700", "SR: 600", "SSS: 500", "sort: 'rarity'",
        ".hero-rarity.rarity-SSR", ".hero-rarity.rarity-SR", ".hero-rarity.rarity-SSS",
        "@media (prefers-reduced-motion: reduce)", ".hero-modal-rarity-line .hero-rarity",
    ]
    for marker in required_html:
        if marker not in html:
            errors.append(f"heroes.html missing {marker}")

    result = {
        "status": "PASS" if not errors else "FAIL",
        "total": len(data["heroes"]),
        "international": len(heroes),
        "rarities": dict(Counter(hero["rarity"] for hero in data["heroes"])),
        "localizedSkills": sum(len(hero.get("skills", [])) for hero in heroes),
        "localizedBonds": sum(len(hero.get("bonds", [])) for hero in heroes),
        "weaponRows": sum(len(hero.get("progression", {}).get("weaponSkins", [])) for hero in heroes),
        "animated": sum(bool(hero.get("visual", {}).get("enabled")) for hero in heroes),
        "fullVfx": sum(hero.get("visual", {}).get("status") == "FULL_EFFECT" for hero in heroes),
        "images": image_rows,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not errors else 1)


if __name__ == "__main__":
    main()
