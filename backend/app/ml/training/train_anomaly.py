"""
FinMind AI — Model B Training Script: Anomaly Detector
=======================================================
Algorithm : Isolation Forest (unsupervised) + IQR statistical baseline
Dataset   : User transaction history (fit at inference time per-user)
Run       : python -m app.ml.training.train_anomaly  (fits general model)

The general model is trained on synthetic transaction features to bootstrap
cold-start users. Per-user fine-tuning happens during inference when enough
history exists (MIN_USER_TRANSACTIONS threshold).
"""

from __future__ import annotations
import os
import sys
import datetime
import json
import logging

logger = logging.getLogger(__name__)

MIN_USER_TRANSACTIONS = 30   # minimum records to fit a user-specific model


def build_general_model(verbose: bool = True) -> dict:
    """
    Fit an Isolation Forest on synthetic transaction feature vectors.
    This provides a cold-start fallback for new users.
    Returns evaluation summary dict.
    """
    try:
        import numpy as np
        import joblib
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline
    except ImportError as e:
        raise RuntimeError(f"ML dependencies missing: {e}") from e

    from app.ml import model_registry

    rng = np.random.default_rng(42)

    # Synthetic normal transactions (n=500)
    normal = np.column_stack([
        rng.lognormal(mean=9.0, sigma=0.8, size=500),   # log-amount (INR ~8k median)
        rng.uniform(0, 1, size=500),                      # is_debit
        rng.uniform(0, 1, size=500),                      # is_weekend
        rng.uniform(8, 20, size=500),                     # hour (business hours)
        rng.uniform(0, 0.3, size=500),                    # velocity_score
        rng.uniform(0, 0.2, size=500),                    # merchant_novelty
        rng.uniform(0.8, 1.2, size=500),                  # amount_ratio_vs_category_mean
    ])

    # Synthetic anomalous transactions (n=50) for reference only (unsupervised)
    anomalies = np.column_stack([
        rng.lognormal(mean=13.0, sigma=0.3, size=50),    # very large amounts
        rng.integers(0, 2, size=50).astype(float),
        rng.integers(0, 2, size=50).astype(float),
        rng.uniform(0, 5, size=50),                       # unusual hours (late night)
        rng.uniform(0.7, 1.0, size=50),                   # high velocity
        rng.uniform(0.8, 1.0, size=50),                   # new merchants
        rng.uniform(3.0, 8.0, size=50),                   # 3-8x category mean
    ])

    X_train = normal   # Isolation Forest trains on normal data

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("iforest", IsolationForest(
            n_estimators=150,
            contamination=0.05,
            max_samples="auto",
            random_state=42,
            n_jobs=-1,
        )),
    ])
    pipeline.fit(X_train)

    # Evaluate: normal data should mostly predict +1, anomalies -1
    normal_preds = pipeline.predict(normal)
    anomaly_preds = pipeline.predict(anomalies)
    normal_recall = float((normal_preds == 1).mean())
    anomaly_detection_rate = float((anomaly_preds == -1).mean())

    if verbose:
        print(f"[Anomaly] Normal recall     : {normal_recall:.3f}")
        print(f"[Anomaly] Anomaly det. rate : {anomaly_detection_rate:.3f}")

    artifacts_dir = os.path.join(os.path.dirname(__file__), "..", "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)
    version = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    artifact_path = os.path.abspath(
        os.path.join(artifacts_dir, f"anomaly_general_v{version}.joblib")
    )
    joblib.dump(pipeline, artifact_path)

    metrics = {
        "normal_recall": round(normal_recall, 4),
        "anomaly_detection_rate_synthetic": round(anomaly_detection_rate, 4),
        "n_train_normal": len(normal),
        "n_train_anomaly_ref": len(anomalies),
        "contamination": 0.05,
        "note": (
            "Isolation Forest trained on synthetic normal transactions. "
            "Anomaly detection rate measured on synthetic anomalies — "
            "not confirmed fraud labels. Labels: suspicious/anomalous only."
        ),
    }

    model_registry.register(
        model_name="anomaly_general",
        artifact_path=artifact_path,
        version=f"v{version}",
        metrics=metrics,
        features=["log_amount", "is_debit", "is_weekend", "hour", "velocity_score",
                  "merchant_novelty", "amount_ratio_vs_category_mean"],
        dataset_source="synthetic_normal_n500 (app/ml/training/train_anomaly.py)",
        notes="Isolation Forest general model; cold-start fallback; not fraud labels",
    )

    if verbose:
        print(f"[Anomaly] Artifact saved → {artifact_path}")

    return metrics


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    result = build_general_model(verbose=True)
    print(json.dumps(result, indent=2))
