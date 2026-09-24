from __future__ import annotations

import importlib.util
import json
import shutil
import struct
import zlib
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image


WEB = Path(r"E:\MangaToiThuong_Web")
SOURCE = Path(r"E:\MangaAllstar\forensics\ma_ups")
ASSETS = SOURCE / "assets"
REPORTS = SOURCE / "reports"
DATA = WEB / "data" / "heroes.json"
HERO_ASSETS = WEB / "assets" / "heros"
SHARED = WEB / "assets" / "shared" / "international"
HERO_IMAGES = WEB / "img" / "heros"
SKILL_IMAGES = WEB / "img" / "skills"

RARITY_ORDER = ["SSR", "SR", "SSS", "SS", "S", "A", "B"]

# These codes are sourced from SR_HERO_EVIDENCE.tsv/modelResource, not inferred
# from row order or translated names.
CODE_BY_ID = {
    1261449521: "H011",
    1261449523: "H013",
    1261449524: "H014",
    1261450034: "H152",
    1261450035: "H153",
    1261450547: "H293",
    1261450548: "H294",
    1261451057: "H431",
    1261451061: "H435",
    1261451062: "H436",
    1261451063: "H437",
}

HERO_LOCALIZATION = {
    1261449521: ("Natsu", ["Naz", "纳兹"], "Pháp sư Diệt Long của Fairy Tail."),
    1261449523: ("Kagura", ["Kagula", "神乐"], "Ta là lưu manh, còn sợ ai?"),
    1261449524: ("Sanji", ["香吉士"], "Yêu phụ nữ, một quý ông trong giới hải tặc."),
    1261450034: ("Sasuke", ["佐助"], "Ninja thiên tài của tộc Uchiha tại Làng Lá."),
    1261450035: ("Athena", ["雅典娜"], "Nữ thần của nghệ thuật và thủ công."),
    1261450547: ("Batman", ["蝙蝠侠"], "Ta rất giàu."),
    1261450548: ("Zoro", ["索隆"], "Kiếm sĩ Tam Kiếm Phái, chiến đấu bằng ba thanh kiếm."),
    1261451057: ("Killua", ["奇犽"], "Thiếu niên hệ điện thích chơi yo-yo."),
    1261451061: ("Triệu Vân", ["Zhao Yun", "赵云"], "Ta là Triệu Tử Long! Mau thả cô gái ra."),
    1261451062: ("Gaara", ["我爱罗"], "Ta tồn tại để tiêu diệt tất cả, trừ chính mình."),
    1261451063: ("Piccolo", ["比克"], "Ta muốn thống trị thế giới."),
}

