import os
import json
import cv2
from PIL import ImageFont, ImageDraw, Image
import numpy as np

# === ĐƯỜNG DẪN ===
IMG_DIR = "coco_uitvic_train"
ANNOT_FILE = "train.json"
REL_FILE = "rel.json"
OUTPUT_DIR = "outputs_train"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# === ĐỌC ANNOTATION ===
with open(ANNOT_FILE, "r", encoding="utf-8") as f:
    ann_data = json.load(f)

with open(REL_FILE, "r", encoding="utf-8") as f:
    rel_data = json.load(f)

# === MAPPING category_id → label ===
catid2label = {
    cat["id"]: cat["supercategory"] for cat in ann_data.get("categories", [])
}

# === TẠO MAPPING ảnh → annotation ===
imgid2anns = {}
for ann in ann_data["annotations"]:
    img_id = ann["image_id"]
    imgid2anns.setdefault(img_id, []).append(ann)

imgid2file = {img["id"]: img["file_name"] for img in ann_data["images"]}


# === VẼ ===
def draw_visual_genome(img_path, objects, relationships, save_path=None):
    img = cv2.imread(img_path)
    if img is None:
        print(f"❌ Không tìm thấy ảnh: {img_path}")
        return
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)

    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()

    object_centers = {}

    for obj in objects:
        x, y, w, h = obj["x"], obj["y"], obj["w"], obj["h"]
        label = obj["names"][0]
        draw.rectangle([x, y, x + w, y + h], outline="red", width=3)
        draw.text((x, max(y - 25, 0)), label, font=font, fill="yellow")
        object_centers[obj["object_id"]] = (x + w // 2, y + h // 2)

    rel_categories = rel_data.get("rel_categories", [])

    for rel in relationships:
        try:
            sid = rel[0]
            oid = rel[1]
            pred_id = rel[2]
            pred = rel_categories[pred_id] if pred_id < len(rel_categories) else str(pred_id)

            subj = objects[sid]
            obj = objects[oid]

            x1, y1 = subj["x"] + subj["w"] // 2, subj["y"] + subj["h"] // 2
            x2, y2 = obj["x"] + obj["w"] // 2, obj["y"] + obj["h"] // 2

            draw.line([x1, y1, x2, y2], fill="blue", width=2)
            mid = ((x1 + x2) // 2, (y1 + y2) // 2)
            draw.text(mid, pred, font=font, fill="blue")
        except Exception as e:
            print(f"Lỗi khi vẽ quan hệ: {rel}, lỗi: {e}")

        if sid in object_centers and oid in object_centers:
            x1, y1 = object_centers[sid]
            x2, y2 = object_centers[oid]
            draw.line([x1, y1, x2, y2], fill="blue", width=2)
            mid = ((x1 + x2) // 2, (y1 + y2) // 2)
            draw.text(mid, pred, font=font, fill="blue")

    img_result = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    if save_path:
        cv2.imwrite(save_path, img_result)
    else:
        cv2.imshow("Image", img_result)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


rel_split = "train"  # hoặc "val"
rel_image_ids = list(rel_data[rel_split].keys())#[:5]

# === CHẠY TRỰC QUAN CHO 5 ẢNH ===
for image_id_str in rel_image_ids:
    image_id = int(image_id_str)
    # test trước 5 ảnh
    if image_id_str == "rel_categories":
        continue

    image_id = int(image_id_str)
    image_name = imgid2file.get(image_id)
    if not image_name:
        continue

    img_path = os.path.join(IMG_DIR, image_name)
    save_path = os.path.join(OUTPUT_DIR, image_name)

    # Lấy annotation gốc
    anns = imgid2anns.get(image_id, [])
    objects = []
    for ann in anns:
        bbox = ann["bbox"]
        cat_id = ann["category_id"]
        label = catid2label.get(cat_id, "unknown")
        objects.append(
            {
                "object_id": ann["id"],  # ID gốc trong annotation
                "names": [label],
                "x": bbox[0],
                "y": bbox[1],
                "w": bbox[2],
                "h": bbox[3],
            }
        )

    # Lấy quan hệ từ rel_test.json nếu có
    rel_ann = next(
        (
            x
            for x in rel_data.values()
            if isinstance(x, list)
            and any(isinstance(i, dict) and i.get("image_id") == image_id for i in x)
        ),
        None,
    )
    if isinstance(rel_ann, list):
        relationships = rel_ann
    else:
        relationships = rel_data[rel_split].get(image_id_str, [])

    draw_visual_genome(img_path, objects, relationships, save_path)
