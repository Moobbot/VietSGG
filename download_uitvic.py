"""
Script tải và chuẩn bị dữ liệu UIT-ViC từ Kaggle bằng kagglehub, sau đó sao chép
(nếu cần) về thư mục ./data của dự án.

Yêu cầu:
- Python 3.10+
- Đã cài đặt: pip install kagglehub
- Có kết nối Internet lần chạy đầu (kagglehub sẽ cache local cho các lần sau)

Cách dùng:
- Chạy từ thư mục gốc repo: python download_uitvic.py
- Kết quả: dữ liệu được đặt/ghép vào ./data
"""

#Download datataset
import kagglehub

# Tải phiên bản mới nhất của dataset theo slug Kaggle "leo040802/uitvic-dataset".
# kagglehub sẽ tự lo việc tải và giải nén vào cache nội bộ.
# Giá trị trả về `path` là đường dẫn tới thư mục dataset trong cache local.
# Download latest version
path = kagglehub.dataset_download("leo040802/uitvic-dataset")

print("Path to dataset files:", path)

import shutil
import os
from pathlib import Path

# Thiết lập thư mục đích local ./data để hợp nhất dữ liệu tải về
# (không ghi đè toàn bộ, chỉ copy tree với dirs_exist_ok=True).
# Robust copy: if `path` points to a cache/version folder, try to detect the real dataset root
src_path = Path(path)  # path from kagglehub (already extracted in your run)
local_dest = Path('.') / 'data'
local_dest.mkdir(parents=True, exist_ok=True)

def looks_like_dataset_root(p: Path) -> bool:
    """
    Heuristic kiểm tra xem thư mục `p` có giống thư mục gốc của dataset không.
    - Ưu tiên các thư mục chứa chỉ dấu thường gặp: images/annotations/train/test...
    - Hoặc nếu có số lượng ảnh đủ lớn ở ngay cấp hiện tại.
    Trả về True/False.
    """
    # heuristics: contains common dataset dirs or many images/annotations
    if not p.exists():
        return False
    names = {c.name.lower() for c in p.iterdir() if c.exists()} if p.is_dir() else set()
    indicators = {'coco_uitvic_test', 'coco_uitvic_train', 'images', 'annotations', 'train', 'test'}
    if indicators & names:
        return True
    # hoặc có nhiều file ảnh trực tiếp trong thư mục (>=10) thì coi như root hợp lệ
    # or many image files directly present
    if p.is_dir():
        img_count = sum(1 for f in p.iterdir() if f.suffix.lower() in {'.jpg', '.jpeg', '.png'} )
        if img_count >= 10:
            return True
    return False

# Tập hợp các ứng viên cho "thư mục gốc dataset":
# ưu tiên chính `src_path`, nếu không phù hợp thì duyệt các thư mục con ngay dưới nó.
# choose best candidate root: src_path or one of its immediate subdirs
candidates = [src_path]
if src_path.is_dir():
    candidates += [d for d in src_path.iterdir() if d.is_dir()]

# Chọn thư mục đầu tiên thỏa heuristic; nếu không, fallback về src_path.
chosen = None
for c in candidates:
    if looks_like_dataset_root(c):
        chosen = c
        break
# fallback to src_path if nothing matched
if chosen is None and src_path.exists():
    chosen = src_path

# Nếu tìm được source hợp lệ, tiến hành sao chép hợp nhất về ./data
if chosen is None:
    print('No valid source dataset found at', src_path)
else:
    print('Using dataset root:', chosen)
    # Tránh trường hợp source và dest là một, để không tự ghi đè vô nghĩa.
    # avoid copying into itself
    try:
        if Path(chosen).resolve() == local_dest.resolve():
            print('Source is same as destination; nothing to do.')
        else:
            # Sao chép toàn bộ nội dung từ `chosen` sang `local_dest`.
            # - Thư mục: copytree với dirs_exist_ok=True (ghép, không xoá đích).
            # - Tệp đơn lẻ: copy2 để giữ metadata cơ bản.
            # copy contents of chosen into local_dest (merge)
            for item in Path(chosen).iterdir():
                dest = local_dest / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)
            print('Dataset copied/extracted to:', local_dest)
    except Exception as e:
        # Ghi log lỗi copy (ví dụ: quyền truy cập, đường dẫn dài, xung đột file đang mở, ...)
        print('Error while copying dataset:', e)