SKILL_LOCALIZATION = {
    1479684916: ("Hoàn Trả Sức Mạnh", "Bị động; ngẫu nhiên thi triển các kỹ năng khác từ 2 đến 4 lần."),
    1479684917: ("Tia Ma Lực", "Tiên thủ; làm choáng một địch và gây sát thương lên mục tiêu."),
    1479684918: ("Cơ Động Cao", "Bị động; tăng mạnh tốc độ bản thân."),
    1479684919: ("Ma Quán Quang Sát Phá", "Kết liễu một địch; chỉ có hiệu lực trong PvP."),
    1479684912: ("Chân Quỷ", "Chủ động; gây sát thương lên một mục tiêu."),
    1479684913: ("Đòn Kết Liễu", "Gây sát thương lên mục tiêu khi HP của địch thấp hơn 50%."),
    1479684914: ("Súp Hormone", "Bị động; hồi sinh đồng minh đầu tiên tử trận."),
    1479684915: ("Bộ Pháp Trăng", "Bị động; tăng tốc độ bản thân."),
    1479684662: ("Mưa Rơi", "Chủ động; gây sát thương vật lý lên toàn bộ địch."),
    1479684663: ("Rong Biển Muối", "Chủ động; đánh dấu địch và giảm kháng vật lý của mục tiêu."),
    1479684664: ("Sức Mạnh Nguyệt Tộc", "Bị động; gây sát thương vật lý bằng 10% HP hiện tại lên toàn bộ địch."),
    1479684665: ("Căm Ghét Bạo Lực", "Bị động; tăng công bản thân."),
    1479684658: ("Phân Thân Cát", "Chủ động; tạo 2 phân thân kế thừa một phần công và chịu sát thương thay."),
    1479684659: ("Kiếm Cát", "Chủ động; gây sát thương và làm choáng toàn bộ địch."),
    1479684660: ("Đạn Cát", "Gây sát thương diện rộng và né đòn đánh của địch trong 5 giây."),
    1479684661: ("Khiên Hạc", "Khi sắp tử trận, trở nên bất tử và nhận thêm tốc độ."),
    1479684408: ("Nhất Kiếm Phái", "Tiên thủ; gây sát thương lên một địch."),
    1479684409: ("Nhị Kiếm Phái", "Chủ động; gây sát thương và làm choáng một địch."),
    1479684656: ("Haki Quan Sát", "Bị động; khi tấn công có 30% xác suất gây sát thương gấp 3 lần."),
    1479684657: ("Haki Vũ Trang", "Bị động; tăng công, kháng vật lý và kháng phép bản thân."),
    1479684404: ("Bậc Thầy Uy Hiếp", "Tiên thủ; gây sát thương lên toàn bộ địch và giảm 50% công của chúng."),
    1479684405: ("Ta Rất Giàu", "Chủ động; ném tiền, gây sát thương và làm choáng địch."),
    1479684406: ("Bậc Thầy Võ Thuật", "Đòn đánh gây thêm sát thương; chênh lệch công càng lớn, sát thương càng cao."),
    1479684407: ("Thể Lực Tối Thượng", "Bị động; tăng HP, công và tốc độ bản thân."),
    1479684400: ("Ân Huệ Tình Yêu", "Chủ động; hồi phục cho toàn bộ đồng minh."),
    1479684401: ("Nữ Thần Ánh Sáng", "Ban khiên bất tử cho đồng minh có HP thấp nhất."),
    1479684402: ("Nữ Thần Khiên", "Bị động; tăng kháng vật lý và kháng phép cho toàn bộ đồng minh."),
    1479684403: ("Nữ Thần Trí Tuệ", "Bị động; tăng công cho toàn bộ đồng minh."),
    1479684150: ("Sharingan", "Chủ động; gây thêm sát thương bằng 100% HP của địch."),
    1479684151: ("Ảo Thuật", "Bị động; miễn nhiễm phần lớn hiệu ứng bất lợi, nhưng không miễn sát thương."),
    1479684152: ("Hóa Cừu", "Chủ động; biến 2 địch được chọn thành động vật nhỏ."),
    1479684153: ("Thuật Thế Thân", "Bị động; giảm 20% sát thương phải chịu từ một đòn."),
    1479684146: ("Lôi Giáng", "Tiên thủ; khiến HP của địch giảm 16%."),
    1479684147: ("Thần Tốc", "Bị động; khi bị địch đánh, HP của kẻ tấn công giảm 18%."),
    1479684148: ("Tốc Hành", "Bị động; miễn nhiễm kỹ năng phép và hiệu ứng khống chế."),
    1479684149: ("Bất Bại", "Khi tử trận, trở nên bất tử và được tăng tốc độ."),
    1479620920: ("Mảnh Vỡ Hỏa Long", "Giảm 100% kháng vật lý và kháng phép của toàn bộ địch."),
    1479620921: ("Rồng Mặt Trời", "Kỹ năng phản kích; gây sát thương phép diện rộng lên toàn bộ địch."),
    1479684144: ("Chế Độ Hỏa Long", "Gây một lần sát thương lôi và một lần sát thương hỏa."),
    1479684145: ("Long Vương Giáng Thế", "Bị động; giảm 50% sát thương phải chịu."),
    1479620916: ("Thương Xà Bàn", "Phản kích; gây sát thương lên toàn bộ địch. Công của địch càng cao, sát thương càng lớn."),
    1479620917: ("Bá Vương Thương", "Chủ động; gây sát thương và làm choáng toàn bộ địch."),
    1479620918: ("Thương Họ Triệu", "Bị động; khi tấn công có 30% xác suất gây sát thương gấp 3 lần."),
    1479620919: ("Ta Là Triệu Tử Long!", "Khi sắp tử trận, trở nên bất tử và nhận thêm tốc độ."),
}

