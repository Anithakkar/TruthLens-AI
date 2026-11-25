from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib

from app.core.config import settings


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = PROJECT_ROOT / "backend" / "models" / "liar_tfidf_logreg.joblib"
LABEL_DESCRIPTIONS = {
    "pants-fire": "rated pants-on-fire in the LIAR benchmark",
    "false": "rated false in the LIAR benchmark",
    "barely-true": "rated barely true in the LIAR benchmark",
    "half-true": "rated half true in the LIAR benchmark",
    "mostly-true": "rated mostly true in the LIAR benchmark",
    "true": "rated true in the LIAR benchmark",
}


class ModelNotReadyError(RuntimeError):
    pass


def _transformer_model_path() -> Path:
    path = Path(settings.transformer_model_path)
    return path if path.is_absolute() else PROJECT_ROOT / path


@lru_cache(maxsize=1)
def _load_model() -> Any:
    if not MODEL_PATH.is_file():
        raise ModelNotReadyError(
            "The text classifier has not been trained. Run backend/scripts/train_baseline.py."
        )
    return joblib.load(MODEL_PATH)


def is_model_ready() -> bool:
    if settings.model_provider == "transformer":
        return is_transformer_model_ready()
    return MODEL_PATH.is_file()


def is_transformer_model_ready() -> bool:
    return (_transformer_model_path() / "config.json").is_file()


def _predict_traditional(text: str) -> dict[str, Any]:
    model = _load_model()
    probabilities = model.predict_proba([text])[0]
    classifier = model.named_steps["classifier"]
    vectorizer = model.named_steps["tfidf"]
    label_index = int(probabilities.argmax())
    label = str(classifier.classes_[label_index])

    vector = vectorizer.transform([text])
    feature_names = vectorizer.get_feature_names_out()
    active_indices = vector.indices
    weighted_terms = [
        (str(feature_names[index]), float(vector[0, index] * classifier.coef_[label_index, index]))
        for index in active_indices
    ]
    positive = sorted(
        ((term, weight) for term, weight in weighted_terms if weight > 0),
        key=lambda item: item[1],
        reverse=True,
    )[:5]
    counter = sorted(
        ((term, weight) for term, weight in weighted_terms if weight < 0),
        key=lambda item: item[1],
    )[:5]

    return {
        "benchmark_label": label,
        "model_score": float(probabilities[label_index]),
        "label_description": LABEL_DESCRIPTIONS[label],
        "top_signals": [{"term": term, "contribution": weight} for term, weight in positive],
        "counter_signals": [
            {"term": term, "contribution": weight} for term, weight in counter
        ],
        "explanation": (
            "The label and score describe similarity to patterns learned from "
            "LIAR benchmark statements. Highlighted terms are model associations, "
            "not verified evidence about this article."
        ),
    }


def predict_statement(text: str) -> dict[str, Any]:
    if settings.model_provider == "transformer":
        return _predict_transformer(text)
    return _predict_traditional(text)


def predict_model_comparison(
    text: str,
    primary_prediction: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if settings.model_provider == "transformer":
        transformer = {"status": "available", **primary_prediction}
        if MODEL_PATH.is_file():
            traditional = {"status": "available", **_predict_traditional(text)}
        else:
            traditional = {
                "status": "not_trained",
                "message": "Train the traditional baseline to compare its prediction.",
            }
    else:
        traditional = {"status": "available", **primary_prediction}
        if is_transformer_model_ready():
            try:
                transformer = {"status": "available", **_predict_transformer(text)}
            except ModelNotReadyError as error:
                transformer = {"status": "unavailable", "message": str(error)}
        else:
            transformer = {
                "status": "not_trained",
                "message": "Fine-tune the transformer to compare its prediction.",
            }

    return {"traditional": traditional, "transformer": transformer}


@lru_cache(maxsize=1)
def _load_transformer() -> tuple[Any, Any, Any]:
    if not is_model_ready():
        raise ModelNotReadyError(
            "The transformer has not been fine-tuned. Run backend/scripts/train_transformer.py."
        )
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as error:
        raise ModelNotReadyError(
            "Install the optional transformer dependencies from "
            "backend/requirements-transformer.txt."
        ) from error

    model_path = str(_transformer_model_path())
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(model_path, local_files_only=True)
    model.eval()
    return torch, tokenizer, model


def _predict_transformer(text: str) -> dict[str, Any]:
    torch, tokenizer, model = _load_transformer()
    encoded = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=256,
    )
    model.zero_grad(set_to_none=True)
    embeddings = model.get_input_embeddings()(encoded["input_ids"]).detach()
    embeddings.requires_grad_(True)
    output = model(inputs_embeds=embeddings, attention_mask=encoded["attention_mask"])
    probabilities = torch.softmax(output.logits[0].detach(), dim=-1)
    label_index = int(torch.argmax(probabilities).item())
    label = model.config.id2label.get(label_index, model.config.id2label.get(str(label_index), ""))
    if label not in LABEL_DESCRIPTIONS:
        raise ModelNotReadyError(f"Unexpected transformer label: {label!r}.")

    output.logits[0, label_index].backward()
    contributions = (embeddings.grad * embeddings).sum(dim=-1)[0].detach()
    tokens = tokenizer.convert_ids_to_tokens(encoded["input_ids"][0])
    signals = []
    counters = []
    special_tokens = set(tokenizer.all_special_tokens)
    for token, contribution in zip(tokens, contributions.tolist()):
        if token in special_tokens:
            continue
        readable = token.replace("##", "").strip()
        if not readable or not any(character.isalnum() for character in readable):
            continue
        item = {"term": readable, "contribution": float(contribution)}
        (signals if contribution > 0 else counters).append(item)

    signals.sort(key=lambda item: item["contribution"], reverse=True)
    counters.sort(key=lambda item: item["contribution"])
    return {
        "benchmark_label": label,
        "model_score": float(probabilities[label_index].item()),
        "label_description": LABEL_DESCRIPTIONS[label],
        "top_signals": signals[:5],
        "counter_signals": counters[:5],
        "explanation": (
            "This fine-tuned transformer predicts a LIAR benchmark label. "
            "Token attributions are approximate gradient signals, not verified "
            "evidence or a truth determination."
        ),
    }
