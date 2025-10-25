# -*- coding: utf-8 -*-
"""
drop_extra_fields.py
--------------------
Loại bỏ các 'sân' bị trùng lặp trong từng ảnh VG-like.

Tính năng:
- Hỗ trợ input là list các annotation VG-like hoặc dạng {"annotations": [...]}
- Với mỗi ảnh, nhóm các object theo nhãn sân (mặc định: "sân bóng đá", "sân bóng chày", "sân tennis").
- Nếu một nhãn sân có >1 box, chỉ giữ 1 box đại diện theo tiêu chí:
    * "largest-area" (mặc định): diện tích bbox lớn nhất; nếu bằng nhau, ưu tiên object_id nhỏ hơn.
    * "lowest-y": toạ độ y nhỏ nhất (trên cùng); nếu bằng, rơi về largest-area.
- Xoá mọi relationships trỏ tới các box bị loại.
- Xây lại trường "triplets" để thuận tiện kiểm tra.

Cách dùng:
    python drop_extra_fields.py --infile vg_input.json --outfile vg_output.json
    # đổi tiêu chí chọn đại diện:
    python drop_extra_fields.py --infile vg.json --outfile vg_out.json --policy lowest-y
    # mở rộng danh sách nhãn sân:
    python drop_extra_fields.py --infile vg.json --outfile vg_out.json --field-labels "sân bóng đá,sân bóng chày,sân tennis,sân cầu lông"
"""

import json
import argparse
from pathlib import Path
from typing import Any, Dict, List, Tuple, Iterable

# Tập nhãn sân mặc định; có thể ghi đè qua tham số CLI --field-labels
DEFAULT_FIELD_LABELS = {"sân bóng đá", "sân bóng chày", "sân tennis"}

def _lname(s: str) -> str:
    """Chuẩn hóa chuỗi: strip + lower; an toàn với None."""
    return (s or "").strip().lower()

def _name(o: Dict[str, Any]) -> str:
    """Lấy tên object (phần tử đầu trong mảng 'names') ở dạng thường."""
    return _lname((o.get("names") or [""])[0])

def _bbox(o: Dict[str, Any]) -> Tuple[int,int,int,int]:
    """Trả về bbox (x, y, w, h) dạng số nguyên từ object VG-like."""
    return int(o["x"]), int(o["y"]), int(o["w"]), int(o["h"])

def _area(b: Tuple[int,int,int,int]) -> int:
    """Diện tích hình chữ nhật; chặn âm do dữ liệu lỗi (w/h âm)."""
    x, y, w, h = b
    return max(0, w) * max(0, h)

def _choose_representative(objs: List[Dict[str, Any]], policy: str = "largest-area") -> Dict[str, Any]:
    """
    Chọn 1 box đại diện trong nhóm cùng nhãn sân theo 'policy':
    - 'largest-area' (mặc định): diện tích bbox lớn nhất; nếu hòa, ưu tiên object_id nhỏ hơn.
    - 'lowest-y': toạ độ y nhỏ nhất (box ở "trên cùng"); nếu hòa, rơi về largest-area.
    """
    assert objs, "Empty group"
    if len(objs) == 1:
        return objs[0]

    if policy == "lowest-y":
        # y nhỏ nhất (trên cùng) ưu tiên; nếu hòa, rơi về largest-area
        best = None
        for o in objs:
            x, y, w, h = _bbox(o)
            # score gồm 3 phần: (y tăng dần, area giảm dần, id tăng dần)
            # => y nhỏ hơn tốt hơn; area lớn hơn tốt hơn (đặt dấu -); id nhỏ hơn tốt hơn
            score = (y, -_area((x,y,w,h)), o.get("object_id", 10**12))
            if best is None or score < best[0]:
                best = (score, o)
        return best[1]

    # default: largest-area
    best = None
    for o in objs:
        x, y, w, h = _bbox(o)
        # area lớn hơn -> score nhỏ hơn; nếu hòa, object_id nhỏ hơn thắng
        score = (-_area((x,y,w,h)), o.get("object_id", 10**12))
        if best is None or score < best[0]:
            best = (score, o)
    return best[1]

