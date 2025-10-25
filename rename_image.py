import os


def rename_images(folder: str) -> None:
    """
    Đổi tên ảnh .jpg trong thư mục `folder` bằng cách loại bỏ số 0 ở đầu tên file (phần trước đuôi).
    - Ví dụ: 000123.jpg -> 123.jpg
    - Bỏ qua các file không phải .jpg
    """
    # Duyệt toàn bộ mục trong thư mục chỉ định
    for filename in os.listdir(folder):
        # Chỉ xử lý file .jpg (chữ thường)
        if filename.endswith(".jpg"):
            # Tách tên và đuôi mở rộng
            name, ext = os.path.splitext(filename)
            # Loại bỏ các số 0 ở đầu tên
            new_name = name.lstrip("0") or "0"  # đảm bảo không rỗng nếu tên toàn 0
            new_name = new_name + ext
            # Tạo đường dẫn cũ/mới tuyệt đối theo thư mục đích
            old_path = os.path.join(folder, filename)
            new_path = os.path.join(folder, new_name)
            # Thực hiện đổi tên nếu có thay đổi
            if old_path != new_path:
                os.rename(old_path, new_path)


if __name__ == "__main__":
    # Mặc định dùng thư mục coco_uitvic_train như trước đây
    rename_images("coco_uitvic_train")
