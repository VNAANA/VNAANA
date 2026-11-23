import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

THRESHOLD = 0.60
MAX_TAGS = 3
MAX_INPUT_LENGTH = 256

VNAANA_GENRES = (
    "Politics", "Technology", "Sports", "Climate", "Economy", "Health",
    "Entertainment", "Culture", "Science", "Domestic", "International",
    "Social Issues",
)


@dataclass(frozen=True)
class GenrePrediction:
    tag: str
    score: float


def _get_labels(model, labels_path: Path | None) -> list[str]:
    if labels_path is not None:
        try:
            labels = json.loads(labels_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"Could not read labels from {labels_path}") from exc
        if not isinstance(labels, list) or not all(isinstance(label, str) for label in labels):
            raise RuntimeError("Labels must be a JSON list of genre names")
    else:
        mapping = model.config.id2label or {}
        labels = [mapping.get(index) for index in range(model.config.num_labels)]
        if any(label is None for label in labels):
            raise RuntimeError("Checkpoint config.id2label is incomplete; provide a labels file")
        if all(label == f"LABEL_{index}" for index, label in enumerate(labels)):
            raise RuntimeError(
                "Checkpoint contains generic LABEL_n names; provide the trained "
                "label order through a labels file"
            )

    if len(labels) != len(VNAANA_GENRES) or set(labels) != set(VNAANA_GENRES):
        raise RuntimeError("Checkpoint labels do not match the VNAANA genres")
    return labels


class GenreClassificationService:
    def __init__(self, *, model, tokenizer, labels: Sequence[str], torch_module, device):
        self.model = model
        self.tokenizer = tokenizer
        self.labels = tuple(labels)
        self.torch = torch_module
        self.device = device

    @classmethod
    def from_checkpoint(
        cls,
        checkpoint: Path,
        *,
        labels_path: Path | None = None,
        device_name: str = "cpu",
    ) -> "GenreClassificationService":
        checkpoint = checkpoint.expanduser().resolve()
        if not checkpoint.is_dir():
            raise RuntimeError(f"Checkpoint directory does not exist: {checkpoint}")
        if labels_path is not None:
            labels_path = labels_path.expanduser().resolve()
            if not labels_path.is_file():
                raise RuntimeError(f"Labels file does not exist: {labels_path}")

        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        if device_name not in {"cpu", "cuda"}:
            raise RuntimeError("device_name must be 'cpu' or 'cuda'")
        if device_name == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but is not available")
        device = torch.device(device_name)

        tokenizer = AutoTokenizer.from_pretrained(checkpoint, local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(
            checkpoint, local_files_only=True
        )
        labels = _get_labels(model, labels_path)
        model.to(device)
        model.eval()
        return cls(
            model=model, tokenizer=tokenizer, labels=labels,
            torch_module=torch, device=device,
        )

    def classify(
        self, *, title: str, summary: str | None, context: str | None
    ) -> list[GenrePrediction]:
        text = "\n\n".join(
            part.strip()
            for part in (title, summary, context)
            if part and part.strip()
        )
        if not text:
            raise ValueError("At least one non-blank Story text field is required")

        encoded = self.tokenizer(
            text, truncation=True, max_length=MAX_INPUT_LENGTH, return_tensors="pt"
        )
        encoded = {name: tensor.to(self.device) for name, tensor in encoded.items()}
        with self.torch.inference_mode():
            logits = self.model(**encoded).logits.squeeze(0)
            scores = self.torch.sigmoid(logits)

        if scores.ndim != 1 or scores.shape[0] != len(self.labels):
            raise RuntimeError(
                f"Expected {len(self.labels)} output scores, received shape {tuple(scores.shape)}"
            )
        if not self.torch.isfinite(scores).all().item():
            raise RuntimeError("Model returned a non-finite score")

        ranked = sorted(
            (
                GenrePrediction(self.labels[index], float(score))
                for index, score in enumerate(scores.cpu())
            ),
            key=lambda prediction: prediction.score,
            reverse=True,
        )
        selected = [prediction for prediction in ranked if prediction.score >= THRESHOLD]
        return selected[:MAX_TAGS]
