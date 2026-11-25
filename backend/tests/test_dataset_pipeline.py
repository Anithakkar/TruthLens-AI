import csv

from scripts import prepare_dataset as dataset


def test_prepare_dataset_skips_bad_rows_and_keeps_source_splits(tmp_path, monkeypatch) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    valid_row = [
        "1.json",
        "true",
        "A benchmark statement with enough words.",
        "topic",
        "speaker",
        "job",
        "state",
        "party",
        "0",
        "0",
        "0",
        "0",
        "0",
        "context",
    ]
    for split in dataset.SPLITS:
        with (raw_dir / f"{split}.tsv").open("w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file, delimiter="\t")
            writer.writerow(valid_row)
            writer.writerow(["malformed", "row"])

    processed_path = tmp_path / "processed.csv"
    monkeypatch.setattr(dataset, "RAW_DIR", raw_dir)
    monkeypatch.setattr(dataset, "PROCESSED_PATH", processed_path)
    monkeypatch.setattr(dataset, "download_dataset", lambda: None)

    counts = dataset.prepare_dataset()

    assert counts == {"train": 1, "valid": 1, "test": 1}
    with processed_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert [row["split"] for row in rows] == ["train", "valid", "test"]
    assert all(row["text"] == valid_row[2] for row in rows)
