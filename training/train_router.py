"""Train a lightweight TF-IDF + LogisticRegression router — M3 fine-tune.

Reads training/router_training_data.csv (produced by prepare_router_data.py),
trains a binary classifier (invoice vs bank_statement) on the first-page text
of each document, and saves the model artifacts to training/artifacts/.

The router node (services/api/nodes/router.py) loads these artifacts at
startup. When present it classifies using CPU inference in <1 ms — no VLM
call, no token cost. Falls back to the VLM router if artifacts are absent.

Usage (after running prepare_router_data.py):
    uv run python training/train_router.py

Outputs:
    training/artifacts/router_tfidf.pkl    -- TF-IDF vectoriser
    training/artifacts/router_clf.pkl      -- LogisticRegression classifier
    training/artifacts/router_meta.json   -- eval metrics + training metadata
"""

from __future__ import annotations

import json
import pickle
import time
from pathlib import Path

_REPO = Path(__file__).parent.parent
_DATA = Path(__file__).parent / "router_training_data.csv"
_ARTIFACTS = Path(__file__).parent / "artifacts"


def main() -> None:
    import csv

    import sklearn
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import classification_report
    from sklearn.model_selection import StratifiedKFold, cross_val_score

    if not _DATA.exists():
        raise FileNotFoundError(
            f"{_DATA} not found — run `uv run python training/prepare_router_data.py` first"
        )

    with _DATA.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    texts = [r["text"] for r in rows]
    labels = [r["label"] for r in rows]

    if len(texts) < 10:
        raise ValueError(f"Only {len(texts)} examples — not enough to train")

    print(f"Loaded {len(texts)} examples")
    by_type: dict[str, int] = {}
    for lbl in labels:
        by_type[lbl] = by_type.get(lbl, 0) + 1
    for t, n in sorted(by_type.items()):
        print(f"  {t}: {n}")

    # ── 5-fold cross-validation to get a reliable accuracy estimate ───────────
    tfidf = TfidfVectorizer(max_features=1000, stop_words="english", ngram_range=(1, 2))
    clf = LogisticRegression(max_iter=500, C=1.0, random_state=42)

    from sklearn.pipeline import Pipeline

    pipe = Pipeline([("tfidf", tfidf), ("clf", clf)])

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(pipe, texts, labels, cv=cv, scoring="accuracy")
    print(f"\n5-fold CV accuracy: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")
    print(f"  per-fold: {[f'{s:.4f}' for s in cv_scores]}")

    # ── Fit on full corpus, save artifacts ────────────────────────────────────
    t0 = time.monotonic()
    pipe.fit(texts, labels)
    train_s = time.monotonic() - t0

    # sanity-check: predict on train set
    preds = pipe.predict(texts)
    train_acc = sum(p == g for p, g in zip(preds, labels)) / len(labels)
    print(f"\nTrain-set accuracy (full corpus): {train_acc:.4f}")
    print(classification_report(labels, preds, target_names=sorted(set(labels))))

    _ARTIFACTS.mkdir(parents=True, exist_ok=True)
    tfidf_path = _ARTIFACTS / "router_tfidf.pkl"
    clf_path = _ARTIFACTS / "router_clf.pkl"
    meta_path = _ARTIFACTS / "router_meta.json"

    tfidf_path.write_bytes(pickle.dumps(pipe.named_steps["tfidf"]))
    clf_path.write_bytes(pickle.dumps(pipe.named_steps["clf"]))

    meta = {
        "sklearn_version": sklearn.__version__,
        "n_examples": len(texts),
        "classes": sorted(set(labels)),
        "cv_accuracy_mean": float(cv_scores.mean()),
        "cv_accuracy_std": float(cv_scores.std()),
        "train_accuracy": float(train_acc),
        "train_time_s": round(train_s, 4),
        "model": "TfidfVectorizer(max_features=1000, ngram_range=(1,2)) + LogisticRegression",
        "vlm_baseline_accuracy": 1.0,
        "vlm_baseline_docs": 130,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"\nArtifacts written to {_ARTIFACTS.relative_to(_REPO)}/")
    print(f"  router_tfidf.pkl  ({tfidf_path.stat().st_size // 1024} KB)")
    print(f"  router_clf.pkl    ({clf_path.stat().st_size // 1024} KB)")
    print("  router_meta.json")

    print("\nVLM baseline : 100.0% on 130/130 docs (~2743 tokens/call)")
    print(f"Fine-tuned   : {cv_scores.mean():.1%} CV accuracy,  0 tokens/call, <1 ms/doc")


if __name__ == "__main__":
    main()
