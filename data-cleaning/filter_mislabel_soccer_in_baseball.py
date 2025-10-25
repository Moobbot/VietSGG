# -*- coding: utf-8 -*-
"""
filter_mislabel_soccer_in_baseball.py
--------------------
Lọc 'bóng/quả bóng đá' bị gán nhầm trong bối cảnh bóng chày/tennis.

Quy tắc:
- Định nghĩa baseball/tennis-context: ảnh có 'sân bóng chày' hoặc 'sân tennis' hoặc có vật thể trong BASEBALL_SET (bao gồm cả đồ tennis) và KHÔNG có 'sân bóng đá'.
- Khi ở baseball/tennis-context, xoá các object có nhãn 'bóng đá' hoặc 'quả bóng đá'.
- Tuỳ chọn chặt hơn với --require-overlap: chỉ xoá khi bóng đá chồng lấn (IoU >= --iou-conflict)
    với ít nhất một bóng chày ('bóng chày'/'quả bóng chày').

Hỗ trợ định dạng input:
- List VG-like: mỗi phần tử có 'objects' và 'relationships'.
- Dict dạng {"annotations": [...]} với mỗi phần tử như trên.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
import argparse

# ====== Cấu hình nhãn ======
# Các tín hiệu dùng để nhận diện bối cảnh "không phải soccer" (baseball hoặc tennis)
BASEBALL_SET = {
    "bóng chày",
    "quả bóng chày",
    "gậy bóng chày",
    "găng bóng chày",
    "vợt tennis",
    "quả bóng tennis",
}
SOCCER_BALL_SET = {"bóng đá", "quả bóng đá"}


def lname(s: str) -> str:
    """Chuẩn hóa chuỗi: strip + lower; an toàn với None."""
    return (s or "").strip().lower()


def obj_name(o: Dict[str, Any]) -> str:
    """Tên object ở dạng thường (lấy phần tử đầu của mảng names)."""
    return lname((o.get("names") or [""])[0])


def bbox(o: Dict[str, Any]) -> Tuple[int, int, int, int]:
    """Lấy bbox (x, y, w, h) dạng số nguyên từ object VG-like."""
    return int(o["x"]), int(o["y"]), int(o["w"]), int(o["h"])


def area(x: int, y: int, w: int, h: int) -> int:
    """Diện tích hình chữ nhật; chặn âm do dữ liệu lỗi."""
    return max(0, w) * max(0, h)


def intersect(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> int:
    """Diện tích giao nhau giữa hai bbox (x, y, w, h)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ax1, ay1, ax2, ay2 = ax, ay, ax + aw, ay + ah
    bx1, by1, bx2, by2 = bx, by, bx + bw, by + bh
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    return iw * ih


