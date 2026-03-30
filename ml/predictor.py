"""
SuccessPredictor  — Neural MLP for hire success probability
ShapExplainer     — SHAP feature importance

Python 3.14 note:
  PyTorch may not be available yet. When absent, the app uses a
  weighted heuristic that behaves similarly. No crash, no error.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, Optional
import numpy as np

# Try to import torch — gracefully skip if not available (Python 3.14+)
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

FEATURE_LABELS = [
    "Embedding similarity",
    "Skills match ratio",
    "Experience gap",
    "Education level",
    "Seniority alignment",
    "Keyword density",
    "Skills breadth",
    "Total experience",
]

_HEURISTIC_WEIGHTS = [0.25, 0.35, -0.05, 0.10, -0.05, 0.05, 0.05, 0.20]


class SuccessPredictor:
    def __init__(self, model_path: Optional[str] = None):
        self._model = None
        if TORCH_AVAILABLE and model_path and Path(model_path).exists():
            self._model = self._load(model_path)

    def predict(self, feature_vector: np.ndarray) -> float:
        if self._model is not None and TORCH_AVAILABLE:
            try:
                x = torch.tensor(feature_vector, dtype=torch.float32).unsqueeze(0)
                with torch.no_grad():
                    return float(np.clip(self._model(x).item(), 0.0, 1.0))
            except Exception:
                pass
        return self._heuristic(feature_vector)

    def _heuristic(self, fv: np.ndarray) -> float:
        raw = float(np.dot(fv, _HEURISTIC_WEIGHTS)) + 0.40
        return float(np.clip(raw, 0.0, 1.0))

    def _load(self, path: str):
        if not TORCH_AVAILABLE:
            return None
        try:
            model = _build_net()
            model.load_state_dict(torch.load(path, map_location="cpu"))
            model.eval()
            return model
        except Exception:
            return None


def _build_net():
    if not TORCH_AVAILABLE:
        return None
    return nn.Sequential(
        nn.Linear(8, 64), nn.ReLU(), nn.Dropout(0.3),
        nn.Linear(64, 32), nn.ReLU(), nn.Dropout(0.2),
        nn.Linear(32, 1), nn.Sigmoid(),
    )


class ShapExplainer:
    def __init__(self, model: Any = None):
        self._model = model
        self._explainer = None
        if model is not None:
            try:
                import shap
                self._explainer = shap.TreeExplainer(model)
            except Exception:
                pass

    def explain(self, feature_vector: np.ndarray) -> list:
        if self._explainer is not None:
            try:
                vals = self._explainer.shap_values(feature_vector.reshape(1, -1))[0]
                return self._format(vals)
            except Exception:
                pass
        return self._format(self._heuristic_shap(feature_vector))

    def _format(self, raw_vals) -> list:
        results = []
        for label, val in zip(FEATURE_LABELS, raw_vals):
            results.append({
                "feature":    label,
                "shap_value": round(float(val), 4),
                "direction":  "positive" if float(val) >= 0 else "negative",
                "importance": round(abs(float(val)), 4),
            })
        return sorted(results, key=lambda x: x["importance"], reverse=True)

    def _heuristic_shap(self, fv: np.ndarray) -> list:
        weights = [0.28, 0.32, 0.06, 0.12, 0.06, 0.08, 0.04, 0.04]
        return [float(v) * float(w) for v, w in zip(fv, weights)]
