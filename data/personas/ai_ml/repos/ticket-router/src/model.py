import onnxruntime as ort
import numpy as np
from transformers import AutoTokenizer
from .config import Config

class TicketRouterModel:
    """
    Wrapper around a distilled transformer exported to ONNX.
    Provides batched inference returning (label, confidence) pairs.
    """
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
        self.session = ort.InferenceSession(str(Config.MODEL_PATH))
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

    def _preprocess(self, texts: list[str]) -> dict[str, np.ndarray]:
        enc = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=128,
            return_tensors="np",
        )
        return {self.input_name: enc["input_ids"]}

    def predict(self, texts: list[str]) -> list[tuple[str, float]]:
        """
        Returns a list of (label, confidence) for each input text.
        Confidence is the softmax probability of the predicted class.
        """
        inputs = self._preprocess(texts)
        logits = self.session.run([self.output_name], inputs)[0]
        probs = np.exp(logits) / np.exp(logits).sum(axis=1, keepdims=True)
        preds = probs.argmax(axis=1)
        confidences = probs.max(axis=1)
        labels = [self._label_from_id(p) for p in preds]
        return list(zip(labels, confidences.tolist()))

    @staticmethod
    def _label_from_id(idx: int) -> str:
        # Mapping mirrors the training label order
        label_map = {0: "billing", 1: "technical", 2: "account", 3: "general"}
        return label_map.get(idx, "unknown")
