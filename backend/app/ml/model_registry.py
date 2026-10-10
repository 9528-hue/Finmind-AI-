"""
FinMind AI — Model Registry
============================
Tracks artifacts: path, version, training date, metrics, features used.
All entries are loaded from an on-disk JSON registry file.
"""
from __future__ import annotations
import json
import os
import datetime
from typing import Any, Dict, Optional

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
REGISTRY_FILE = os.path.join(ARTIFACTS_DIR, "registry.json")


def _load() -> Dict[str, Any]:
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    if not os.path.exists(REGISTRY_FILE):
        return {}
    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save(data: Dict[str, Any]) -> None:
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    with open(REGISTRY_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)


def register(
    model_name: str,
    artifact_path: str,
    version: str,
    metrics: Dict[str, Any],
    features: list,
    dataset_source: str,
    notes: str = "",
) -> None:
    """Persist model metadata into the registry."""
    data = _load()
    data[model_name] = {
        "version": version,
        "artifact_path": artifact_path,
        "trained_at": datetime.datetime.utcnow().isoformat(),
        "metrics": metrics,
        "features": features,
        "dataset_source": dataset_source,
        "notes": notes,
    }
    _save(data)


def get(model_name: str) -> Optional[Dict[str, Any]]:
    """Return registry entry for a model, or None."""
    return _load().get(model_name)


def list_models() -> Dict[str, Any]:
    return _load()
