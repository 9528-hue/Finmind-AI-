"""
FinMind AI — Inference Service: Transaction Categorizer (Model A)
=================================================================
Loads the latest trained categorizer artifact and provides
thread-safe predictions with confidence scores.

If no artifact exists, attempts auto-training once.
If auto-training fails (e.g. missing sklearn), returns None gracefully.
"""

from __future__ import annotations
import logging
import os
import threading
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_pipeline = None  # cached pipeline
_loaded_path: Optional[str] = None
_load_attempted = False


CONFIDENCE_THRESHOLD = 0.45  # below this → return "Other" with low confidence flag


def _find_latest_artifact() -> Optional[str]:
    """Return path of the newest categorizer artifact or None."""
    artifacts_dir = os.path.join(os.path.dirname(__file__), "..", "artifacts")
    if not os.path.isdir(artifacts_dir):
        return None
    files = [
        f for f in os.listdir(artifacts_dir)
        if f.startswith("categorizer_") and f.endswith(".joblib")
    ]
    if not files:
        return None
    files.sort(reverse=True)  # newest first by timestamp in name
    return os.path.join(artifacts_dir, files[0])


def _load_model() -> bool:
    """Load the model into the module-level cache. Returns True on success."""
    global _pipeline, _loaded_path, _load_attempted
    path = _find_latest_artifact()
    if path is None:
        # Try auto-training
        logger.info("[Categorizer] No artifact found — attempting auto-training.")
        try:
            from app.ml.training.train_categorizer import train_and_save
            train_and_save(verbose=False)
            path = _find_latest_artifact()
        except Exception as exc:
            logger.warning("[Categorizer] Auto-training failed: %s", exc)
            _load_attempted = True
            return False

    if path is None:
        _load_attempted = True
        return False

    try:
        import joblib
        _pipeline = joblib.load(path)
        _loaded_path = path
        logger.info("[Categorizer] Loaded artifact: %s", path)
        _load_attempted = True
        return True
    except Exception as exc:
        logger.error("[Categorizer] Failed to load artifact %s: %s", path, exc)
        _load_attempted = True
        return False


def get_model():
    """Return the loaded pipeline, attempting load on first call."""
    global _load_attempted
    with _lock:
        if _pipeline is not None:
            return _pipeline
        if not _load_attempted:
            _load_model()
        return _pipeline


def predict(text: str) -> Tuple[Optional[str], float, bool]:
    """
    Classify a transaction description.

    Returns:
        (category, confidence, model_used)
        - category: predicted label or None if model unavailable
        - confidence: 0.0–1.0
        - model_used: True if ML model ran, False if unavailable
    """
    model = get_model()
    if model is None:
        return None, 0.0, False

    try:
        import numpy as np
        probs = model.predict_proba([text])[0]
        classes = model.classes_
        idx = int(np.argmax(probs))
        confidence = float(probs[idx])
        category = classes[idx]

        if confidence < CONFIDENCE_THRESHOLD:
            return "Other", confidence, True

        return category, confidence, True
    except Exception as exc:
        logger.error("[Categorizer] Prediction error: %s", exc)
        return None, 0.0, False


def predict_batch(texts: list) -> list:
    """
    Predict categories for a list of descriptions.
    Returns list of dicts: {category, confidence, model_used}.
    """
    model = get_model()
    if model is None:
        return [{"category": None, "confidence": 0.0, "model_used": False} for _ in texts]

    try:
        import numpy as np
        probs = model.predict_proba(texts)
        classes = model.classes_
        results = []
        for prob_row in probs:
            idx = int(np.argmax(prob_row))
            conf = float(prob_row[idx])
            cat = classes[idx] if conf >= CONFIDENCE_THRESHOLD else "Other"
            results.append({"category": cat, "confidence": round(conf, 4), "model_used": True})
        return results
    except Exception as exc:
        logger.error("[Categorizer] Batch prediction error: %s", exc)
        return [{"category": None, "confidence": 0.0, "model_used": False} for _ in texts]


def model_info() -> dict:
    """Return info about the currently loaded model."""
    from app.ml import model_registry
    reg = model_registry.get("categorizer")
    return {
        "loaded": _pipeline is not None,
        "artifact_path": _loaded_path,
        "registry": reg,
    }
