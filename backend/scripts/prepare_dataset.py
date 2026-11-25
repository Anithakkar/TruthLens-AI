import csv
import io
import urllib.request
import zipfile
from pathlib import Path


DATASET_URL = "https://sites.cs.ucsb.edu/~william/data/liar_dataset.zip"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "liar" / "raw"
ZIP_PATH = PROJECT_ROOT / "data" / "liar" / "liar_dataset.zip"
PROCESSED_PATH = PROJECT_ROOT / "data" / "liar" / "liar_processed.csv"
SPLITS = ("train", "valid", "test")
LABELS = {
    "pants-fire",
    "false",
    "barely-true",
    "half-true",
    "mostly-true",
    "true",
}


def download_dataset() -> None:
    if RAW_DIR.exists() and all((RAW_DIR / f"{split}.tsv").exists() for split in SPLITS):
        return

    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        DATASET_URL,
        headers={"User-Agent": "TruthLens-AI educational research project"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        archive_bytes = response.read()

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        for split in SPLITS:
            member = f"{split}.tsv"
            if member not in archive.namelist():
                raise ValueError(f"Dataset archive is missing {member}.")
            (RAW_DIR / member).write_bytes(archive.read(member))
        if "README" in archive.namelist():
            (RAW_DIR / "README").write_bytes(archive.read("README"))
    ZIP_PATH.write_bytes(archive_bytes)


def prepare_dataset() -> dict[str, int]:
    download_dataset()
    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    counts = {split: 0 for split in SPLITS}

    with PROCESSED_PATH.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=["split", "id", "label", "text"])
        writer.writeheader()
        for split in SPLITS:
            source = RAW_DIR / f"{split}.tsv"
            with source.open(encoding="utf-8", newline="") as input_file:
                for row in csv.reader(input_file, delimiter="\t"):
                    if len(row) != 14:
                        continue
                    statement_id, label, text = row[:3]
                    text = text.strip()
                    if label not in LABELS or not text:
                        continue
                    writer.writerow(
                        {"split": split, "id": statement_id, "label": label, "text": text}
                    )
                    counts[split] += 1

    if not counts["train"] or not counts["valid"] or not counts["test"]:
        raise ValueError("Dataset preparation produced an empty split.")
    return counts


if __name__ == "__main__":
    prepared_counts = prepare_dataset()
    print(f"Prepared dataset at {PROCESSED_PATH}")
    print(f"Rows per split: {prepared_counts}")