def _rebuild_triplets(objs: List[Dict[str, Any]], rels: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Sinh triplets chữ (subject, predicate, object) cho tiện debug/phân tích."""
    id2name = {o.get("object_id"): _name(o) for o in objs}
    triplets = []
    for r in rels:
        sid = r.get("subject_id")
        oid = r.get("object_id")
        s = id2name.get(sid, "")
        o = id2name.get(oid, "")
        p = r.get("predicate", "")
        if s and o:
            triplets.append({"subject": s, "predicate": p, "object": o})
    return triplets

def drop_extra_fields_in_image(ann: Dict[str, Any], field_labels: Iterable[str], policy: str = "largest-area") -> Dict[str, Any]:
    """
    Giữ tối đa 1 object cho mỗi loại 'sân' (sân bóng đá / sân bóng chày / sân tennis).
    Tiêu chí chọn: diện tích bbox lớn nhất (hoặc lowest-y). Loại bỏ các 'sân' còn lại, đồng thời
    xoá quan hệ liên quan và dựng lại triplets.
    
    Tham số:
    - ann: một annotation VG-like (có 'objects' và 'relationships').
    - field_labels: tập nhãn sân cần chuẩn hoá; sẽ được lowercase để so khớp.
    - policy: 'largest-area' | 'lowest-y' (xem _choose_representative).
    """
    objs: List[Dict[str, Any]] = ann.get("objects", []) or []
    rels: List[Dict[str, Any]] = ann.get("relationships", []) or []

    field_labels = {_lname(x) for x in field_labels}
    # Gom object theo từng nhãn sân
    by_field: Dict[str, List[Dict[str, Any]]] = {}
    for o in objs:
        n = _name(o)
        if n in field_labels:
            by_field.setdefault(n, []).append(o)

    drop_ids = set()
    for label, group in by_field.items():
        if len(group) <= 1:
            continue
        # Chọn một đại diện theo policy; các box còn lại cùng nhãn sẽ bị drop
        rep = _choose_representative(group, policy=policy)
        rep_id = rep.get("object_id")
        for o in group:
            if o.get("object_id") != rep_id:
                drop_ids.add(o.get("object_id"))

    if drop_ids:
        # Loại object thừa và mọi relationship trỏ đến chúng
        objs = [o for o in objs if o.get("object_id") not in drop_ids]
        rels = [r for r in rels if r.get("subject_id") not in drop_ids and r.get("object_id") not in drop_ids]

    ann["objects"] = objs
    ann["relationships"] = rels
    ann["triplets"] = _rebuild_triplets(objs, rels)
    return ann

def _detect_format(data: Any) -> str:
    """Nhận diện định dạng input: 'vg' (list) hoặc 'vg_wrapped' (dict có 'annotations')."""
    if isinstance(data, list) and data and isinstance(data[0], dict) and "objects" in data[0] and "relationships" in data[0]:
        return "vg"
    if isinstance(data, dict) and "annotations" in data:
        return "vg_wrapped"
    return "unknown"

def process_data(data: Any, field_labels: Iterable[str], policy: str) -> Any:
    """Điều phối xử lý theo định dạng; trả về dữ liệu cùng cấu trúc với đầu vào."""
    fmt = _detect_format(data)
    if fmt == "vg":
        return [drop_extra_fields_in_image(ann, field_labels, policy) for ann in data]
    if fmt == "vg_wrapped":
        anns = data["annotations"]
        data["annotations"] = [drop_extra_fields_in_image(ann, field_labels, policy) for ann in anns]
        return data
    raise ValueError("Unsupported format. Expect list of VG-like items or dict with 'annotations'.")

def main():
    """CLI: đọc infile, xử lý loại bỏ sân trùng lặp, ghi outfile."""
    ap = argparse.ArgumentParser(description="Drop duplicated field objects per image (VG-like).")
    ap.add_argument("--infile", required=True, help="Đường dẫn JSON đầu vào (VG-like list hoặc {'annotations':[...]})")
    ap.add_argument("--outfile", required=True, help="Đường dẫn JSON đầu ra")
    ap.add_argument("--field-labels", default="sân bóng đá,sân bóng chày,sân tennis",
                    help="Danh sách nhãn sân, phân tách bằng dấu phẩy")
    ap.add_argument("--policy", choices=["largest-area", "lowest-y"], default="largest-area",
                    help="Tiêu chí chọn đại diện khi có nhiều sân cùng nhãn")
    args = ap.parse_args()

    field_labels = [s.strip() for s in args.field_labels.split(",") if s.strip()]
    raw = json.loads(Path(args.infile).read_text(encoding="utf-8"))
    result = process_data(raw, field_labels, args.policy)
    Path(args.outfile).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
