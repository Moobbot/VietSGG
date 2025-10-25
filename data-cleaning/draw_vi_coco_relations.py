#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vẽ bbox & quan hệ (tiếng Việt) lên ảnh COCO-Style bằng OpenCV (tránh lỗi font).

Đầu vào JSON (ví dụ relationships_vi_coco_uitvic_test.json):
- Mỗi phần tử gồm:
  { "image_id": int, "objects": [{"object_id": int, "x": int, "y": int, "w": int, "h": int}, ...],
    "relationships": [{"subject_id": int, "predicate": str, "object_id": int}, ...] }

Ảnh COCO có tên dạng 12 chữ số: 000000<image_id>.jpg (ví dụ image_id=7615 -> 000000007615.jpg)

Chú ý tiếng Việt: OpenCV putText không hỗ trợ Unicode hoàn chỉnh. Ta dùng Pillow để vẽ chữ
với font Unicode (Arial/SegoeUI/DejaVu/Noto), sau đó trả ảnh về OpenCV. 

Sử dụng:
  python viz/draw_vi_coco_relations.py output-AI/relationships_vi_coco_uitvic_test.json \
         --images data/coco_uitvic_test --out viz/output-vi

Phụ thuộc: opencv-python, numpy, Pillow
"""
from __future__ import annotations
import os, json, argparse
from typing import Dict, List, Tuple, Optional, Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


# ------------------------- I/O -------------------------
def read_json(path: str):
    """Đọc file JSON với encoding UTF-8 và trả về dữ liệu Python."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(p: str) -> None:
    """Tạo thư mục đích nếu chưa có (an toàn khi tồn tại)."""
    os.makedirs(p, exist_ok=True)


def coco_name_from_id(image_id: int) -> str:
    """Tên file COCO 12 chữ số từ image_id (ví dụ 7615 -> 000000007615.jpg)."""
    return f"{int(image_id):012d}.jpg"


def find_image_path(image_id: int, images_dir: str) -> Optional[str]:
    """Tìm ảnh theo nhiều ứng viên tên file trong thư mục images_dir; trả về đường dẫn đầu tiên tìm thấy."""
    candidates = [
        coco_name_from_id(image_id),
        f"{image_id}.jpg",
        f"{image_id}.png",
        f"{int(image_id):012d}.png",
    ]
    for name in candidates:
        p = os.path.join(images_dir, name)
        if os.path.exists(p):
            return p
    return None


def _coerce_int_key_map(d: Dict[Any, Any]) -> Dict[int, Any]:
    """Chuyển khoá dạng chuỗi số sang int cho tiện truy cập."""
    out: Dict[int, Any] = {}
    for k, v in (d or {}).items():
        try:
            out[int(k)] = v
        except Exception:
            pass
    return out


def load_name_map(path: Optional[str]) -> Dict[int, Dict[int, str]]:
    """Đọc file JSON ánh xạ tên đối tượng: image_id -> {object_id -> name}.

    Hỗ trợ các dạng:
    - {"7615": {"1": "người", "2": "bóng"}, ...}
    - {7615: {1: "người", 2: "bóng"}, ...}
    - [{"image_id": 7615, "names": {"1":"người"}} , ...]
    """
    if not path:
        return {}
    try:
        data = read_json(path)
    except Exception:
        return {}
    out: Dict[int, Dict[int, str]] = {}
    if isinstance(data, dict):
        # map trực tiếp: image_id -> map(object_id->name)
        for imgk, names in data.items():
            try:
                iid = int(imgk)
            except Exception:
                continue
            if isinstance(names, dict):
                out[iid] = {int(ok): str(ov) for ok, ov in _coerce_int_key_map(names).items() if isinstance(ov, (str, int))}
    elif isinstance(data, list):
        for e in data:
            if not isinstance(e, dict):
                continue
            iid = e.get("image_id")
            names = e.get("names") or {}
            try:
                iid = int(iid)
            except Exception:
                continue
            if isinstance(names, dict):
                out[iid] = {int(ok): str(ov) for ok, ov in _coerce_int_key_map(names).items() if isinstance(ov, (str, int))}
    return out


