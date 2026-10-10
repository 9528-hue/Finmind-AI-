"""
FinMind AI — Model A Training Script: Transaction Categorizer
==============================================================
Algorithm : TF-IDF (char+word n-grams) + Logistic Regression Pipeline
Dataset   : Synthetic labeled examples (app/ml/training/dataset.py)
Run       : python -m app.ml.training.train_categorizer

Outputs   : app/ml/artifacts/categorizer_v{N}.joblib
Evaluation: macro-F1, per-class precision/recall, confusion matrix
"""

from __future__ import annotations
import os
import sys
import datetime
import json
import logging

logger = logging.getLogger(__name__)


def train_and_save(verbose: bool = True) -> dict:
    """
    Train the TF-IDF + LR categorizer and save the artifact.
    Returns a dict with evaluation metrics.
    """
    try:
        import joblib
        import numpy as np
        from sklearn.pipeline import Pipeline
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import StratifiedKFold, cross_val_predict
        from sklearn.metrics import (
            f1_score, precision_score, recall_score,
            confusion_matrix, classification_report,
        )
    except ImportError as e:
        raise RuntimeError(
            f"ML dependencies missing ({e}). "
            "Run: pip install scikit-learn joblib"
        ) from e

    from app.ml.training.dataset import get_training_data, CATEGORY_LABELS
    from app.ml import model_registry

    X, y = get_training_data()
    if verbose:
        print(f"[Categorizer] Training on {len(X)} examples, {len(set(y))} classes")

    # Build pipeline
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 4),
            min_df=1,
            max_features=20_000,
            lowercase=True,
            sublinear_tf=True,
        )),
        ("clf", LogisticRegression(
            max_iter=1000,
            C=5.0,
            multi_class="multinomial",
            solver="lbfgs",
            class_weight="balanced",
        )),
    ])

    # Cross-validated evaluation (5-fold stratified)
    cv = StratifiedKFold(n_splits=min(5, min(len(y) // len(CATEGORY_LABELS), 5)), shuffle=True, random_state=42)
    y_pred_cv = cross_val_predict(pipeline, X, y, cv=cv)

    macro_f1 = float(f1_score(y, y_pred_cv, average="macro", zero_division=0))
    macro_precision = float(precision_score(y, y_pred_cv, average="macro", zero_division=0))
    macro_recall = float(recall_score(y, y_pred_cv, average="macro", zero_division=0))
    report = classification_report(y, y_pred_cv, zero_division=0, output_dict=True)
    cm = confusion_matrix(y, y_pred_cv, labels=sorted(set(y))).tolist()

    if verbose:
        print(f"  CV macro-F1      : {macro_f1:.4f}")
        print(f"  CV macro-Prec    : {macro_precision:.4f}")
        print(f"  CV macro-Recall  : {macro_recall:.4f}")
        print(classification_report(y, y_pred_cv, zero_division=0))

    # Fit final model on ALL data
    pipeline.fit(X, y)

    # Save artifact
    artifacts_dir = os.path.join(os.path.dirname(__file__), "..", "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)
    version = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    artifact_path = os.path.abspath(
        os.path.join(artifacts_dir, f"categorizer_v{version}.joblib")
    )
    joblib.dump(pipeline, artifact_path)

    metrics = {
        "cv_macro_f1": round(macro_f1, 4),
        "cv_macro_precision": round(macro_precision, 4),
        "cv_macro_recall": round(macro_recall, 4),
        "per_class": report,
        "confusion_matrix_labels": sorted(set(y)),
        "confusion_matrix": cm,
        "n_train": len(X),
        "n_classes": len(set(y)),
        "cv_folds": 5,
        "note": "Cross-validated; NOT trained and evaluated on the same split.",
    }

    model_registry.register(
        model_name="categorizer",
        artifact_path=artifact_path,
        version=f"v{version}",
        metrics=metrics,
        features=["tfidf_char_wb_2_4gram", "logistic_regression"],
        dataset_source="synthetic_dataset_v1 (app/ml/training/dataset.py)",
        notes="TF-IDF char n-gram + Logistic Regression; balanced class weights",
    )

    if verbose:
        print(f"[Categorizer] Artifact saved → {artifact_path}")

    return metrics


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Ensure project root is on path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    result = train_and_save(verbose=True)
    print("\nFinal metrics:")
    print(json.dumps({k: v for k, v in result.items() if k not in ("per_class", "confusion_matrix")}, indent=2))
