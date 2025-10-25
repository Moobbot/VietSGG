# -*- coding: utf-8 -*-
"""standardize_relationships_vi.py

Tiện ích chuẩn hóa/canonical hóa các bộ ba (subject–predicate–object)
quan hệ thị giác tiếng Việt và chú thích kiểu Visual Genome theo từng ảnh.

Module này cung cấp:
- từ điển RULES với các quy tắc và heuristic chuẩn hóa,
- các hàm trợ giúp để chuẩn hóa nhãn đối tượng và vị ngữ,
- bộ xử lý cho danh sách bộ ba dạng "simple" và dữ liệu per-image dạng "vg-like",
- một CLI qua hàm `standardize_file`.

Mã được viết theo hướng bảo thủ: không thay đổi object id hay bounding box,
chỉ chuẩn hóa chuỗi văn bản của nhãn và vị ngữ quan hệ.
"""

from typing import List, Dict, Any, Tuple, Optional
import json, re
from pathlib import Path

RULES = {
    "synonyms_obj": {
        "giày thể thao": "giày",
        "giày sneaker": "giày",
        "giày tennis": "giày",
        "đồ thể thao": "trang phục thể thao",
        "đồng phục thể thao": "trang phục thể thao",
        "sân bóng": "sân bóng đá",
    },
    "wear_targets": [
        "áo",
        "áo đấu",
        "áo thi đấu",
        "đồng phục",
        "trang phục",
        "trang phục thể thao",
        "quần áo",
    ],
    "shoe_targets": ["giày", "giày thể thao", "giày bóng đá", "giày tennis"],
    "place_targets": [
        "sân bóng đá",
        "sân tennis",
        "sân bóng chày",
        "khung thành",
        "lưới",
        "sân",
    ],
    "implausible_patterns": [
        [".*", "gần", "áo( đấu)?|đồng phục|trang phục( thể thao)?"],
        ["bóng tennis", "trên", "cầu thủ"],
        ["găng bóng chày", "trên", "sân bóng đá"],
        ["sân bóng chày", "trên", "sân bóng đá"],
    ],
    "predicate_replacements": {"đánh vung": "vung", "vung vợt vào": "vung"},
}


def _norm_lower(x: Optional[str]) -> str:
    """Chuẩn hóa chuỗi về chữ thường đã bỏ khoảng trắng đầu/cuối.

    Tham số:
        x: chuỗi đầu vào (có thể là None).

    Trả về:
        Chuỗi chữ thường đã được strip; trả về chuỗi rỗng nếu đầu vào không hợp lệ.
    """
    return (x or "").strip().lower()


def normalize_object_label(label: str) -> str:
    """Chuẩn hóa nhãn đối tượng dựa trên RULES['synonyms_obj'].

    Hàm sẽ chuyển về chữ thường, bỏ khoảng trắng, sau đó thay thế các từ đồng
    nghĩa đã biết về dạng chuẩn (ví dụ: 'giày sneaker' -> 'giày').

    Tham số:
        label: chuỗi nhãn đối tượng thô.

    Trả về:
        Nhãn đối tượng đã chuẩn hóa (chữ thường, thay thế đồng nghĩa phổ biến).
    """
    lab = _norm_lower(label)
    return RULES["synonyms_obj"].get(lab, lab)


