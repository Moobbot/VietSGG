import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image


# === CẤU HÌNH ĐƯỜNG DẪN ===
INPUT_PATH = Path("relationships_vi_coco_uitvic_test-final.json")
OUTPUT_COCO = Path("val.json")
OUTPUT_REL = Path("rel_test.json")
IMAGES_DIR = "coco_uitvic_test"  # Thư mục chứa ảnh

def coco_name_from_id(image_id: int) -> str:
    return f"{int(image_id):012d}.jpg"


def find_image_path(image_id: int, images_dir: str) -> Optional[str]:
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

# === HÀM CHUYỂN ĐỔI ===
def convert_vg_to_coco_sgg(input_path: Path, output_coco: Path, output_rel: Path, images_dir: str):
    with open(input_path, "r", encoding="utf-8") as f:
        vg_data = json.load(f)

    images = []
    annotations = []
    relationships_by_image: Dict[str, List[List[int]]] = {}
    categories_set = set()
    object_counter = 0
    predicate_set = set()

    for img_item in vg_data:
        image_id = img_item["image_id"]
        # Tìm đường dẫn ảnh thực tế
        img_path = find_image_path(int(image_id), images_dir)
        if img_path and os.path.exists(img_path):
            file_name = os.path.basename(img_path)
            file_key = os.path.splitext(file_name)[0]  # loại bỏ .jpg
            with Image.open(img_path) as im:
                width, height = im.size
        else:
            file_name = img_item.get("image", f"{image_id}.jpg")
            file_key = os.path.splitext(file_name)[0]
            width = img_item.get("width", 800)
            height = img_item.get("height", 600)

        images.append({
            "id": image_id,
            "file_name": file_name,
            "height": height,
            "width": width
        })

        obj_id_map = {}
        objects = img_item.get("objects", [])
        ann_indices = []
        for idx, obj in enumerate(objects):
            category = obj["names"][0] if obj.get("names") else "unknown"
            categories_set.add(category)

            ann = {
                "id": object_counter,
                "image_id": image_id,
                "bbox": [obj["x"], obj["y"], obj["w"], obj["h"]],
                "area": obj["w"] * obj["h"],
                "iscrowd": 0,
                "category_id": category  # sẽ map lại sau
            }
            obj_id_map[obj["object_id"]] = idx  # index trong ảnh này
            ann_indices.append(object_counter)
            annotations.append(ann)
            object_counter += 1

        rels = img_item.get("relationships", [])
        rel_entries = []
        for rel in rels:
            subj_ann_idx = obj_id_map.get(rel["subject_id"])
            obj_ann_idx = obj_id_map.get(rel["object_id"])
            predicate = rel["predicate"]
            predicate_set.add(predicate)

            if subj_ann_idx is not None and obj_ann_idx is not None:
                rel_entries.append([subj_ann_idx, obj_ann_idx, predicate])  # dùng index local

        if rel_entries:
            relationships_by_image[str(image_id)] = rel_entries  # key là str(image_id)

    # Ánh xạ category name → ID
    categories_list = sorted(list(categories_set))
    category2id = {cat: i + 1 for i, cat in enumerate(categories_list)}

    # Cập nhật category_id trong annotations
    for ann in annotations:
        cat_name = ann["category_id"]
        ann["category_id"] = category2id[cat_name]

    # COCO categories
    categories = [
        {"id": cid, "name": name, "supercategory": name}
        for name, cid in category2id.items()
    ]

    # Ánh xạ predicate → ID
    predicate_list = ["__background__"] + sorted(list(predicate_set))
    predicate2id = {p: i for i, p in enumerate(predicate_list)}

    # Chuyển quan hệ về index
    relationships_final = {}
    for image_id_str, rels in relationships_by_image.items():
        rel_entries = []
        for subj_idx, obj_idx, pred in rels:
            rel_entries.append([subj_idx, obj_idx, predicate2id[pred]])
        relationships_final[image_id_str] = rel_entries

    # Lưu COCO
    coco_format = {
        "images": images,
        "annotations": annotations,
        "categories": categories
    }
    with open(output_coco, "w", encoding="utf-8") as f:
        json.dump(coco_format, f, ensure_ascii=False, indent=2)

    # Lưu rel.json
    rel_json_format = {
        "test": relationships_final,
        "rel_categories": predicate_list
    }
    with open(output_rel, "w", encoding="utf-8") as f:
        json.dump(rel_json_format, f, ensure_ascii=False, indent=2)

    print(f"✅ Đã lưu COCO-format: {output_coco}")
    print(f"✅ Đã lưu quan hệ:     {output_rel}")

# === GỌI HÀM CHUYỂN ĐỔI ===
convert_vg_to_coco_sgg(INPUT_PATH, OUTPUT_COCO, OUTPUT_REL, IMAGES_DIR)