BOND_NAME_LOCALIZATION = {
    "Fire and electric": "Hỏa Điện",
    "Summon array": "Trận Đồ Triệu Hồi",
    "Magic genius": "Thiên Tài Ma Pháp",
    "Magic wu": "Ma Võ",
    "god is coming": "Thần Linh Giáng Thế",
    "Hurting player": "Càng Đau Càng Mạnh",
    "Physical genius": "Thiên Tài Thể Thuật",
    "Barbarian": "Cuồng Chiến",
    "Addicted to girls": "Mê Gái",
    "Invincible": "Bất Khả Chiến Bại",
    "weaker more stronger": "Càng Yếu Càng Mạnh",
    "Naruto class seven": "Đội 7 Naruto",
    "I am rich": "Ta Rất Giàu",
    "One Piece": "One Piece",
    "Swordsman": "Kiếm Sĩ",
    "Electric flint": "Điện Quang Hỏa Thạch",
    "Assassins Guild": "Hội Sát Thủ",
    "Best Partner": "Đồng Đội Tối Ưu",
    "Guns": "Súng Đạn",
    "Heaven Earth": "Thiên Địa",
    "magic weapon": "Pháp Khí",
    "Sand messenger": "Sứ Giả Cát",
    "Unbeatable master": "Cao Thủ Bất Bại",
    "Ninja contest": "Đại Chiến Ninja",
    "Single in group": "Cô Độc Giữa Đám Đông",
    "Single Attack": "Đơn Thể Công Kích",
    "Dragon Ball": "Ngọc Rồng",
}

FACTIONS = {
    1: "Học viện Thánh·Caesar",
    2: "Học viện Thu Diệp·Nãi Đề",
    3: "Học viện Diệu·Quy Nguyên",
    4: "Học viện New Lily 3",
}

ROLES = {0: "Đỡ đòn hàng trước", 1: "Sát thương hàng sau", 2: "Pháp sư hàng sau"}
ROLE_BY_LOCATION = {
    "Front-line Tank": "Đỡ đòn hàng trước",
    "Rearline Damage Dealer": "Sát thương hàng sau",
    "Rearline Support": "Hỗ trợ hàng sau",
    "Rearline Mage": "Pháp sư hàng sau",
}

AWAKENING_LOCALIZATION = {
    "Zhao Zilong": "Triệu Tử Long", "Dragon Wizard": "Pháp Sư Diệt Long",
    "Zoldyck": "Zoldyck", "Uchiha": "Uchiha", "Goddess": "Nữ Thần",
    "Dark Knight": "Kỵ Sĩ Bóng Đêm", "Straw hat Gang": "Băng Mũ Rơm",
    "Soil Ninja": "Ninja Thổ", "The Ultimate Ninja": "Ninja Tối Thượng",
    "Vinsmoke": "Vinsmoke", "Super Devil": "Đại Ma Vương",
}

WEAPON_TIER_LOCALIZATION = {1: "Chiến Binh", 2: "Hỏa Diệm", 3: "Hàn Thiên", 4: "Tận Thế"}

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def web_path(path: Path) -> str:
    return "./" + path.relative_to(WEB).as_posix()


def build_cczp_key() -> list[int]:
    mask = 0xFFFFFFFF
    key = [0] * 1024
    parts = [0x12345678] * 4
    z = key[-1]
    total = 0
    for _ in range(6):
        total = (total + 0x9E3779B9) & mask
        e = (total >> 2) & 3
        for p in range(1023):
            y = key[p + 1]
            mx = ((((z >> 5) ^ ((y << 2) & mask)) + ((y >> 3) ^ ((z << 4) & mask))) ^ (((total ^ y) + (parts[(p & 3) ^ e] ^ z)) & mask)) & mask
            key[p] = (key[p] + mx) & mask
            z = key[p]
        y = key[0]
        p = 1023
        mx = ((((z >> 5) ^ ((y << 2) & mask)) + ((y >> 3) ^ ((z << 4) & mask))) ^ (((total ^ y) + (parts[(p & 3) ^ e] ^ z)) & mask)) & mask
        key[p] = (key[p] + mx) & mask
        z = key[p]
    return key


CCZP_KEY = build_cczp_key()


