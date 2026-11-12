import os
import pandas as pd
from datasets import load_dataset

# 1. Lùi lại 1 cấp thư mục để lưu vào data_phapdien
# nằm cùng cấp với backend
output_dir = os.path.join("..", "data_phapdien")
os.makedirs(output_dir, exist_ok=True)

print("⏳ Đang tải Bộ Pháp điển từ Hugging Face...")

dataset = load_dataset(
    "tmquan/phapdien-moj-gov-vn",
    "documents",
    split="train"
)

df = dataset.to_pandas()

# 2. Đường dẫn file trong thư mục data_phapdien ở gốc dự án
json_file = os.path.join(output_dir, "phapdien_raw.json")
csv_file = os.path.join(output_dir, "phapdien_raw.csv")

# 3. Xuất dữ liệu ra JSON và CSV
df.to_json(
    json_file,
    orient="records",
    force_ascii=False,
    indent=2
)

df.to_csv(
    csv_file,
    index=False,
    encoding="utf-8-sig"
)

# 4. Thông báo kết quả
print(
    f"✅ Đã tải và xuất thành công vào folder: "
    f"{os.path.abspath(output_dir)}"
)
print(f"   📁 JSON: {os.path.abspath(json_file)}")
print(f"   📁 CSV:  {os.path.abspath(csv_file)}")