# Open-source integration evaluation

TRL INSIGHT 2.0 is CPU-first and works with **no network access and no paid
APIs**. The projects below were inspected for licence, compatibility, utility
and resource cost before any code was written. Optional packages are never
required for the app to start, analyse a document or export a report.

| Project | Licence | Decision | Why |
|---|---|---|---|
| [Docling](https://github.com/docling-project/docling) | MIT | **Optional integration** | Layout-aware PDF/DOCX parsing with page provenance, headings, tables and reading order. Used when installed (`TRL_PARSER=auto|docling`); PyMuPDF/pdfplumber/python-docx remain the fallback. |
| [sentence-transformers](https://github.com/UKPLab/sentence-transformers) | Apache-2.0 | **Optional integration** | Configurable lightweight embedding model for milestone/evidence similarity. Lazy loaded, CPU inference, on-disk embedding cache. TF-IDF cosine fallback is always available. |
| [FlagEmbedding / BGE](https://github.com/FlagOpen/FlagEmbedding) | MIT | **Optional integration** | Alternative BGE embeddings for retrieval. Selected explicitly; falls back to sentence-transformers or TF-IDF when unavailable. |
| [SHAP](https://github.com/shap/shap) | MIT | **Optional integration** | Explains the actual classifier's feature contributions. When SHAP is absent, linear models use exact coefficient attribution (clearly labelled). Model explanations are never presented as source evidence. |
| [Haystack](https://github.com/deepset-ai/haystack) | Apache-2.0 | **Not integrated (reference only)** | Evaluated for retrieval/pipelines. The existing deterministic pipeline already provides source-located evidence, rule-based verification and auditable exports. Haystack would add a large dependency surface and a second orchestration model without a new user-facing capability. Its pipeline/retriever patterns informed the semantic retrieval API instead. |
| [OSSTRL](https://github.com/adulau/osstrl) | BSD-2-Clause | **Not reused (methodological reference)** | OSSTRL estimates readiness of an open-source **repository** from GitHub signals (contributors, governance, CI, releases). TRL INSIGHT assesses a **technology** from submitted documents. The evidence/coverage/confidence separation and explicit readiness gates inspired the uncertainty decomposition, but no code was copied. |

## Installation (optional)

```bash
# Layout-aware extraction
pip install "docling>=2.0"

# Semantic embeddings (choose one)
pip install "sentence-transformers>=2.7"
pip install "FlagEmbedding>=1.2"

# True SHAP attribution (falls back cleanly when absent)
pip install "shap>=0.46"
```

The base `requirements.txt` deliberately keeps these commented so the default
install stays small and fast on an ordinary laptop.

## Runtime configuration

| Variable | Default | Meaning |
|---|---|---|
| `TRL_PARSER` | `auto` | `auto` tries Docling when installed, then native extractors; `docling` requires it; `native` skips it. |
| `TRL_SEMANTIC_RETRIEVAL` | `true` | Enable milestone similarity ranking (TF-IDF fallback always works). |
| `TRL_EMBEDDING_BACKEND` | `auto` | `auto`, `sentence-transformers`, `bge` or `tfidf`. |
| `TRL_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model name/path. |
| `TRL_EMBEDDING_CACHE` | `backend/data/embeddings` | On-disk embedding cache directory. |
| `TRL_SHAP_ENABLED` | `true` | Compute model explanations when possible. |

## Attribution

* Docling — MIT, © The Docling Contributors.
* sentence-transformers — Apache-2.0, © Nils Reimers / UKP Lab.
* FlagEmbedding — MIT, © 2022 staoxiao.
* SHAP — MIT, © 2018 Scott Lundberg.
* Haystack — Apache-2.0, © 2021 deepset GmbH.
* OSSTRL — BSD-2-Clause, © Alexandre Dulaunoy / ossbase.org / CIRCL.

No third-party source code has been vendored into this repository. Optional
packages are imported lazily at runtime; if they are absent the app reports the
capability as unavailable and uses its documented fallback.