def fix_predicate(predicate: str, subj: str, obj: str) -> str:
    """Áp dụng heuristic để chuẩn hóa vị ngữ (predicate).

    Bước xử lý:
      - đưa predicate và subject về chữ thường;
      - chuẩn hóa nhãn object;
      - áp dụng các quy tắc trong RULES, gồm:
          • thay thế đơn giản RULES['predicate_replacements'];
          • 'đeo' -> 'mặc' khi đối tượng là trang phục; 'đeo' -> 'mang' khi là giày;
          • điều chỉnh không gian khi chủ ngữ là 'bóng' và đối tượng là địa điểm
            (ví dụ: 'trên sân' -> 'nằm trên').

    Tham số:
        predicate: chuỗi vị ngữ gốc.
        subj: nhãn chủ ngữ (có thể đã chuẩn hóa hoặc chưa).
        obj: nhãn tân ngữ (sẽ được chuẩn hóa bên trong hàm).

    Trả về:
        Chuỗi vị ngữ đã được chuẩn hóa.
    """
    p = _norm_lower(predicate)
    s = _norm_lower(subj)
    o = normalize_object_label(obj)

    if p in RULES["predicate_replacements"]:
        p = RULES["predicate_replacements"][p]

    if p == "đeo":
        # Nếu tân ngữ là trang phục → dùng 'mặc'; nếu là giày → dùng 'mang'.
        if any(o == t for t in RULES["wear_targets"]):
            return "mặc"
        if any(o == t for t in RULES["shoe_targets"]):
            return "mang"

    # 'bắt' + găng → 'đeo'
    if p == "bắt" and o.startswith("găng"):
        return "đeo"

    # Điều chỉnh không gian khi chủ ngữ là 'bóng'
    if p in {"trên sân", "trên"} and re.search(r"bóng( đá| rổ| tennis)?", s):
        if o in RULES["place_targets"]:
            return "nằm trên"
    if p in {"trong"} and (o == "khung thành"):
        return "nằm trong"
    if p in {"trong"} and o in RULES["place_targets"]:
        return "ở trong"

    return p


def drop_implausible(subj: str, predicate: str, obj: str) -> bool:
    """Trả về True nếu bộ ba khớp với một mẫu phi lý (implausible).

    RULES['implausible_patterns'] chứa các bộ (subject_regex, predicate_exact,
    object_regex). Nếu predicate khớp chính xác và cả subject/object cùng khớp
    full-match regex tương ứng, quan hệ được coi là phi lý và sẽ bị loại.
    """
    s = _norm_lower(subj)
    p = _norm_lower(predicate)
    o = _norm_lower(obj)
    for s_rx, pred, o_rx in RULES["implausible_patterns"]:
        if p == pred and re.fullmatch(s_rx, s) and re.fullmatch(o_rx, o):
            return True
    return False


def standardize_triplet(
    subj: str, pred: str, obj: str
) -> Optional[Tuple[str, str, str]]:
    """Chuẩn hóa một bộ ba (subject, predicate, object).

    Các bước:
      1. đưa subject về chữ thường/strip;
      2. chuẩn hóa nhãn object;
      3. áp dụng heuristic cho predicate;
      4. lọc bỏ các quan hệ phi lý;
      5. hậu xử lý nhỏ (ví dụ: 'trên sân' -> 'nằm trên').

    Trả về:
        Bộ (subject, predicate, object) đã chuẩn hóa hoặc None nếu bị loại.
    """
    subj_n = _norm_lower(subj)
    obj_n = normalize_object_label(obj)
    pred_n = fix_predicate(pred, subj_n, obj_n)

    if drop_implausible(subj_n, pred_n, obj_n):
        return None

    if pred_n == "trên sân":
        pred_n = "nằm trên"

    # Giữ lại gợi ý chuẩn hóa cho 'quả bóng' để có thể bật lại khi cần.
    # if subj_n.startswith("quả bóng "):
    #     subj_n = subj_n.replace("quả bóng ", "bóng ", 1)

    return subj_n, pred_n, obj_n


