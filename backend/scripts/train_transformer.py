import json
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from train_baseline import LABELS, PROJECT_ROOT, load_split


MODEL_OUTPUT = PROJECT_ROOT / "backend" / "models" / "liar_distilbert"


def train_transformer() -> dict[str, float]:
    try:
        import torch
        from torch.utils.data import Dataset
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            Trainer,
            TrainingArguments,
        )
    except ImportError as error:
        raise RuntimeError(
            "Install the optional transformer dependencies with "
            "`python -m pip install -r backend/requirements-transformer.txt`."
        ) from error

    splits = load_split()
    label_to_id = {label: index for index, label in enumerate(LABELS)}
    id_to_label = {index: label for label, index in label_to_id.items()}
    checkpoint = "distilbert/distilbert-base-uncased"
    tokenizer = AutoTokenizer.from_pretrained(checkpoint)

    class EncodedStatements(Dataset):
        def __init__(self, split: str):
            texts, labels = splits[split]
            self.encodings = tokenizer(
                texts,
                truncation=True,
                padding="max_length",
                max_length=128,
            )
            self.labels = [label_to_id[label] for label in labels]

        def __len__(self) -> int:
            return len(self.labels)

        def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
            item = {
                key: torch.tensor(values[index], dtype=torch.long)
                for key, values in self.encodings.items()
            }
            item["labels"] = torch.tensor(self.labels[index], dtype=torch.long)
            return item

    model = AutoModelForSequenceClassification.from_pretrained(
        checkpoint,
        num_labels=len(LABELS),
        id2label=id_to_label,
        label2id=label_to_id,
    )

    def compute_metrics(evaluation) -> dict[str, float]:
        predictions = np.argmax(evaluation.predictions, axis=-1)
        targets = evaluation.label_ids
        return {
            "accuracy": float(accuracy_score(targets, predictions)),
            "macro_f1": float(f1_score(targets, predictions, average="macro")),
            "macro_precision": float(
                precision_score(targets, predictions, average="macro", zero_division=0)
            ),
            "macro_recall": float(
                recall_score(targets, predictions, average="macro", zero_division=0)
            ),
        }

    arguments = TrainingArguments(
        output_dir=str(PROJECT_ROOT / "backend" / "models" / "transformer-checkpoints"),
        num_train_epochs=2,
        learning_rate=2e-5,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=32,
        eval_strategy="epoch",
        save_strategy="no",
        logging_strategy="epoch",
        report_to=[],
        seed=42,
        use_cpu=not torch.cuda.is_available(),
    )
    trainer = Trainer(
        model=model,
        args=arguments,
        train_dataset=EncodedStatements("train"),
        eval_dataset=EncodedStatements("valid"),
        compute_metrics=compute_metrics,
    )
    trainer.train()
    test_metrics = trainer.evaluate(EncodedStatements("test"), metric_key_prefix="test")
    MODEL_OUTPUT.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(MODEL_OUTPUT))
    tokenizer.save_pretrained(str(MODEL_OUTPUT))
    result = {
        "dataset": "LIAR (Wang, ACL 2017)",
        "checkpoint": checkpoint,
        "test_accuracy": float(test_metrics["test_accuracy"]),
        "test_macro_f1": float(test_metrics["test_macro_f1"]),
        "test_macro_precision": float(test_metrics["test_macro_precision"]),
        "test_macro_recall": float(test_metrics["test_macro_recall"]),
    }
    (MODEL_OUTPUT / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return {
        "test_accuracy": result["test_accuracy"],
        "test_macro_f1": result["test_macro_f1"],
    }


if __name__ == "__main__":
    print(train_transformer())