def decode_png(source: Path) -> bytes:
    raw = source.read_bytes()
    if raw.startswith(PNG_SIG):
        return raw
    if raw[:4] == b"CCZp":
        data = bytearray(raw)
        count = (len(data) - 12) // 4
        words = list(struct.unpack_from(f"<{count}I", data, 12))
        key_index = 0
        for i in range(min(count, 512)):
            words[i] ^= CCZP_KEY[key_index]
            key_index = (key_index + 1) % 1024
        for i in range(512, count, 64):
            words[i] ^= CCZP_KEY[key_index]
            key_index = (key_index + 1) % 1024
        struct.pack_into(f"<{count}I", data, 12, *words)
        expected = struct.unpack_from(">I", data, 12)[0]
        decoded = zlib.decompress(bytes(data[16:]))
        if len(decoded) != expected or not decoded.startswith(PNG_SIG):
            raise ValueError(f"Không giải mã được CCZp: {source}")
        return decoded
    if raw[:4] == b"CCZ!":
        expected = struct.unpack_from(">I", raw, 12)[0]
        decoded = zlib.decompress(raw[16:])
        if len(decoded) != expected or not decoded.startswith(PNG_SIG):
            raise ValueError(f"Không giải mã được CCZ: {source}")
        return decoded
    raise ValueError(f"Texture không phải PNG/CCZ: {source}")


def export_png(source: Path, target: Path) -> dict:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(decode_png(source))
    with Image.open(target) as image:
        image.verify()
    with Image.open(target) as image:
        return {"path": web_path(target), "width": image.width, "height": image.height, "mode": image.mode}


def copy_resource(resource: str, cache: dict[str, list[dict]]) -> list[dict]:
    if not resource:
        return []
    if resource in cache:
        return cache[resource]
    rel = Path(resource.replace("\\", "/").lstrip("./"))
    exact = ASSETS / rel
    candidates: list[Path] = []
    if exact.is_file():
        candidates.append(exact)
        if exact.suffix.lower() in {".exportjson", ".plist", ".atlas", ".xml"}:
            candidates.extend(exact.parent.glob(exact.stem + ".*"))
    elif exact.is_dir():
        candidates.extend(p for p in exact.rglob("*") if p.is_file())
    elif exact.parent.exists():
        candidates.extend(exact.parent.glob(exact.name + ".*"))
    result = []
    seen = set()
    for source in candidates:
        if not source.is_file() or source.resolve() in seen:
            continue
        seen.add(source.resolve())
        relative = source.relative_to(ASSETS)
        target = SHARED / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            if source.suffix.lower() == ".png":
                export_png(source, target)
                fmt = "CCZ/PNG→PNG"
            else:
                shutil.copy2(source, target)
                fmt = source.suffix.lower().lstrip(".") or "binary"
            result.append({"path": web_path(target), "format": fmt})
        except Exception as exc:
            result.append({"source": str(source), "error": str(exc)})
    cache[resource] = result
    return result


