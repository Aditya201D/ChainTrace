"""Train a demonstrator phishing-website classifier with reproducible artifacts."""
from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import joblib
import mlflow
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from ucimlrepo import fetch_ucirepo

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    source = fetch_ucirepo(id=327)
    X = source.data.features.copy()
    raw_y = source.data.targets.iloc[:, 0].astype(int)
    if set(raw_y.unique()) != {-1, 1}:
        raise RuntimeError(f"Unexpected dataset labels: {sorted(raw_y.unique())}")
    y = (raw_y == -1).astype(int)  # 1 = phishing; 0 = legitimate

    X = X.apply(pd.to_numeric, errors="raise")
    if X.isna().any().any() or len(X.columns) != 30:
        raise RuntimeError("Unexpected missing values or feature count")

    dataset_path = OUT / "phishing_dataset.csv"
    pd.concat([X.reset_index(drop=True), y.rename("is_phishing").reset_index(drop=True)], axis=1).to_csv(
        dataset_path, index=False
    )
    dataset_hash = sha256(dataset_path)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=42
    )

    params = {"n_estimators": 200, "max_depth": 12, "class_weight": "balanced", "random_state": 42, "n_jobs": -1}
    model = RandomForestClassifier(**params)

    mlflow.set_tracking_uri(f"sqlite:///{ROOT / 'mlflow.db'}")
    mlflow.set_experiment("ChainTrace-Phishing-Detection")

    with mlflow.start_run(run_name="phishing-random-forest-v1") as run:
        mlflow.log_params({**params, "test_size": 0.2, "dataset_id": "UCI-327"})
        mlflow.set_tags({"use_case": "phishing website screening", "dataset_sha256": dataset_hash, "positive_class": "phishing"})
        model.fit(X_train, y_train)
        predictions = model.predict(X_test)
        probabilities = model.predict_proba(X_test)[:, list(model.classes_).index(1)]
        metrics = {
            "accuracy": accuracy_score(y_test, predictions),
            "phishing_precision": precision_score(y_test, predictions, zero_division=0),
            "phishing_recall": recall_score(y_test, predictions, zero_division=0),
            "phishing_f1": f1_score(y_test, predictions, zero_division=0),
            "roc_auc": roc_auc_score(y_test, probabilities),
        }
        mlflow.log_metrics(metrics)
        tn, fp, fn, tp = confusion_matrix(y_test, predictions, labels=[0, 1]).ravel()

        model_path = OUT / "phishing_model.joblib"
        joblib.dump(model, model_path)
        model_hash = sha256(model_path)

        manifest = {
            "manifest_version": 1,
            "artifact_type": "TrainingRun",
            "execution_status": "completed",
            "use_case": "phishing website risk classification",
            "dataset_source": "UCI Machine Learning Repository, dataset 327 (Phishing Websites)",
            "dataset_filename": dataset_path.name,
            "dataset_sha256": dataset_hash,
            "model_filename": model_path.name,
            "model_sha256": model_hash,
            "mlflow_run_id": run.info.run_id,
            "algorithm": "RandomForestClassifier",
            "hyperparameters": params,
            "features": list(X.columns),
            "label_mapping": {"0": "legitimate", "1": "phishing"},
            "train_rows": len(X_train),
            "test_rows": len(X_test),
            "metrics": metrics,
            "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
            "environment": {"python": platform.python_version(), "scikit_learn": sklearn.__version__, "pandas": pd.__version__, "mlflow": mlflow.__version__},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "limitations": "Historical benchmark; not independently audited or validated for production deployment.",
        }
        manifest_path = OUT / "training_run_manifest.json"
        save_json(manifest_path, manifest)

        mlflow.log_artifact(str(dataset_path), artifact_path="dataset")
        mlflow.log_artifact(str(model_path), artifact_path="model")
        mlflow.log_artifact(str(manifest_path), artifact_path="provenance")

    print(json.dumps({"run_id": run.info.run_id, "dataset_sha256": dataset_hash, "model_sha256": model_hash, "metrics": metrics, "false_positives": int(fp), "false_negatives": int(fn), "outputs": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
