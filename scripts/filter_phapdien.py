import json
import os
import pandas as pd

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

DATA_DIR = os.path.join(BASE_DIR, "data_phapdien")
INPUT_FILE = os.path.join(DATA_DIR, "phapdien_raw.json")

# Chỉ lấy đúng chủ đề đã thống nhất.
TARGET_TOPIC = "Xây dựng, nhà ở, đô thị"


def has_content(record):
    return bool(
        str(record.get("content_text") or "").strip()
    )


def is_target_record(record):
    topic = str(record.get("topic_title_vi") or "").strip()
    return topic == TARGET_TOPIC and has_content(record)


def export_records(name, records):
    json_path = os.path.join(DATA_DIR, f"{name}.json")
    csv_path = os.path.join(DATA_DIR, f"{name}.csv")

    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(
            records,
            file,
            ensure_ascii=False,
            indent=2
        )

    pd.DataFrame(records).to_csv(
        csv_path,
        index=False,
        encoding="utf-8-sig"
    )

    print(f"\n{name}")
    print(f"Số bản ghi: {len(records):,}")
    print(f"JSON: {json_path}")
    print(f"CSV: {csv_path}")


def export_review_report(records):
    rows = []

    for record in records:
        rows.append({
            "record_id": record.get("record_id", ""),
            "topic_title_vi": record.get("topic_title_vi", ""),
            "subject_title_vi": record.get("subject_title_vi", ""),
            "chapter_title": record.get("chapter_title", ""),
            "article_id": record.get("article_id", ""),
            "article_title": record.get("article_title", ""),
            "source_note_text": record.get("source_note_text", ""),
            "source_links": json.dumps(
                record.get("source_links", []),
                ensure_ascii=False
            ),
            "source_url": record.get("source_url", ""),
            "content_text": record.get("content_text", ""),
            "scraped_at": record.get("scraped_at", ""),
        })

    path = os.path.join(
        DATA_DIR,
        "phapdien_housing_land_review.csv"
    )

    pd.DataFrame(rows).to_csv(
        path,
        index=False,
        encoding="utf-8-sig"
    )

    print(f"\nBáo cáo rà soát: {path}")


def main():
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(
            f"Không tìm thấy file: {INPUT_FILE}"
        )

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        records = json.load(file)

    if not isinstance(records, list):
        raise ValueError(
            "Dữ liệu JSON phải là một danh sách bản ghi."
        )

    # Lọc chính xác theo chủ đề, không dùng từ khóa nội dung.
    target_records = [
        record
        for record in records
        if isinstance(record, dict)
        and is_target_record(record)
    ]

    # Loại trùng; ưu tiên record_id.
    unique_records = []
    seen = set()

    for record in target_records:
        record_id = str(record.get("record_id") or "").strip()

        if record_id:
            key = ("record_id", record_id)
        else:
            key = (
                "content",
                str(record.get("article_id") or "").strip(),
                str(record.get("article_title") or "").strip(),
                str(record.get("content_text") or "").strip(),
            )

        if key not in seen:
            seen.add(key)
            unique_records.append(record)

    os.makedirs(DATA_DIR, exist_ok=True)

    export_records(
        "phapdien_housing_land",
        unique_records
    )

    export_review_report(unique_records)

    print("\n===== THỐNG KÊ THEO CHỦ ĐỀ =====")
    print(f"{TARGET_TOPIC}: {len(unique_records):,}")

    print("\n===== THỐNG KÊ THEO LĨNH VỰC =====")
    subject_counts = pd.Series([
        record.get("subject_title_vi") or "(Không xác định)"
        for record in unique_records
    ]).value_counts()

    print(subject_counts.to_string())

    print("\n===== TỔNG KẾT =====")
    print(f"Dữ liệu gốc: {len(records):,}")
    print(f"Bản ghi thuộc chủ đề: {len(target_records):,}")
    print(f"Bản ghi sau loại trùng: {len(unique_records):,}")

    print(
        "\nLƯU Ý: Dữ liệu được chọn theo chủ đề pháp điển, "
        "chưa xác minh đầy đủ hiệu lực và phiên bản pháp luật. "
        "Chủ đề này có thể chứa nội dung kiến trúc, nên chưa "
        "đảm bảo bao phủ toàn bộ quy định về đất đai."
    )


if __name__ == "__main__":
    main()