def decode_lucky_rows() -> list[dict]:
    module_path = REPORTS / "decode_sproto_aux.py"
    spec = importlib.util.spec_from_file_location("ma_aux_decoder", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    schema = [
        ("ID", "integer", False), ("Name", "string", False), ("Desc", "string", False),
        ("HeroName", "string", False), ("ID0", "integer", True), ("Lucky", "integer", False),
        ("AttackRate", "number", False), ("SpeedRate", "number", False), ("HPRate", "number", False),
        ("WuFangRate", "number", False), ("MoFangRate", "number", False), ("CritRate", "number", False),
        ("DodgeRate", "number", False), ("DamageRateW", "number", False), ("DamageRateM", "number", False),
        ("GoldDropAcc", "number", False), ("HeroName1", "string", False), ("ID1", "integer", True),
        ("HeroName2", "string", False), ("ID2", "integer", True), ("HeroName3", "string", False),
        ("ID3", "integer", True), ("HeroName4", "string", False), ("ID4", "integer", True),
        ("HeroName5", "string", False), ("ID5", "integer", True), ("Target", "integer", False),
        ("CardNation", "integer", False), ("Occupation", "integer", False),
        ("ActiveMainProperty", "integer", False), ("HeroCount", "integer", False),
        ("Activated", "integer", False), ("relatedID", "integer", False),
    ]
    raw = ASSETS / "src" / "app" / "res" / "luaBin" / "LuckySkillRes.bin"
    return module.decode_book(raw.read_bytes(), schema)


def rate_text(row: dict) -> str:
    labels = {
        "AttackRate": "Công", "SpeedRate": "Tốc", "HPRate": "HP",
        "WuFangRate": "Kháng vật lý", "MoFangRate": "Kháng phép",
        "CritRate": "Bạo kích", "DodgeRate": "Né",
        "DamageRateW": "Sát thương vật lý", "DamageRateM": "Sát thương phép",
        "GoldDropAcc": "Vàng rơi",
    }
    parts = []
    for field, label in labels.items():
        value = float(row.get(field) or 0)
        if value:
            parts.append(f"{label} +{value * 100:g}%")
    return "; ".join(parts)


def effect_rows(skill: dict, cache: dict[str, list[dict]]) -> list[dict]:
    output = []
    action = skill.get("ActionBeforeSkill")
    if action:
        output.append({
            "type": "CHARACTER_ANIMATION", "field": "ActionBeforeSkill", "source": action,
            "timing": skill.get("ActionTimeBeforeSkill") or 0,
            "renderer": "Cocos Armature ani.ExportJson", "webStatus": "PACKAGED_NOT_COMPOSITED",
        })
    for field, kind, timing in (
        ("PreEffect", "PARTICLE", "PreTime"), ("SelfEffect", "PARTICLE", "SelfTime"),
        ("ProEffect", "PROJECTILE", "ProTime"), ("PostEffect", "HIT_EFFECT", "PostTime"),
    ):
        resource = skill.get(field)
        if resource:
            output.append({
                "type": kind, "field": field, "source": resource, "timing": skill.get(timing) or 0,
                "webAssets": copy_resource(resource, cache), "webStatus": "PACKAGED_NOT_COMPOSITED",
            })
    if skill.get("Buff") or skill.get("SkillIDForBuf"):
        output.append({
            "type": "BUFF_EFFECT", "field": "Buff/SkillIDForBuf",
            "source": skill.get("SkillIDForBuf") or skill.get("Buff"),
            "timing": skill.get("BufferTime") or 0, "webStatus": "PACKAGED_NOT_COMPOSITED",
        })
    for field in ("SoundBeforeSkill", "PreSoundEffect", "SelfSoundEffect", "ProSoundEffect", "PostSoundEffect"):
        resource = skill.get(field)
        if resource:
            output.append({
                "type": "SOUND", "field": field, "source": resource,
                "webAssets": copy_resource(resource, cache), "webStatus": "PACKAGED_NOT_PLAYED",
            })
    return output


def main():
    card_rows = load(REPORTS / "CardRes.decoded.json")
    only_rows = load(REPORTS / "T_OnlyTableRes.decoded.json")
    harem_rows = load(REPORTS / "HaremRes.decoded.json")
    skill_rows = load(REPORTS / "SkillRes.decoded.json")
    item_rows = load(REPORTS / "ItemRes.decoded.json")
    weapon_rows = load(REPORTS / "T_WeaponRes.decoded.json")
    awakening_rows = load(REPORTS / "juexingRes.decoded.json")
    hero_show_rows = load(REPORTS / "HeroShowRes.decoded.json")
    lucky_rows = decode_lucky_rows()
    skill_by_id = {int(row["ID"]): row for row in skill_rows}
    item_by_id = {int(row["ID"]): row for row in item_rows}

    identity_rows = {int(row["ID"]): row for row in only_rows if int(row.get("Leader") or 0) == 15}
    candidate_groups = {}
    for row in card_rows:
        only_id = int(row.get("OnlyId") or 0)
        if only_id not in CODE_BY_ID:
            continue
        if int(row.get("ActorType") or 0) != 0 or int(row.get("Visible") or 0) != 1 or int(row.get("SSRCard") or 0) != 1:
            continue
        candidate_groups.setdefault(only_id, []).append(row)

    if set(candidate_groups) != set(CODE_BY_ID):
        raise RuntimeError(f"Candidate mismatch: {sorted(candidate_groups)}")

    document = load(DATA)
    # Idempotent rebuild: replace only records previously created by this
    # importer and preserve the complete Rebuild roster byte-for-byte in data.
    current = [hero for hero in document["heroes"] if hero.get("sourceRegion") != "international"]
    existing_ids = {int(hero["id"]) for hero in current}
    existing_codes = {hero["code"] for hero in current}
    cache: dict[str, list[dict]] = {}
    imported = []
    audit = []

    all_names = {int(hero["id"]): hero["name"] for hero in current}
    all_names.update({int(row["ID"]): row.get("Name") or str(row["ID"]) for row in only_rows})
    all_names[1261449522] = "Saber"
    all_names.update({only_id: HERO_LOCALIZATION[only_id][0] for only_id in CODE_BY_ID})

    for only_id, code in CODE_BY_ID.items():
        if only_id in existing_ids or code in existing_codes:
            continue
        group = candidate_groups[only_id]
        leaders = sorted({int(row.get("Leader") or 0) for row in group})
        canonical = next((row for row in group if int(row.get("Leader") or 0) == 15 and int(row.get("Quality") or 0) == 6 and int(row.get("StarLevel") or 0) == 1), None)
        if canonical is None:
            canonical = next(row for row in group if int(row.get("Leader") or 0) == 15)
        identity = identity_rows[only_id]
        # The identity/master row fixes Leader=15. Leader=16 rows share the
        # same OnlyId/model/skills and are an SSR progression state, so they
        # must not become a duplicate hero.
        rarity = "SR"

        model_source = ASSETS / "res" / "card" / "role" / code
        model_target = HERO_ASSETS / code / "model"
        model_target.mkdir(parents=True, exist_ok=True)
        textures = []
        for source in sorted(model_source.iterdir()):
            target = model_target / source.name
            if source.suffix.lower() == ".png":
                textures.append(export_png(source, target))
            elif source.suffix.lower() in {".skel", ".atlas"}:
                shutil.copy2(source, target)

        skill_ids = []
        for value in (canonical.get("Skills") or []) + (canonical.get("SkillsEx") or []):
            value = int(value)
            if value and value not in skill_ids:
                skill_ids.append(value)
        hero_skills = []
        effects_by_action = {}
        for index, skill_id in enumerate(skill_ids, 1):
            row = skill_by_id[skill_id]
            localized_name, localized_desc = SKILL_LOCALIZATION[skill_id]
            icon_source = ASSETS / str(row.get("SkillIcon") or "").replace("/", "\\")
            icon = ""
            if icon_source.is_file():
                icon_target = SKILL_IMAGES / icon_source.name
                export_png(icon_source, icon_target)
                icon = web_path(icon_target)
            effects = effect_rows(row, cache)
            effects_by_action[f"skill{index}"] = effects
            hero_skills.append({
                "id": skill_id, "name": localized_name, "description": localized_desc,
                "icon": icon, "unlock": "", "type": row.get("Type"),
                "skillType": row.get("SkillType"), "skillTypeS": row.get("SkillTypeS"),
                "source": f"SkillRes:{skill_id}", "sourceText": {"name": row.get("Name", ""), "description": row.get("Desc", "")},
                "effects": effects, "vfxStatus": "PARTIAL_VFX",
            })

        harem = [row for row in harem_rows if int(row.get("CardID") or 0) == only_id and int(row.get("Level") or 0) == 1 and int(row.get("MengWang") or 0) == 0]
        harem.sort(key=lambda row: (0 if int(row.get("ShangXian") or 0) == 1 else 1, int(row.get("ID") or 0)))
        activation = harem[0] if harem else {}
        patch_id = int(activation.get("PatchID") or 0)
        patch_item = item_by_id.get(patch_id, {})

        bonds = []
        for lucky in lucky_rows:
            owners = [int(value) for value in lucky.get("ID0", [])]
            if only_id not in owners or int(lucky.get("Activated") or 0) != 1:
                continue
            required = []
            for field in ("ID1", "ID2", "ID3", "ID4", "ID5"):
                required.extend(int(value) for value in lucky.get(field, []) if int(value))
            required = list(dict.fromkeys(required))
            names = [all_names.get(value, str(value)) for value in required]
            # Lucky names are title-like proper phrases; preserve them when a
            # trustworthy Vietnamese equivalent is unavailable, while the
            # effect and activation condition remain fully localized.
            source_bond_name = lucky.get("Name") or ""
            bonds.append({
                "id": int(lucky["ID"]), "name": BOND_NAME_LOCALIZATION.get(source_bond_name, "Duyên phận"),
                "description": rate_text(lucky) or (lucky.get("Desc") or ""),
                "condition": "Tướng yêu cầu: " + ", ".join(names) if names else "",
                "source": f"LuckySkillRes:{lucky['ID']}", "sourceName": source_bond_name,
            })

        name, aliases, description = HERO_LOCALIZATION[only_id]
        weapons = []
        for weapon in sorted((row for row in weapon_rows if int(row.get("OnlyID") or 0) == only_id), key=lambda row: int(row.get("WeaponColor") or 0)):
            tier = int(weapon.get("WeaponColor") or 0)
            weapons.append({
                "id": int(weapon["ID"]), "name": f"{WEAPON_TIER_LOCALIZATION.get(tier, 'Vũ Khí')} · {name}",
                "tier": tier, "skin": weapon.get("Icon") or "", "gold": int(weapon.get("Gold") or 0),
                "attack": weapon.get("Attack") or 0, "HP": weapon.get("HP") or 0,
                "skillBeforeId": int(weapon.get("SkillBeforeID") or 0), "skillAfterId": int(weapon.get("SkillAfterID") or 0),
                "source": f"T_WeaponRes:{weapon['ID']}", "sourceName": weapon.get("Name") or "",
            })
        awakening_source = next((row for row in awakening_rows if int(row.get("CardId1") or 0) == only_id), None)
        awakening = None
        if awakening_source:
            source_title = awakening_source.get("SHOWNAME") or ""
            awakening = {
                "id": int(awakening_source.get("CardId2") or 0),
                "name": AWAKENING_LOCALIZATION.get(source_title, source_title),
                "gold": int(awakening_source.get("NeedGold") or 0),
                "itemIds": [int(value) for value in awakening_source.get("ItemIDs", [])],
                "itemCounts": [int(value) for value in awakening_source.get("ItemCounts", [])],
                "source": f"juexingRes:{only_id}", "sourceName": source_title,
            }
        hero_show = next((row for row in hero_show_rows if int(row.get("HeroOnlyID") or 0) == only_id), None)
        manifest_path = HERO_ASSETS / code / "manifest.json"
        model_meta = {
            "skeleton": web_path(model_target / f"{code}.skel"),
            "atlas": web_path(model_target / f"{code}.atlas"),
            "textures": [entry["path"] for entry in textures],
            "source": str(model_source),
        }
        manifest = {
            "code": code, "heroCode": code, "heroId": only_id,
            "renderer": "native-windows-offline-spine-2.1.27+cocos-armature",
            "webStatus": "MODEL_PACKAGED_RENDER_PENDING", "effectParity": "PARTIAL_VFX",
            "model": model_meta, "effects": effects_by_action,
            "skillVfxStatus": {action: "PARTIAL_VFX" for action in effects_by_action}, "visuals": {},
            "rarityEvidence": {
                "identityLeader": int(identity.get("Leader") or 0), "SSRCard": 1,
                "progressionLeaders": leaders, "deduplicatedBy": "OnlyId",
                "resolution": "SR identity; Leader=16 rows are the same identity's SSR progression state",
            },
            "notes": [
                "Original international model and all discoverable referenced skill resources are packaged.",
                "No generic CSS aura, glow or particle is used as skill VFX.",
                "Skill actions remain PARTIAL_VFX until character, projectile, particle, impact and timing are all composited.",
            ],
        }
        save(manifest_path, manifest)

        stats = {field: canonical.get(field) for field in ("HP", "Attack", "Speed", "Crit", "Dodge", "WuFang", "MoFang") if canonical.get(field) is not None}
        status = "ACTIVE" if int(activation.get("ShangXian") or 0) == 1 else "HIDDEN"
        imported.append({
            "id": only_id, "code": code, "name": name, "aliases": aliases,
            "rarity": rarity, "status": status, "image": f"./img/heros/{code}.png",
            "faction": FACTIONS.get(int(canonical.get("CardNation") or 0), ""),
            "role": ROLE_BY_LOCATION.get(identity.get("Location") or "", ROLES.get(int(canonical.get("Occupation") or 0), "")),
            "stars": int(identity.get("StarLevel") or 0), "description": description,
            "stats": stats, "skills": hero_skills, "bonds": bonds,
            "obtain": ([{
                "name": "Kích hoạt bằng mảnh",
                "description": f"Cần {int(activation.get('PatchCount') or 0)} × Mảnh {name} và {int(activation.get('GoldCost') or 0):,} vàng.".replace(",", "."),
                "source": f"HaremRes:{activation.get('ID', 0)} + ItemRes:{patch_id}",
                "sourceItemName": patch_item.get("Name", ""),
            }] if activation else []) + ([{
                "name": "Nguồn sự kiện",
                "description": "Siêu nạp, Gacha và sự kiện.",
                "source": f"HeroShowRes:{hero_show['ID']}",
            }] if hero_show and "Acquire From: Super Recharge,Gasha,Event." in (hero_show.get("HeroDes") or "") else []),
            "progression": {"weaponSkins": weapons, "awakening": awakening},
            "animation": {"enabled": False, "renderer": manifest["renderer"], "manifest": web_path(manifest_path), "webStatus": "RENDER_PENDING"},
            "visual": {"enabled": False, "manifest": web_path(manifest_path), "type": "prerendered-original", "status": "RENDER_PENDING"},
            "sourceRegion": "international",
            "source": "CardRes + T_OnlyTableRes + HaremRes + SkillRes + LuckySkillRes + ItemRes",
            "evidence": {
                "cardId": int(canonical["ID"]), "onlyId": only_id, "fragmentId": patch_id,
                "identityLeader": int(identity.get("Leader") or 0), "SSRCard": int(canonical.get("SSRCard") or 0),
                "progressionLeaders": leaders, "qualityRows": len(group), "model": str(model_source / f"{code}.skel"),
            },
        })
        audit.append({
            "onlyId": only_id, "code": code, "sourceName": canonical.get("Name"), "name": name,
            "rarity": rarity, "leaders": leaders, "rows": len(group), "skills": skill_ids,
            "active": status, "modelTextures": [entry["path"] for entry in textures],
        })

    combined = current + imported
    if len({int(hero["id"]) for hero in combined}) != len(combined):
        raise RuntimeError("Duplicate OnlyId after merge")
    if len({hero["code"] for hero in combined}) != len(combined):
        raise RuntimeError("Duplicate code after merge")
    priority = {rarity: index for index, rarity in enumerate(reversed(RARITY_ORDER), 1)}
    combined.sort(key=lambda hero: (-priority.get(hero.get("rarity"), 0), int(hero["id"])))
    counts = Counter(hero["rarity"] for hero in combined)
    document["heroes"] = combined
    document["meta"]["totalHeroes"] = len(combined)
    document["meta"]["rarities"] = {rarity: counts[rarity] for rarity in RARITY_ORDER if counts[rarity]}
    document["meta"]["rarityOrder"] = RARITY_ORDER
    document["meta"]["generatedAt"] = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
    document["meta"]["source"] = "MangaToiThuong-Rebuild + MangaAllstar international"
    document["meta"]["playableRule"] = (
        "Rebuild roster preserved; International: CardRes.ActorType=0, Visible=1, SSRCard=1, "
        "T_OnlyTableRes identity Leader=15; deduplicate OnlyId; HaremRes.ShangXian retained as status"
    )
    document["meta"]["internationalImport"] = {
        "SSR": 0, "SR": len(imported), "deduplicatedBy": "OnlyId",
        "identityRule": "SSRCard=1 and T_OnlyTableRes.Leader=15 => SR; Leader=16 rows for the same OnlyId are progression, not a second hero",
    }
    save(DATA, document)
    save(WEB / "build" / "international-import" / "audit.json", {
        "generatedAt": document["meta"]["generatedAt"], "imported": audit,
        "counts": {"SSR": 0, "SR": len(imported), "total": len(combined)},
    })
    print(json.dumps({"imported": len(imported), "total": len(combined), "rarities": document["meta"]["rarities"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
