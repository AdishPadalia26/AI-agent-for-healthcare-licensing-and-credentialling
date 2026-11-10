"""Hybrid retrieval over provider document chunks and human-confirmed field mappings.

Elasticsearch is the production store. Keyword and vector results are fused client side
with reciprocal rank fusion because the server-side RRF retriever needs a paid license.
"""
from __future__ import annotations

import hashlib
import logging
import math
import re
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from .config import Settings
from .llm import EMBEDDING_DIMS

log = logging.getLogger(__name__)
CHUNK_INDEX = "provider_chunks"
MAPPING_INDEX = "confirmed_mappings"
_RRF_K = 60


@dataclass(frozen=True)
class Confirmed:
    descriptor: str
    chosen_key: str
    score: float


class RetrievalStore(Protocol):
    def index_chunks(self, job_id: str, chunks: list[str]) -> None: ...
    def search_chunks(self, job_id: str, query: str, k: int = 3) -> list[str]: ...
    def add_confirmed(self, descriptor: str, chosen_key: str) -> None: ...
    def search_confirmed(self, query: str, k: int = 3) -> list[Confirmed]: ...
    def purge_job(self, job_id: str) -> None: ...


def chunk_lines(lines: list[str], max_chars: int = 500) -> list[str]:
    chunks, current, size = [], [], 0
    for line in lines:
        if size + len(line) > max_chars and current:
            chunks.append("\n".join(current))
            current, size = [], 0
        current.append(line)
        size += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks


def rrf(rankings: list[list[str]], k: int = _RRF_K) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    return scores


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / ((math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))) or 1.0)


def _similarity(a: str, b: str) -> float:
    left, right = _tokens(a), _tokens(b)
    return len(left & right) / len(left | right) if left and right else 0.0


class NullStore:
    def index_chunks(self, job_id, chunks): ...
    def search_chunks(self, job_id, query, k=3): return []
    def add_confirmed(self, descriptor, chosen_key): ...
    def search_confirmed(self, query, k=3): return []
    def purge_job(self, job_id): ...


class InMemoryStore:
    """Same behaviour as Elasticsearch, per process, for local mode and tests."""

    def __init__(self, embed: Callable[[list[str]], list[list[float]]]):
        self._embed = embed
        self._chunks: dict[str, list[tuple[str, list[float]]]] = {}
        self._confirmed: dict[tuple[str, str], list[float]] = {}

    def index_chunks(self, job_id, chunks):
        if chunks:
            self._chunks[job_id] = list(zip(chunks, self._embed(chunks)))

    def search_chunks(self, job_id, query, k=3):
        items = self._chunks.get(job_id, [])
        if not items:
            return []
        vector = self._embed([query])[0]
        keyword = sorted(items, key=lambda i: -len(_tokens(query) & _tokens(i[0])))
        semantic = sorted(items, key=lambda i: -_cosine(vector, i[1]))
        fused = rrf([[i[0] for i in keyword[:k * 3]], [i[0] for i in semantic[:k * 3]]])
        return sorted(fused, key=lambda t: -fused[t])[:k]

    def add_confirmed(self, descriptor, chosen_key):
        self._confirmed[(descriptor, chosen_key)] = self._embed([descriptor])[0]

    def search_confirmed(self, query, k=3):
        ranked = sorted(
            (Confirmed(d, c, _similarity(query, d)) for (d, c) in self._confirmed), key=lambda r: -r.score
        )
        return [r for r in ranked if r.score > 0][:k]

    def purge_job(self, job_id):
        self._chunks.pop(job_id, None)


