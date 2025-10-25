import json
import os
from pathlib import Path

# Danh sách các file rel cần ghép
REL_FILES = [
    "rel_train.json",
    "rel_val.json"
]

OUTPUT_FILE = "rel.json"

def merge_rel_files(rel_files, output_file):
    merged_test = {}
    merged_train = {}
    merged_categories = []
    categories_set = set()

    for rel_path in rel_files:
        if not os.path.exists(rel_path):
            print(f"⚠️ Không tìm thấy file: {rel_path}")
            continue
        with open(rel_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Gộp phần test hoặc train
            if "val" in rel_path:
                for k, v in data.get("test", {}).items():
                    merged_test[k] = v
            elif "train" in rel_path:
                for k, v in data.get("test", {}).items():
                    merged_train[k] = v
            # Gộp rel_categories
            for cat in data.get("rel_categories", []):
                if cat not in categories_set:
                    merged_categories.append(cat)
                    categories_set.add(cat)

    merged = {
        "train": merged_train,
        "val": merged_test,
        "rel_categories": merged_categories
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"✅ Đã lưu file ghép: {output_file}")

if __name__ == "__main__":
    merge_rel_files(REL_FILES, OUTPUT_FILE)
