"""Semantic retrieval with optional neural embeddings and a native fallback.

Backends, in order of preference:

* ``sentence-transformers`` (Apache-2.0) — configurable lightweight bi-encoder,
  CPU inference, lazy-loaded.
* ``FlagEmbedding`` / BGE (MIT) — optional alternative embedding model.
* deterministic TF-IDF cosine — always available, no download, no network.

Embeddings from neural backends are cached on disk keyed by
``model + sha256(texts)`` so repeated assessments do not re-encode the same
text. The result is only used for **retrieval/ranking**; it never overrides the
conservative evidence status rules or invents evidence.
"""
from __future__ import annotations

import hashlib
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from app.core.config import settings
from app.core.logging import get_logger
from app.services.evidence import EvidenceRecord

logger = get_logger("semantic")

_CACHE: dict[str, np.ndarray] = {}


@dataclass
class BackendInfo:
    backend: str
    model: str
    available: bool
    requested: str
    fallback_reason: str = ""
    cached: bool = False


class _Backend:
    name = "base"
    model = ""
    available = True
    reason = ""

    def encode(self, texts: list[str]) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError

    def transform(self, texts: list[str]) -> np.ndarray:  # pragma: no cover - interface
        return self.encode(texts)


class TfidfBackend(_Backend):
    """Deterministic lexical embedding fallback (word + character n-grams)."""

    name = "tfidf"
    model = "word(1,2)+char_wb(3,5) tf-idf cosine"
    available = True

    def __init__(self) -> None:
        self._vectorizer: Any = None

    def fit(self, corpus: list[str]) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=1,
            max_features=30000,
            analyzer="word",
        ).fit(corpus)

    def encode(self, texts: list[str]) -> np.ndarray:
        if self._vectorizer is None:
            self.fit(texts or [""])
        return self.transform(texts)

    def transform(self, texts: list[str]) -> np.ndarray:
        from sklearn.preprocessing import normalize

        if self._vectorizer is None:
            self.fit(texts or [""])
        matrix = self._vectorizer.transform(texts)
        return np.asarray(normalize(matrix).toarray(), dtype=np.float64)


class SentenceTransformerBackend(_Backend):
    name = "sentence-transformers"

    def __init__(self, model_name: str) -> None:
        self.model = model_name
        self.available = importlib.util.find_spec("sentence_transformers") is not None
        self.reason = (
            ""
            if self.available
            else "sentence-transformers is not installed; using the native TF-IDF fallback."
        )
        self._model: Any = None

    def _ensure(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # type: ignore

            logger.info("Loading embedding model %s on CPU", self.model)
            self._model = SentenceTransformer(self.model, device="cpu")
        return self._model

    def encode(self, texts: list[str]) -> np.ndarray:
        model = self._ensure()
        vectors = model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return np.asarray(vectors, dtype=np.float64)


class BgeBackend(_Backend):
    name = "bge"

    def __init__(self, model_name: str) -> None:
        self.model = model_name
        self.available = importlib.util.find_spec("FlagEmbedding") is not None
        self.reason = (
            ""
            if self.available
            else "FlagEmbedding is not installed; using the native TF-IDF fallback."
        )
        self._model: Any = None

    def _ensure(self) -> Any:
        if self._model is None:
            from FlagEmbedding import FlagModel  # type: ignore

            logger.info("Loading BGE embedding model %s on CPU", self.model)
            self._model = FlagModel(self.model, use_fp16=False, device="cpu")
        return self._model

    def encode(self, texts: list[str]) -> np.ndarray:
        model = self._ensure()
        result = model.encode(texts, batch_size=16)
        if isinstance(result, dict):
            result = result.get("dense_vecs", result.get("embeddings"))
        vectors = np.asarray(result, dtype=np.float64)
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms


def _cache_path(key: str) -> Path:
    return Path(settings.EMBEDDING_CACHE_DIR) / f"{key}.npy"


def _cached_encode(backend: _Backend, texts: list[str]) -> tuple[np.ndarray, bool]:
    """Encode with an on-disk cache; returns (vectors, cache_hit)."""
    digest = hashlib.sha256()
    digest.update(f"{backend.name}|{backend.model}|".encode("utf-8"))
    for text in texts:
        digest.update(text.encode("utf-8", errors="replace"))
        digest.update(b"\x00")
    key = digest.hexdigest()
    if key in _CACHE:
        return _CACHE[key], True

    path = _cache_path(key)
    if path.is_file():
        try:
            vectors = np.load(path)
            _CACHE[key] = vectors
            return vectors, True
        except Exception as exc:  # noqa: BLE001 - corrupt cache is non-fatal
            logger.warning("Ignoring unreadable embedding cache %s: %s", path, exc)

    vectors = backend.encode(texts)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, vectors)
    except OSError as exc:  # pragma: no cover - read-only filesystem
        logger.debug("Could not write embedding cache: %s", exc)
    _CACHE[key] = vectors
    return vectors, False