def iou(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> float:
    """Intersection-over-Union tiêu chuẩn giữa hai bbox."""
    inter = intersect(a, b)
    aa = area(*a)
    bb = area(*b)
    denom = aa + bb - inter
    return (inter / denom) if denom > 0 else 0.0


def detect_format(data: Any) -> str:
    """Nhận diện định dạng input: 'vg' (list) hoặc 'vg_wrapped' (dict có 'annotations')."""
    if (
        isinstance(data, list)
        and data
        and isinstance(data[0], dict)
        and "objects" in data[0]
        and "relationships" in data[0]
    ):
        return "vg"
    if isinstance(data, dict) and "annotations" in data:
        return "vg_wrapped"
    return "unknown"


def is_baseball_tennis_context(names: set) -> bool:
    """
    Phát hiện bối cảnh baseball/tennis:
    - Có 'sân bóng chày' hoặc 'sân tennis', hoặc
    - Có ít nhất một object thuộc BASEBALL_SET (bao gồm đồ baseball/tennis).
    """
    return (
        ("sân bóng chày" in names)
        or ("sân tennis" in names)
        or (len(BASEBALL_SET & names) > 0)
    )


def has_soccer_field(names: set) -> bool:
    """Ảnh có 'sân bóng đá' hay không (để tránh xoá bóng đá trong ngữ cảnh đúng)."""
    return "sân bóng đá" in names


def dedupe_soccer_balls(
    soccer_objs: List[Dict[str, Any]], iou_dup: float
) -> List[Dict[str, Any]]:
    """Gộp trùng bóng đá theo IoU; giữ object có bbox lớn hơn (đại diện nhóm)."""
    if len(soccer_objs) <= 1:
        return soccer_objs
    kept: List[Dict[str, Any]] = []
    used = [False] * len(soccer_objs)
    for i, a in enumerate(soccer_objs):
        if used[i]:
            continue
        group = [i]
        for j, b in enumerate(soccer_objs):
            if j <= i or used[j]:
                continue
            if iou(bbox(a), bbox(b)) >= iou_dup:
                group.append(j)
        # chọn đại diện theo diện tích (lớn hơn)
        rep = max(group, key=lambda idx: area(*bbox(soccer_objs[idx])))
        for idx in group:
            used[idx] = True
        kept.append(soccer_objs[rep])
    return kept


def filter_mislabel_in_one(
    ann: Dict[str, Any],
    iou_dup: float = 0.9,
    iou_conflict: float = 0.0,  # 0 => xoá mọi bóng đá khi baseball-context (không cần chồng lấn)
    require_overlap_with_baseball_ball: bool = False,
) -> Dict[str, Any]:
    """
    Lọc bóng đá bị gán nhầm trong một annotation.

    - Chỉ tác động khi là baseball/tennis-context và KHÔNG có 'sân bóng đá'.
    - Gộp trùng bóng đá bằng ngưỡng IoU iou_dup.
    - Nếu require_overlap_with_baseball_ball=True: chỉ xoá bóng đá chồng lấn với bóng chày
      (nhãn 'bóng chày'/'quả bóng chày') với IoU >= iou_conflict.
    - Ngược lại: xoá toàn bộ bóng đá trong bối cảnh baseball/tennis.
    - Đồng thời loại bỏ các relationships liên quan đến các object bị xoá.
    """
    objs = ann.get("objects", [])
    rels = ann.get("relationships", [])

    # Tập tên hiện có
    names = {obj_name(o) for o in objs}

    # Chỉ xử lý khi là baseball-context hoặc tennis-context và không có sân bóng đá
    if not is_baseball_tennis_context(names) or has_soccer_field(names):
        # không động chạm; nhưng vẫn có thể rebuild triplets cho sạch
        return rebuild_triplets(ann)

    # Tách danh sách bóng đá & bóng chày
    soccer_objs = [o for o in objs if obj_name(o) in SOCCER_BALL_SET]
    baseball_balls = [o for o in objs if obj_name(o) in {"bóng chày", "quả bóng chày"}]

    # Gộp trùng bóng đá trước (tránh xoá trùng lặp)
    soccer_objs = dedupe_soccer_balls(soccer_objs, iou_dup)

    # Xác định id cần drop
    drop_ids = set()
    if require_overlap_with_baseball_ball and baseball_balls:
        # Chỉ drop bóng đá nếu chồng lấn với BẤT KỲ bóng chày nào ≥ iou_conflict
        for s in soccer_objs:
            sb = bbox(s)
            if any(iou(sb, bbox(bb)) >= iou_conflict for bb in baseball_balls):
                drop_ids.add(s.get("object_id"))
    else:
        # Drop toàn bộ bóng đá trong baseball-context (không có sân bóng đá)
        for s in soccer_objs:
            drop_ids.add(s.get("object_id"))

    # Lọc objects/relationships theo drop_ids
    if drop_ids:
        objs = [o for o in objs if o.get("object_id") not in drop_ids]
        rels = [
            r
            for r in rels
            if r.get("subject_id") not in drop_ids
            and r.get("object_id") not in drop_ids
        ]

    ann["objects"] = objs
    ann["relationships"] = rels
    return rebuild_triplets(ann)


def rebuild_triplets(ann: Dict[str, Any]) -> Dict[str, Any]:
    """Sinh triplets chữ (subject, predicate, object) để tiện debug/phân tích."""
    id2name = {o.get("object_id"): obj_name(o) for o in ann.get("objects", [])}
    triplets = []
    for r in ann.get("relationships", []):
        s = id2name.get(r.get("subject_id"), "")
        o = id2name.get(r.get("object_id"), "")
        p = r.get("predicate", "")
        if s and o:
            triplets.append({"subject": s, "predicate": p, "object": o})
    ann["triplets"] = triplets
    return ann


def process(
    data: Any, iou_dup: float, iou_conflict: float, require_overlap: bool
) -> Any:
    """Điều phối xử lý theo định dạng 'vg' hoặc 'vg_wrapped'."""
    fmt = detect_format(data)
    if fmt == "vg":
        return [
            filter_mislabel_in_one(ann, iou_dup, iou_conflict, require_overlap)
            for ann in data
        ]
    if fmt == "vg_wrapped":
        anns = data["annotations"]
        data["annotations"] = [
            filter_mislabel_in_one(ann, iou_dup, iou_conflict, require_overlap)
            for ann in anns
        ]
        return data
    raise ValueError(
        "Unsupported format. Expect list of VG-like items or dict with 'annotations'."
    )


def main():
    """CLI: đọc infile, áp dụng lọc, ghi outfile."""
    ap = argparse.ArgumentParser(
        description="Filter mislabelled soccer balls in baseball-context images."
    )
    ap.add_argument("--infile", required=True)
    ap.add_argument("--outfile", required=True)
    ap.add_argument(
        "--iou-dup",
        type=float,
        default=0.90,
        help="Ngưỡng IoU gộp trùng các bóng đá (mặc định 0.90)",
    )
    ap.add_argument(
        "--iou-conflict",
        type=float,
        default=0.0,
        help="Ngưỡng IoU với bóng chày để coi là chồng lấn (0.0 => không cần chồng lấn)",
    )
    ap.add_argument(
        "--require-overlap",
        action="store_true",
        help="Chỉ xoá bóng đá khi chồng lấn với một bóng chày/tennis (IoU >= iou_conflict)",
    )
    args = ap.parse_args()

    raw = json.loads(Path(args.infile).read_text(encoding="utf-8"))
    result = process(raw, args.iou_dup, args.iou_conflict, args.require_overlap)
    Path(args.outfile).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