def process_simple_triplets(data: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Xử lý danh sách các bộ ba ở dạng đơn giản (simple triplets).

    Hỗ trợ các khóa ('subject'|'subj'), ('predicate'|'pred'), ('object'|'obj').
    Trả về danh sách bộ ba đã chuẩn hóa với các khóa 'subject','predicate','object'.
    Những quan hệ phi lý sẽ bị loại bỏ.
    """
    out: List[Dict[str, str]] = []
    for rel in data:
        subj = rel.get("subject") or rel.get("subj") or ""
        pred = rel.get("predicate") or rel.get("pred") or ""
        obj = rel.get("object") or rel.get("obj") or ""
        std = standardize_triplet(subj, pred, obj)
        if std:
            s, p, o = std
            out.append({"subject": s, "predicate": p, "object": o})
    return out


def process_vg_like(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Xử lý dữ liệu chú thích dạng Visual Genome (theo từng ảnh).

    Mỗi phần tử đầu vào là một dict có 'objects' và 'relationships'. Mục object
    cần có 'object_id' và 'names'. Hàm sẽ chuẩn hóa tên object tại chỗ, sau đó
    chuẩn hóa từng quan hệ bằng cách tra subject/object theo id. Kết quả trả về
    là danh sách, mỗi phần tử ứng với một ảnh với các trường: image_id, objects
    (đã chuẩn hóa tên), relationships (được giữ lại, predicate có thể đã đổi)
    và danh sách tiện lợi 'triplets' gồm các dict (s,p,o) chuẩn hóa.
    """
    out = []
    for ann in data:
        objects = ann.get("objects", [])
        rels = ann.get("relationships", [])
        id_to_name = {}
        for obj in objects:
            name = (obj.get("names") or [""])[0]
            name = normalize_object_label(name)
            id_to_name[obj.get("object_id")] = name
            obj["names"] = [name]

        triplets = []
        kept = []
        for r in rels:
            s_id = r.get("subject_id")
            o_id = r.get("object_id")
            p = r.get("predicate", "")
            s_name = id_to_name.get(s_id, "")
            o_name = id_to_name.get(o_id, "")
            std = standardize_triplet(s_name, p, o_name)
            if std:
                s, p2, o = std
                triplets.append({"subject": s, "predicate": p2, "object": o})
                r["predicate"] = p2
                kept.append(r)

        out.append(
            {
                "image_id": ann.get("image_id"),
                "objects": objects,
                "relationships": kept,
                "triplets": triplets,
            }
        )
    return out


def detect_format(data: Any) -> str:
    """Nhận diện định dạng đầu vào: 'vg' (per-image) hay 'simple'.

    Trả về 'vg' nếu phần tử là dict có 'objects' và 'relationships';
    trả về 'simple' nếu là danh sách các dict bộ ba; ngược lại 'unknown'.
    """
    if isinstance(data, list) and data:
        item = data[0]
        if isinstance(item, dict):
            if "objects" in item and "relationships" in item:
                return "vg"
            if "subject" in item and "predicate" in item and "object" in item:
                return "simple"
    return "unknown"


def standardize_file(input_path: str, output_path: str) -> dict:
    """Đọc JSON đầu vào, chuẩn hóa quan hệ và ghi JSON đầu ra.

    Hàm cố gắng tự động nhận diện định dạng. Hỗ trợ:
        - danh sách bộ ba đơn giản (mỗi dict có subject/predicate/object)
        - danh sách chú thích per-image kiểu VG (mỗi phần tử có 'objects' và
            'relationships')
        - dict có khóa 'annotations' chứa danh sách VG-like

    Trả về một dict metadata nhỏ gồm đường dẫn input/output, định dạng phát hiện
    và số lượng phần tử đầu ra.
    """
    p_in = Path(input_path)
    p_out = Path(output_path)
    data = json.loads(Path(p_in).read_text(encoding="utf-8"))

    fmt = detect_format(data)
    if fmt == "simple":
        result = process_simple_triplets(data)
    elif fmt == "vg":
        result = process_vg_like(data)
    else:
        # Một số tập dữ liệu bọc VG-like trong khóa 'annotations' ở mức root.
        if isinstance(data, dict) and "annotations" in data:
            result = process_vg_like(data["annotations"])
        else:
            raise ValueError(
                "Không nhận diện được format input. Hỗ trợ: simple triplets hoặc VG-like per-image."
            )

    p_out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "input": str(p_in),
        "output": str(p_out),
        "detected_format": fmt if fmt != "unknown" else "fallback",
        "num_items": (
            len(result)
            if isinstance(result, list)
            else (len(result.get("annotations", [])) if isinstance(result, dict) else 0)
        ),
    }


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(
        description="Chuẩn hóa hậu kỳ quan hệ thị giác tiếng Việt."
    )
    ap.add_argument("--infile", required=True, help="Đường dẫn JSON input")
    ap.add_argument("--outfile", required=True, help="Đường dẫn JSON output")
    args = ap.parse_args()
    info = standardize_file(args.infile, args.outfile)
    print(json.dumps(info, ensure_ascii=False, indent=2))