# ------------------------- FONT (Unicode VN) -------------------------
def _windows_font_paths() -> List[str]:
    """Liệt kê đường dẫn font trong thư mục Fonts của Windows (nếu có)."""
    paths: List[str] = []
    win_dir = os.environ.get("WINDIR") or "C:\\Windows"
    fonts_dir = os.path.join(win_dir, "Fonts")
    if os.path.isdir(fonts_dir):
        try:
            for fn in os.listdir(fonts_dir):
                paths.append(os.path.join(fonts_dir, fn))
        except Exception:
            pass
    return paths


def get_vietnamese_font(size: int = 18) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Chọn font có hỗ trợ tiếng Việt:
    - Ưu tiên đường dẫn tuyệt đối từ biến môi trường VN_FONT_PATH.
    - Sau đó thử tên font trong thư mục hiện tại/repo.
    - Tiếp theo thử trong C:\\Windows\\Fonts.
    - Cuối cùng dùng font mặc định của Pillow.
    """
    # Các font có hỗ trợ tiếng Việt phổ biến
    preferred = [
        "arial.ttf",
        "arialuni.ttf",
        "segoeui.ttf",
        "tahoma.ttf",
        "DejaVuSans.ttf",
        "DejaVuSansCondensed.ttf",
        "NotoSans-Regular.ttf",
        "NotoSansDisplay-Regular.ttf",
        "Times.ttf",
        "times.ttf",
        "timesi.ttf",
        "timesbd.ttf",
    ]
    # 1) Thử đường dẫn tuyệt đối nếu người dùng đặt env FONT_PATH
    env_font = os.environ.get("VN_FONT_PATH")
    if env_font and os.path.exists(env_font):
        try:
            return ImageFont.truetype(env_font, size=size)
        except Exception:
            pass
    # 2) Thử trong thư mục hiện tại / repo
    for fn in preferred:
        if os.path.exists(fn):
            try:
                return ImageFont.truetype(fn, size=size)
            except Exception:
                continue
    # 3) Thử thư mục Fonts của Windows
    for p in _windows_font_paths():
        base = os.path.basename(p).lower()
        if base in [f.lower() for f in preferred]:
            try:
                return ImageFont.truetype(p, size=size)
            except Exception:
                continue
    # 4) Cuối cùng: font mặc định (có thể không hiển thị đủ dấu)
    return ImageFont.load_default()


# ------------------------- VẼ (PIL + OpenCV) -------------------------
def draw_text_vi(
    img_bgr: np.ndarray,
    text: str,
    org_xy: Tuple[int, int],
    font: ImageFont.ImageFont,
    fg=(255, 255, 255),
    bg=(0, 0, 0),
) -> np.ndarray:
    """Vẽ text Unicode lên ảnh BGR bằng Pillow. org_xy là toạ độ góc trái-dưới (giống cv2.putText)."""
    # Chuyển BGR -> RGB cho Pillow
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    draw = ImageDraw.Draw(pil_img)
    # Tính bbox của text
    ascent, descent = font.getmetrics() if hasattr(font, "getmetrics") else (0, 0)
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        tw, th = draw.textsize(text, font=font)
    x, y_baseline = org_xy
    # Chúng ta coi org_xy là baseline, vẽ nền phía trên
    x0, y0 = x, y_baseline - th - 4
    x1, y1 = x + tw + 6, y_baseline + 2
    # Vẽ nền (bg)
    if bg is not None:
        draw.rectangle([x0, y0, x1, y1], fill=bg)
    # Vẽ text (điều chỉnh lên 1-2 px cho đẹp)
    draw.text((x + 3, y_baseline - th - 1), text, font=font, fill=fg)
    # Chuyển về BGR
    out = cv2.cvtColor(np.asarray(pil_img), cv2.COLOR_RGB2BGR)
    return out


def draw_box(img: np.ndarray, bbox_xyxy: List[float], color=(0, 165, 255), thick=2):
    """Vẽ bbox (x1,y1,x2,y2) lên ảnh; tự động cắt vào trong biên ảnh."""
    x1, y1, x2, y2 = map(int, bbox_xyxy)
    h, w = img.shape[:2]
    x1 = max(0, min(w - 1, x1))
    x2 = max(0, min(w - 1, x2))
    y1 = max(0, min(h - 1, y1))
    y2 = max(0, min(h - 1, y2))
    cv2.rectangle(img, (x1, y1), (x2, y2), color, thick)
    return img


def draw_arrow(
    img: np.ndarray,
    p1: Tuple[int, int],
    p2: Tuple[int, int],
    color=(0, 0, 230),
    thick=2,
):
    """Vẽ mũi tên từ p1 tới p2 bằng OpenCV."""
    cv2.arrowedLine(img, p1, p2, color, thick, tipLength=0.03)
    return img


def center_of(b: List[float]) -> Tuple[int, int]:
    """Tâm (x,y) của bbox (x1,y1,x2,y2)."""
    x1, y1, x2, y2 = b
    return int((x1 + x2) / 2), int((y1 + y2) / 2)


def to_xyxy(x: float, y: float, w: float, h: float) -> List[float]:
    """Chuyển bbox COCO (x,y,w,h) sang (x1,y1,x2,y2)."""
    return [float(x), float(y), float(x) + float(w), float(y) + float(h)]


# ------------------------- LOGIC -------------------------
def visualize_entry(
    entry: dict,
    images_dir: str,
    out_dir: str,
    font: ImageFont.ImageFont,
    name_map: Optional[Dict[int, Dict[int, str]]] = None,
) -> Optional[str]:
    """
    Vẽ bbox + tên đối tượng + mũi tên quan hệ cho một bản ghi.
    - Ưu tiên tên từ dữ liệu (names[0]); nếu không có, dùng name_map nếu cung cấp; cuối cùng fallback "ĐT <id>".
    - Lưu ảnh kết quả vào out_dir, trả về đường dẫn file đã lưu hoặc None nếu không vẽ được.
    """
    image_id = entry.get("image_id")
    if image_id is None:
        return None
    img_path = find_image_path(int(image_id), images_dir)
    if not img_path or not os.path.exists(img_path):
        return None

    img = cv2.imread(img_path)
    if img is None:
        return None

    # object_id -> bbox_xyxy; object_id -> name (nếu có)
    id2bbox: Dict[int, List[float]] = {}
    id2name: Dict[int, str] = {}
    for obj in entry.get("objects", []) or []:
        try:
            oid = (
                int(obj.get("object_id")) if obj.get("object_id") is not None else None
            )
            x = float(obj.get("x"))
            y = float(obj.get("y"))
            w = float(obj.get("w"))
            h = float(obj.get("h"))
        except Exception:
            continue
        if oid is None:
            continue
        # Lấy tên ưu tiên từ dữ liệu: names[0] -> name/label/class/category/instance/canonical
        name: Optional[str] = None
        nm_list = obj.get("names")
        if isinstance(nm_list, list) and nm_list:
            # lấy phần tử chuỗi đầu tiên không rỗng
            for cand in nm_list:
                if isinstance(cand, str) and cand.strip():
                    name = cand.strip()
                    break
        bbox = to_xyxy(x, y, w, h)
        id2bbox[oid] = bbox
        if name:
            id2name[oid] = name
        # Vẽ bbox + nhãn (ưu tiên name_map, sau đó trường name nội bộ, rồi fallback)
        img = draw_box(img, bbox, color=(0, 165, 255), thick=2)
        # Ưu tiên dùng tên có sẵn trong dữ liệu, sau đó mới tới name_map nếu cung cấp.
        label = id2name.get(oid) or (name_map or {}).get(int(image_id), {}).get(oid) or f"ĐT {oid}"
        # vẽ label phía trên góc trái bbox
        x1, y1, x2, y2 = map(int, bbox)
        img = draw_text_vi(img, label, (x1, y1), font, fg=(0, 0, 0), bg=(0, 165, 255))

    # Vẽ quan hệ
    for rel in entry.get("relationships", []) or []:
        sid = rel.get("subject_id")
        oid = rel.get("object_id")
        pred = str(rel.get("predicate", "quan hệ"))
        if sid in id2bbox and oid in id2bbox:
            b1 = id2bbox[sid]
            b2 = id2bbox[oid]
            c1 = center_of(b1)
            c2 = center_of(b2)
            img = draw_arrow(img, c1, c2, color=(0, 0, 230), thick=2)
            # Nhãn predicate ở giữa
            mx, my = (c1[0] + c2[0]) // 2, (c1[1] + c2[1]) // 2
            img = draw_text_vi(
                img, pred, (mx, my), font, fg=(255, 255, 255), bg=(0, 0, 230)
            )

    # Lưu
    ensure_dir(out_dir)
    out_path = os.path.join(out_dir, os.path.basename(img_path))
    cv2.imwrite(out_path, img)
    return out_path


def visualize(json_path: str, images_dir: str, out_dir: str, name_map_path: Optional[str] = None) -> int:
    """Vẽ cho toàn bộ dữ liệu trong JSON; trả về số ảnh đã lưu."""
    data = read_json(json_path)
    ensure_dir(out_dir)
    font = get_vietnamese_font(size=18)
    name_map = load_name_map(name_map_path)
    saved = 0
    if isinstance(data, list):
        for entry in data:
            if not isinstance(entry, dict):
                continue
            if visualize_entry(entry, images_dir, out_dir, font, name_map):
                saved += 1
    elif isinstance(data, dict):
        if visualize_entry(data, images_dir, out_dir, font, name_map):
            saved += 1
    return saved


def main():
    """CLI: đọc đường dẫn, gọi visualize và in thống kê."""
    ap = argparse.ArgumentParser(
        description="Vẽ bbox & quan hệ tiếng Việt từ JSON (COCO IDs)."
    )
    ap.add_argument("--json", help="Đường dẫn file JSON đầu vào.")
    ap.add_argument(
        "--images",
        default="data/coco_uitvic_test",
        help="Thư mục ảnh (mặc định: data/coco_uitvic_test)",
    )
    ap.add_argument(
        "--out",
        default="viz/output-vi-vg",
        help="Thư mục lưu ảnh kết quả (mặc định: viz/output-vi)",
    )
    ap.add_argument(
        "--name-map",
        dest="name_map",
        default=None,
        help="ĐƯỜNG DẪN file JSON ánh xạ tên: image_id -> {object_id: name}. Tuỳ chọn.\n"
             "Mặc định script sẽ ưu tiên dùng trường 'names' hoặc 'name' có sẵn trong dữ liệu.",
    )
    args = ap.parse_args()

    n = visualize(args.json, args.images, args.out, args.name_map)
    print(f"✅ Đã lưu {n} ảnh vào: {args.out}")
    if n == 0:
        print(
            "⚠️ Không có ảnh nào được vẽ. Kiểm tra image_id, đường dẫn --images và định dạng JSON."
        )
        print("   Gợi ý: image_id=7615 -> ảnh 000000007615.jpg trong COCO.")


if __name__ == "__main__":
    main()
# python data-cleaning/draw_vi_coco_relations.py --json output-AI\train\relationships_vi_coco_uitvic_train-final-v0.json --images data/coco_uitvic_train --out viz/output-vi-train
# 2695 ảnh vào

# python data-cleaning/draw_vi_coco_relations.py checking/relationships_part_1.json --images data/coco_uitvic_train --out checking-image/relationships_part_1


# python standardize_relationships_vi.py --infile checking/relationships_part_2.json --outfile checking/relationships_part_2.json
