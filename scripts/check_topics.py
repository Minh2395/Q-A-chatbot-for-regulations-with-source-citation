import json
from collections import Counter

file_path = "data_phapdien/phapdien_raw.json"

with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)

targets = ["Xây dựng, nhà ở, đô thị"]

print("===== SỐ BẢN GHI THEO CHỦ ĐỀ =====")
topic_counts = Counter(
    item.get("topic_title_vi") or "(Trống)"
    for item in data
)

for topic in targets:
    print(f"{topic}: {topic_counts[topic]}")

print("\n===== MẪU BẢN GHI: XÂY DỰNG, NHÀ Ở, ĐÔ THỊ =====")

count = 0
for item in data:
    if item.get("topic_title_vi") == "Xây dựng, nhà ở, đô thị":
        print(json.dumps({
            "topic": item.get("topic_title_vi"),
            "title": item.get("article_title"),
            "content": (item.get("content_text") or "")[:250],
        }, ensure_ascii=False))
        count += 1

        if count >= 10:
            break
