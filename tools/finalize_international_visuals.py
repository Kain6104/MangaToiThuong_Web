from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from PIL import Image


WEB = Path(r"E:\MangaToiThuong_Web")
DATA = WEB / "data" / "heroes.json"
RESULTS_DIR = WEB / "build" / "international-import"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def image_meta(path: Path) -> dict:
    with Image.open(path) as image:
        return {
            "renderWidth": image.width,
            "renderHeight": image.height,
            "frameCount": getattr(image, "n_frames", 1),
        }


def main() -> None:
    results = {}
    for result_path in sorted(RESULTS_DIR.glob("visual-render*.json")):
        results.update(load(result_path))
    document = load(DATA)
    completed = 0
    for hero in document["heroes"]:
        if hero.get("sourceRegion") != "international":
            continue
        code = hero["code"]
        result = results.get(code, {})
        idle_path = WEB / "assets" / "heros" / code / "visual" / "idle.webp"
        attack_path = WEB / "assets" / "heros" / code / "visual" / "attack.webp"
        static_path = WEB / "img" / "heros" / f"{code}.png"
        manifest_path = WEB / "assets" / "heros" / code / "manifest.json"
        manifest = load(manifest_path)
        if result.get("error") or not all(path.is_file() for path in (idle_path, attack_path, static_path)):
            hero["animation"] = {"enabled": False, "renderer": manifest["renderer"], "manifest": hero["visual"]["manifest"], "webStatus": "STATIC_ONLY"}
            hero["visual"] = {"enabled": False, "manifest": hero["visual"]["manifest"], "type": "static-fallback", "status": "STATIC_ONLY"}
            manifest["webStatus"] = "STATIC_ONLY"
            manifest["effectParity"] = "STATIC_ONLY"
            save(manifest_path, manifest)
            continue

        idle = result["idle"]
        attack = result["attack"]
        idle_image = image_meta(idle_path)
        attack_image = image_meta(attack_path)
        manifest["webStatus"] = "ANIMATION_WITH_PARTIAL_VFX"
        manifest["effectParity"] = "PARTIAL_VFX"
        manifest["staticImage"] = f"./img/heros/{code}.png"
        manifest["staticRender"] = {
            **result["static"], "renderWidth": 1024, "renderHeight": 1280,
            "alphaMode": "straight-alpha", "fullBodySafeArea": True,
        }
        manifest["battleController"] = {
            "source": "res/fight/ani/ani.ExportJson",
            "sourceParity": "International and Rebuild SHA-256 identical",
            "movement": "shoot_o_x", "renderer": "Cocos Armature",
        }
        manifest["visuals"] = {
            "idle": {
                "type": "image", "format": "animated-webp", "src": f"./assets/heros/{code}/visual/idle.webp",
                "loop": True, "durationMs": idle["durationMs"], "fps": idle["fps"],
                "frameCount": idle_image["frameCount"], "renderWidth": idle_image["renderWidth"],
                "renderHeight": idle_image["renderHeight"], "encoding": idle["encoding"],
                "alphaMode": "straight-alpha", "renderer": "native-windows-offline-original-runtime",
                "source": f"res/card/role/{code}/{code}.skel animation stand; CardModel.lua timeScale=1/2",
            },
            "attack": {
                "type": "image", "format": "animated-webp", "src": f"./assets/heros/{code}/visual/attack.webp",
                "loop": False, "durationMs": attack["durationMs"], "fps": attack["fps"],
                "frameCount": attack_image["frameCount"], "renderWidth": attack_image["renderWidth"],
                "renderHeight": attack_image["renderHeight"], "encoding": attack["encoding"],
                "alphaMode": "straight-alpha", "renderer": "native-windows-offline-original-runtime",
                "source": "CardModel.lua ProSpellEffect + res/fight/ani/ani.ExportJson movement shoot_o_x",
                "effectParity": "PARTIAL_VFX",
            },
        }
        manifest["notes"] = [
            "Static and animated character renders use the original Spine 2.1.27 model and Cocos Armature transforms at 1080×1080.",
            "Only one visual layer is active in the modal; the static PNG is fully hidden after an animation frame is ready.",
            "Original referenced skill resources and source timing are retained under effects.",
            "No skill button is exposed because projectile, target hit, buff/summon and screen effects are not yet fully composited.",
            "No generic CSS aura, circle, glow or particle is used as skill VFX; FULL_EFFECT is intentionally not claimed.",
        ]
        save(manifest_path, manifest)
        hero["animation"] = {
            "enabled": True, "renderer": "prerendered-original", "manifest": f"./assets/heros/{code}/manifest.json",
            "webStatus": "ANIMATION_WITH_PARTIAL_VFX",
        }
        hero["visual"] = {
            "enabled": True, "manifest": f"./assets/heros/{code}/manifest.json", "type": "prerendered-original",
            "status": "ANIMATION_WITH_PARTIAL_VFX", "quality": "1080p-q96-alpha",
        }
        completed += 1

    source_counts = Counter(hero.get("sourceRegion", "rebuild") for hero in document["heroes"])
    document["meta"]["visualExport"]["animatedHeroes"] = sum(1 for hero in document["heroes"] if hero.get("visual", {}).get("enabled"))
    document["meta"]["visualExport"]["attackHeroes"] = sum(
        1 for hero in document["heroes"]
        if (WEB / "assets" / "heros" / hero["code"] / "visual" / "attack.webp").is_file()
    )
    document["meta"]["playableRule"] = (
        "Rebuild roster preserved; International: CardRes.ActorType=0, Visible=1, SSRCard=1, "
        "T_OnlyTableRes identity Leader=15; deduplicate OnlyId; HaremRes.ShangXian retained as status"
    )
    document["meta"]["internationalImport"].update({
        "animated": completed,
        "fullOriginalVfx": 0,
        "partialVfx": completed,
        "staticFallback": source_counts["international"] - completed,
    })
    save(DATA, document)
    print(json.dumps({"internationalAnimated": completed, "internationalTotal": source_counts["international"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
