# -*- coding: utf-8 -*-
"""
harmonize_sport_context.py
--------------------
Harmonize nội dung thể thao trong annotation VG:
- Ưu tiên sửa nhãn 'sân bóng đá' thành 'sân bóng chày' nếu phát hiện 'gậy bóng chày'.
- Nếu không có bat nhưng có tín hiệu tennis rõ ràng → đổi sang 'sân tennis'.
- Khi bối cảnh bóng đá chiếm ưu thế → loại hoặc thay nhãn các vật thể bóng chày.
- Có fallback cũ: khi có tín hiệu bóng chày mà không có tín hiệu bóng đá → đổi sân sang bóng chày.
- Tùy chọn chuẩn hóa predicate: 'đeo'→'mặc' (áo/đồng phục), 'đeo'→'mang' (giày).
- Hỗ trợ 2 định dạng: list kiểu VG và dict {'annotations': [...]}.
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List

# Tập tín hiệu bóng đá (soccer) cho biết bối cảnh ảnh mang tính bóng đá
SOCCER_SET = {"bóng đá", "khung thành"}
# Tập tín hiệu bóng chày (baseball) để phát hiện vật thể liên quan bóng chày
BASEBALL_SET = {"bóng chày", "gậy bóng chày", "găng bóng chày"}

# Thêm bộ tín hiệu tennis (chấp nhận cả “quả bóng tennis”)
TENNIS_SET = {"bóng tennis", "quả bóng tennis", "vợt tennis", "sân tennis"}

# Bản đồ thay nhãn khi strategy='relabel' trong bối cảnh bóng đá trội (hiện để trống)
RELABEL_MAP = {}


def must_convert_field_to_baseball(names: set) -> bool:
    """
    Ưu tiên cao nhất:
    - Nếu trong cùng ảnh có cả 'sân bóng đá' và 'gậy bóng chày' → ép đổi sân thành 'sân bóng chày'.
    """
    # Ưu tiên cao nhất: chỉ cần có gậy bóng chày + sân bóng đá là ép về sân bóng chày
    return ("sân bóng đá" in names) and ("gậy bóng chày" in names)


def must_convert_field_to_tennis(names: set) -> bool:
    """
    Ưu tiên tiếp theo (khi không có bat):
    - Nếu có 'sân bóng đá' và đồng thời có bất kỳ tín hiệu TENNIS_SET → đổi sang 'sân tennis'.
    """
    # Nếu có sân bóng đá và có tín hiệu tennis rõ ràng -> ép về sân tennis
    return ("sân bóng đá" in names) and (len(TENNIS_SET & names) > 0)


def decide_soccer_dominant(names: set) -> bool:
    """
    Xác định bối cảnh bóng đá chiếm ưu thế:
    - Có 'sân bóng đá' và có ít nhất 1 tín hiệu soccer.
    - Không có tín hiệu baseball.
    """
    has_soccer_field = "sân bóng đá" in names
    has_soccer_signal = len(SOCCER_SET & names) > 0
    has_baseball_signal = len(BASEBALL_SET & names) > 0
    return has_soccer_field and has_soccer_signal and not has_baseball_signal


def need_convert_field_to_baseball(names: set) -> bool:
    """
    Fallback cũ:
    - Có 'sân bóng đá' và có tín hiệu baseball nhưng không có tín hiệu soccer → đổi sân thành 'sân bóng chày'.
    """
    # Quy tắc cũ (fallback): có dấu hiệu bóng chày, không có soccer signal → đổi sân
    has_soccer_field = "sân bóng đá" in names
    has_soccer_signal = len(SOCCER_SET & names) > 0
    has_baseball_signal = len(BASEBALL_SET & names) > 0
    return has_soccer_field and has_baseball_signal and not has_soccer_signal


def _lname(x: str) -> str:
    """Chuẩn hóa chuỗi: strip + lower, chống None."""
    return (x or "").strip().lower()


def _obj_name(obj: Dict[str, Any]) -> str:
    """Lấy tên đối tượng (names[0]) ở dạng thường, an toàn khi thiếu."""
    return _lname((obj.get("names") or [""])[0])


def _fix_predicate(p: str, obj_label: str) -> str:
    """
    Chuẩn hóa predicate theo object:
    - 'đeo' + (áo/đồng phục/...) → 'mặc'
    - 'đeo' + (giày...) → 'mang'
    Các trường hợp khác giữ nguyên.
    """
    p = _lname(p)
    o = _lname(obj_label)
    if p == "đeo":
        if o in {
            "áo",
            "áo đấu",
            "áo thi đấu",
            "đồng phục",
            "trang phục",
            "trang phục thể thao",
            "quần áo",
        }:
            return "mặc"
        if o.startswith("giày"):
            return "mang"
    return p


def detect_format(data: Any) -> str:
    """
    Nhận diện định dạng input:
    - 'vg': list item có keys 'objects' và 'relationships'
    - 'vg_wrapped': dict có key 'annotations' là list tương tự VG
    - 'unknown': không hỗ trợ
    """
    if isinstance(data, list) and data:
        item = data[0]
        if isinstance(item, dict) and "objects" in item and "relationships" in item:
            return "vg"
    if isinstance(data, dict) and "annotations" in data:
        return "vg_wrapped"
    return "unknown"


# --- QUY TẮC MỚI: nếu có "gậy bóng chày" và có "sân bóng đá" -> ép đổi sân thành "sân bóng chày"
def must_convert_field_to_baseball(names: set) -> bool:
    return ("sân bóng đá" in names) and ("gậy bóng chày" in names)


def decide_soccer_dominant(names: set) -> bool:
    has_soccer_field = "sân bóng đá" in names
    has_soccer_signal = len(SOCCER_SET & names) > 0
    has_baseball_signal = len(BASEBALL_SET & names) > 0
    return has_soccer_field and has_soccer_signal and not has_baseball_signal


# (giữ lại rule cũ cho các ca không có "gậy bóng chày")
def need_convert_field_to_baseball(names: set) -> bool:
    has_soccer_field = "sân bóng đá" in names
    has_soccer_signal = len(SOCCER_SET & names) > 0
    has_baseball_signal = len(BASEBALL_SET & names) > 0
    return has_soccer_field and has_baseball_signal and not has_soccer_signal


def harmonize_one(
    ann: Dict[str, Any], strategy: str = "drop", also_fix_predicates: bool = False
) -> Dict[str, Any]:
    """
        Chuẩn hóa một annotation theo các bước:
        Bước 0 (ưu tiên đổi sân):
            0.1 Nếu có 'gậy bóng chày' + 'sân bóng đá' → đổi 'sân bóng đá' thành 'sân bóng chày'.
            0.2 Nếu không có bat nhưng có tín hiệu TENNIS_SET → đổi 'sân bóng đá' thành 'sân tennis'.
        Bước 1 (bóng đá trội):
            - strategy='drop': loại các object thuộc BASEBALL_SET và các quan hệ liên quan.
            - strategy='relabel': thay nhãn theo RELABEL_MAP (nếu có).
        Bước 2 (fallback cũ):
            - Nếu có tín hiệu baseball và không có tín hiệu soccer → đổi sân thành 'sân bóng chày'.
        Bước 3 (tùy chọn):
            - also_fix_predicates=True: chuẩn hóa predicate theo đối tượng đích.
        Bước 4:
            - Sinh triplets chữ (subject, predicate, object) từ relationships.
    """
    image_id = ann.get("image_id")
    objs = ann.get("objects", [])
    rels = ann.get("relationships", [])

    id2name = {o.get("object_id"): _obj_name(o) for o in objs}
    names = set(id2name.values())

    # (0) ƯU TIÊN ĐỔI SÂN:
    # 0.1 Baseball bat hiện diện -> ép sân bóng chày
    if must_convert_field_to_baseball(names):
        changed_count = 0
        for o in objs:
            if _obj_name(o) == "sân bóng đá":
                o["names"] = ["sân bóng chày"]
                changed_count += 1
        if changed_count:
            print(f"[harmonize] image_id={image_id} -> field converted: 'sân bóng đá' -> 'sân bóng chày' (x{changed_count})")
        id2name = {o.get("object_id"): _obj_name(o) for o in objs}
        names = set(id2name.values())
    # 0.2 Nếu không có bat nhưng có tín hiệu TENNIS -> ép sân tennis
    elif must_convert_field_to_tennis(names):
        changed_count = 0
        for o in objs:
            if _obj_name(o) == "sân bóng đá":
                o["names"] = ["sân tennis"]
                changed_count += 1
        if changed_count:
            print(f"[harmonize] image_id={image_id} -> field converted: 'sân bóng đá' -> 'sân tennis' (x{changed_count})")
        id2name = {o.get("object_id"): _obj_name(o) for o in objs}
        names = set(id2name.values())

    # (1) Phần xử lý bối cảnh bóng đá trội (drop/relabel baseball items)
    if decide_soccer_dominant(names):
        if strategy == "drop":
            drop_ids = {
                o.get("object_id") for o in objs if _obj_name(o) in BASEBALL_SET
            }
            if drop_ids:
                dropped_info = [
                    f"{o.get('object_id')}: {_obj_name(o)}" for o in objs if o.get("object_id") in drop_ids
                ]
            before_rels = len(rels)
            objs = [o for o in objs if o.get("object_id") not in drop_ids]
            rels = [
                r
                for r in rels
                if r.get("subject_id") not in drop_ids
                and r.get("object_id") not in drop_ids
            ]
            removed_rels = before_rels - len(rels)
            if drop_ids:
                print(
                    f"[harmonize] image_id={image_id} -> soccer-dominant: dropped objects: "+
                    ", ".join(dropped_info) + f" | removed_rels={removed_rels}"
                )
        elif strategy == "relabel":
            relabeled = []
            for o in objs:
                n = _obj_name(o)
                if n in RELABEL_MAP:
                    o["names"] = [RELABEL_MAP[n]]
                    relabeled.append((o.get("object_id"), n, RELABEL_MAP[n]))
            if relabeled:
                parts = [f"{oid}: {old}->{new}" for oid, old, new in relabeled]
                print(f"[harmonize] image_id={image_id} -> soccer-dominant: relabeled objects: "+", ".join(parts))

    # (2) Fallback cũ: nếu có baseball signal mà không có soccer signal -> đổi sân sang bóng chày
    id2name = {o.get("object_id"): _obj_name(o) for o in objs}
    names = set(id2name.values())
    if need_convert_field_to_baseball(names):
        changed_count = 0
        for o in objs:
            if _obj_name(o) == "sân bóng đá":
                o["names"] = ["sân bóng chày"]
                changed_count += 1
        if changed_count:
            print(f"[harmonize] image_id={image_id} -> fallback: field converted: 'sân bóng đá' -> 'sân bóng chày' (x{changed_count})")

    # (3) Sửa predicate nếu bật
    if also_fix_predicates:
        id2name = {o.get("object_id"): _obj_name(o) for o in objs}
        fix_cnt = 0
        for r in rels:
            obj_label = id2name.get(r.get("object_id"), "")
            old_p = r.get("predicate", "")
            new_p = _fix_predicate(old_p, obj_label)
            if new_p != old_p:
                fix_cnt += 1
                r["predicate"] = new_p
        if fix_cnt:
            print(f"[harmonize] image_id={image_id} -> predicates fixed: {fix_cnt}")

    # (4) Triplets chữ để tiện debug/phân tích
    id2name = {o.get("object_id"): _obj_name(o) for o in objs}
    triplets = []
    for r in rels:
        s = id2name.get(r.get("subject_id"), "")
        o = id2name.get(r.get("object_id"), "")
        p = r.get("predicate", "")
        if s and o:
            triplets.append({"subject": s, "predicate": p, "object": o})

    ann["objects"] = objs
    ann["relationships"] = rels
    ann["triplets"] = triplets
    return ann


def harmonize(
    data: Any, strategy: str = "drop", also_fix_predicates: bool = False
) -> Any:
    """
    Điều phối xử lý theo định dạng:
    - 'vg': list các item VG-like.
    - 'vg_wrapped': dict chứa 'annotations'.
    """
    fmt = detect_format(data)
    if fmt == "vg":
        return [harmonize_one(ann, strategy, also_fix_predicates) for ann in data]
    if fmt == "vg_wrapped":
        anns = data["annotations"]
        data["annotations"] = [
            harmonize_one(ann, strategy, also_fix_predicates) for ann in anns
        ]
        return data
    raise ValueError(
        "Unsupported format. Expect a list of VG-like items or a dict with 'annotations'."
    )


def main(
    infile: str, outfile: str, strategy: str = "drop", also_fix_predicates: bool = False
):
    """Đọc JSON, harmonize, và ghi ra JSON mới."""
    raw = json.loads(Path(infile).read_text(encoding="utf-8"))
    result = harmonize(raw, strategy=strategy, also_fix_predicates=also_fix_predicates)
    Path(outfile).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    import argparse

    # CLI: chuẩn hóa ngữ cảnh thể thao, ưu tiên đổi sân bóng chày khi có bat
    ap = argparse.ArgumentParser(
        description="Resolve sport-context conflicts (prioritize baseball field if a bat exists)."
    )
    ap.add_argument(
        "--infile",
        required=True,
        help="Input JSON (VG-like list or {'annotations': [...]})",
    )
    ap.add_argument("--outfile", required=True, help="Output JSON")
    ap.add_argument(
        "--strategy",
        choices=["drop", "relabel"],
        default="drop",
        help="Handle baseball items in soccer-dominant scenes",
    )
    ap.add_argument(
        "--also-fix-predicates",
        action="store_true",
        help="Normalize 'đeo'->'mặc' (uniform), 'đeo'->'mang' (shoes)",
    )
    args = ap.parse_args()
    main(
        args.infile,
        args.outfile,
        strategy=args.strategy,
        also_fix_predicates=args.also_fix_predicates,
    )