class ElasticStore:
    def __init__(self, client: Any, embed: Callable[[list[str]], list[list[float]]]):
        self._client = client
        self._embed = embed
        self._ensure_indices()

    def _ensure_indices(self) -> None:
        vector = {"type": "dense_vector", "dims": EMBEDDING_DIMS, "index": True, "similarity": "cosine"}
        definitions = {
            CHUNK_INDEX: {"job_id": {"type": "keyword"}, "text": {"type": "text"}, "vector": vector},
            MAPPING_INDEX: {"descriptor": {"type": "text"}, "chosen_key": {"type": "keyword"}, "vector": vector},
        }
        for name, properties in definitions.items():
            if not self._client.indices.exists(index=name):
                self._client.indices.create(index=name, mappings={"properties": properties})

    def index_chunks(self, job_id, chunks):
        for position, (text, vector) in enumerate(zip(chunks, self._embed(chunks) if chunks else [])):
            self._client.index(
                index=CHUNK_INDEX, id=f"{job_id}:{position}", document={"job_id": job_id, "text": text, "vector": vector}
            )
        self._client.indices.refresh(index=CHUNK_INDEX)

    def search_chunks(self, job_id, query, k=3):
        vector = self._embed([query])[0]
        scope = {"term": {"job_id": job_id}}
        keyword = self._client.search(
            index=CHUNK_INDEX, size=k * 3, query={"bool": {"must": {"match": {"text": query}}, "filter": scope}}
        )
        semantic = self._client.search(
            index=CHUNK_INDEX,
            size=k * 3,
            knn={"field": "vector", "query_vector": vector, "k": k * 3, "num_candidates": 50, "filter": scope},
        )
        texts = [[hit["_source"]["text"] for hit in r["hits"]["hits"]] for r in (keyword, semantic)]
        fused = rrf(texts)
        return sorted(fused, key=lambda t: -fused[t])[:k]

    def add_confirmed(self, descriptor, chosen_key):
        doc_id = hashlib.sha1(f"{descriptor}|{chosen_key}".encode()).hexdigest()
        self._client.index(
            index=MAPPING_INDEX,
            id=doc_id,
            document={"descriptor": descriptor, "chosen_key": chosen_key, "vector": self._embed([descriptor])[0]},
            refresh=True,
        )

    def search_confirmed(self, query, k=3):
        vector = self._embed([query])[0]
        keyword = self._client.search(index=MAPPING_INDEX, size=k * 3, query={"match": {"descriptor": query}})
        semantic = self._client.search(
            index=MAPPING_INDEX, size=k * 3, knn={"field": "vector", "query_vector": vector, "k": k * 3, "num_candidates": 50}
        )
        ids: dict[str, dict[str, Any]] = {}
        rankings: list[list[str]] = []
        for response in (keyword, semantic):
            ranking = []
            for hit in response["hits"]["hits"]:
                ids[hit["_id"]] = hit["_source"]
                ranking.append(hit["_id"])
            rankings.append(ranking)
        fused = rrf(rankings)
        ordered = sorted(fused, key=lambda i: -fused[i])[:k]
        return [
            Confirmed(ids[i]["descriptor"], ids[i]["chosen_key"], _similarity(query, ids[i]["descriptor"]))
            for i in ordered
        ]

    def purge_job(self, job_id):
        self._client.delete_by_query(index=CHUNK_INDEX, query={"term": {"job_id": job_id}}, refresh=True)


class ResilientStore:
    """Retrieval improves mapping but must never be the reason a job fails."""

    def __init__(self, inner: RetrievalStore):
        self._inner = inner
        self.degraded = False

    def _guard(self, method: str, default: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return getattr(self._inner, method)(*args, **kwargs)
        except Exception as exc:
            self.degraded = True
            log.warning("retrieval %s failed: %s", method, type(exc).__name__)
            return default

    def index_chunks(self, job_id, chunks): self._guard("index_chunks", None, job_id, chunks)
    def search_chunks(self, job_id, query, k=3): return self._guard("search_chunks", [], job_id, query, k)
    def add_confirmed(self, descriptor, chosen_key): self._guard("add_confirmed", None, descriptor, chosen_key)
    def search_confirmed(self, query, k=3): return self._guard("search_confirmed", [], query, k)
    def purge_job(self, job_id): self._guard("purge_job", None, job_id)


def build_store(settings: Settings, embed: Callable[[list[str]], list[list[float]]]) -> RetrievalStore:
    if not settings.elasticsearch_url:
        return InMemoryStore(embed)
    try:
        from elasticsearch import Elasticsearch

        client = Elasticsearch(settings.elasticsearch_url, api_key=settings.elasticsearch_api_key)
        return ResilientStore(ElasticStore(client, embed))
    except Exception as exc:
        log.warning("Elasticsearch unavailable, continuing without retrieval: %s", type(exc).__name__)
        return NullStore()
