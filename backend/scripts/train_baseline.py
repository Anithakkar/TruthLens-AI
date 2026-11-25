import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.pipeline import Pipeline

from prepare_dataset import PROCESSED_PATH, prepare_dataset


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = PROJECT_ROOT / "backend" / "models" / "liar_tfidf_logreg.joblib"
METRICS_PATH = PROJECT_ROOT / "backend" / "models" / "liar_tfidf_metrics.json"
LABELS = ["pants-fire", "false", "barely-true", "half-true", "mostly-true", "true"]


def load_split() -> dict[str, tuple[list[str], list[str]]]:
    if not PROCESSED_PATH.exists():
        prepare_dataset()

    examples: dict[str, tuple[list[str], list[str]]] = {
        split: ([], []) for split in ("train", "valid", "test")
    }
    with PROCESSED_PATH.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            texts, labels = examples[row["split"]]
            texts.append(row["text"])
            labels.append(row["label"])
    return examples


def evaluate(model: Pipeline, texts: list[str], labels: list[str]) -> dict[str, Any]:
    predictions = model.predict(texts)
    return {
        "examples": len(labels),
        "accuracy": float(accuracy_score(labels, predictions)),
        "macro_f1": float(f1_score(labels, predictions, labels=LABELS, average="macro")),
        "classification_report": classification_report(
            labels,
            predictions,
            labels=LABELS,
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": confusion_matrix(labels, predictions, labels=LABELS).tolist(),
    }


def train() -> dict[str, Any]:
    splits = load_split()
    train_texts, train_labels = splits["train"]
    model = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    ngram_range=(1, 2),
                    min_df=2,
                    max_features=100_000,
                    sublinear_tf=True,
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )
    model.fit(train_texts, train_labels)
    metrics = {
        "dataset": "LIAR (Wang, ACL 2017)",
        "label_semantics": (
            "Six-way benchmark labels attributed by the dataset source; "
            "predictions are not independent fact verification."
        ),
        "features": "statement text only; speaker and metadata are excluded",
        "train_examples": len(train_labels),
        "train_label_counts": dict(sorted(Counter(train_labels).items())),
        "validation": evaluate(model, *splits["valid"]),
        "test": evaluate(model, *splits["test"]),
    }
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


if __name__ == "__main__":
    results = train()
    print(f"Saved model: {MODEL_PATH}")
    print(f"Test accuracy: {results['test']['accuracy']:.3f}")
    print(f"Test macro-F1: {results['test']['macro_f1']:.3f}")