def select_backend(preferred: str | None = None) -> tuple[_Backend, BackendInfo]:
    """Resolve the configured embedding backend with a documented fallback."""
    requested = (preferred or settings.EMBEDDING_BACKEND or "auto").strip().lower()

    if requested in {"tfidf", "native", "lexical"}:
        return TfidfBackend(), BackendInfo(
            backend="tfidf",
            model=TfidfBackend.model,
            available=True,
            requested=requested,
            fallback_reason="",
        )

    candidates: list[_Backend] = []
    if requested in {"sentence-transformers", "st", "sentence_transformers"}:
        candidates.append(SentenceTransformerBackend(settings.EMBEDDING_MODEL))
    elif requested in {"bge", "flagembedding", "flag"}:
        model = settings.EMBEDDING_MODEL
        if "bge" not in model.lower():
            model = "BAAI/bge-small-en-v1.5"
        candidates.append(BgeBackend(model))
    else:
        # auto: prefer sentence-transformers, then BGE, then TF-IDF.
        candidates.append(SentenceTransformerBackend(settings.EMBEDDING_MODEL))
        bge_model = settings.EMBEDDING_MODEL
        if "bge" not in bge_model.lower():
            bge_model = "BAAI/bge-small-en-v1.5"
        candidates.append(BgeBackend(bge_model))

    reasons: list[str] = []
    for candidate in candidates:
        if candidate.available:
            return candidate, BackendInfo(
                backend=candidate.name,
                model=candidate.model,
                available=True,
                requested=requested,
                fallback_reason="",
            )
        if candidate.reason:
            reasons.append(candidate.reason)

    reason = " ".join(dict.fromkeys(reasons)) or (
        "No neural embedding backend is available; deterministic TF-IDF cosine "
        "retrieval is in use."
    )
    return TfidfBackend(), BackendInfo(
        backend="tfidf",
        model=TfidfBackend.model,
        available=True,
        requested=requested,
        fallback_reason=reason,
    )


def _cosine(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    left = np.asarray(left, dtype=np.float64)
    right = np.asarray(right, dtype=np.float64)
    if left.ndim == 1:
        left = left.reshape(1, -1)
    if right.ndim == 1:
        right = right.reshape(1, -1)
    left_norm = left / np.clip(np.linalg.norm(left, axis=1, keepdims=True), 1e-12, None)
    right_norm = right / np.clip(np.linalg.norm(right, axis=1, keepdims=True), 1e-12, None)
    return np.clip(left_norm @ right_norm.T, -1.0, 1.0)


def _milestone_queries(framework: Any) -> list[tuple[str, str]]:
    queries: list[tuple[str, str]] = []
    for milestone in framework.milestones:
        parts = [
            str(milestone.get("label", "")),
            str(milestone.get("description", "")),
            *[str(x) for x in milestone.get("defining_indicators", [])],
        ]
        queries.append((str(milestone["id"]), " ".join(p for p in parts if p)))
    return queries


def _similarity_matrix(
    backend: _Backend, corpus: list[str], queries: list[str]
) -> tuple[np.ndarray, bool]:
    if isinstance(backend, TfidfBackend):
        backend.fit(list(corpus) + list(queries))
        corpus_vectors = backend.transform(corpus)
        query_vectors = backend.transform(queries)
        return _cosine(query_vectors, corpus_vectors), False
    corpus_vectors, hit_corpus = _cached_encode(backend, corpus)
    query_vectors, hit_queries = _cached_encode(backend, queries)
    return _cosine(query_vectors, corpus_vectors), hit_corpus and hit_queries


def _empty_retrieval(info: BackendInfo) -> dict[str, Any]:
    return {
        "enabled": False,
        "method": info.backend,
        "model": info.model,
        "backend": info.backend,
        "cached": False,
        "fallback_reason": info.fallback_reason,
        "by_milestone": [],
        "note": "Semantic retrieval is disabled; keyword/indicator matching is used.",
    }


def rank_evidence(
    evidence: list[EvidenceRecord],
    framework: Any,
    top_k: int = 5,
    preferred: str | None = None,
) -> dict[str, Any]:
    """Rank evidence against every milestone using cosine similarity.

    The learned similarity is attached to each evidence record as
    ``semantic_similarity`` / ``semantic_milestone`` (re-ranking only) and a
    per-milestone retrieval list is returned for the API/UI.
    """
    backend, info = select_backend(preferred)
    if not settings.SEMANTIC_RETRIEVAL or not evidence:
        return _empty_retrieval(info)

    queries = _milestone_queries(framework)
    if not queries:
        return _empty_retrieval(info)

    corpus = [item.statement for item in evidence]
    try:
        matrix, cached = _similarity_matrix(
            backend, corpus, [text for _, text in queries]
        )
    except Exception as exc:  # noqa: BLE001 - never break an assessment
        logger.error("Semantic retrieval failed (%s); continuing without it", exc)
        fallback_info = BackendInfo(
            backend=info.backend,
            model=info.model,
            available=True,
            requested=info.requested,
            fallback_reason=f"Retrieval failed ({type(exc).__name__}); keyword matching only.",
        )
        return _empty_retrieval(fallback_info)

    milestone_ids = [milestone_id for milestone_id, _ in queries]
    # Attach the best matching milestone to each evidence item.
    for index, item in enumerate(evidence):
        scores = matrix[:, index]
        best_index = int(np.argmax(scores)) if scores.size else -1
        if best_index >= 0:
            item.semantic_similarity = round(float(scores[best_index]), 4)
            item.semantic_milestone = milestone_ids[best_index]

    by_milestone: list[dict[str, Any]] = []
    for query_index, milestone_id in enumerate(milestone_ids):
        scores = matrix[query_index]
        order = np.argsort(-scores)[: max(1, top_k)]
        matches = []
        for evidence_index in order:
            score = float(scores[evidence_index])
            if score <= 0:
                continue
            item = evidence[evidence_index]
            matches.append(
                {
                    "evidence_id": item.id,
                    "statement": item.statement,
                    "source_document": item.source_document,
                    "page_number": item.page_number,
                    "location": item.location,
                    "status": item.status,
                    "similarity": round(score, 4),
                }
            )
        by_milestone.append(
            {"milestone": milestone_id, "matches": matches}
        )

    return {
        "enabled": True,
        "method": info.backend,
        "model": info.model,
        "backend": info.backend,
        "cached": cached,
        "fallback_reason": info.fallback_reason,
        "by_milestone": by_milestone,
        "note": (
            "Similarity ranks how closely an excerpt matches a milestone's "
            "description. It does not change the conservative evidence status "
            "(confirmed/proposed/contradicted/unclear)."
        ),
    }
