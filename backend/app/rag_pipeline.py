from __future__ import annotations
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger("truthlens.rag_pipeline")


@dataclass
class RetrievedDoc:
    content: str
    source: str
    relevance: float


class RagPipeline:
    COLLECTION_NAME = "truthlens_knowledge"
    TOP_K = 5
    WIKIPEDIA_MAX_CHARS = 1200

    def __init__(self):
        self._chroma_client = None
        self._collection = None
        self._init_chroma()
        self._seed_corpus()

    def _init_chroma(self):
        try:
            import chromadb
            from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
            persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
            self._chroma_client = chromadb.PersistentClient(path=persist_dir)
            self._collection = self._chroma_client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                embedding_function=DefaultEmbeddingFunction(),
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("ChromaDB ready. %d docs.", self._collection.count())
        except Exception as e:
            logger.warning("ChromaDB init failed: %s", e)

    def _seed_corpus(self):
        if self._collection is None or self._collection.count() > 0:
            return
        seed_docs = [
            {"id": "seed_001", "text": "Climate change is caused primarily by human activities since the mid-20th century, especially burning fossil fuels.", "source": "IPCC 2021"},
            {"id": "seed_002", "text": "mRNA COVID-19 vaccines were tested on tens of thousands of participants before emergency authorisation.", "source": "WHO 2022"},
            {"id": "seed_003", "text": "The 2020 US presidential election was certified by all 50 states with no evidence of widespread fraud.", "source": "US Election Council 2020"},
            {"id": "seed_004", "text": "The Apollo 11 moon landing in 1969 has been verified by independent space agencies worldwide.", "source": "NASA"},
            {"id": "seed_005", "text": "There is no scientific evidence linking 5G towers to COVID-19 or any health hazards at regulatory exposure levels.", "source": "WHO EMF 2020"},
        ]
        self._collection.add(
            ids=[d["id"] for d in seed_docs],
            documents=[d["text"] for d in seed_docs],
            metadatas=[{"source": d["source"]} for d in seed_docs],
        )
        logger.info("Seeded %d documents.", len(seed_docs))

    def _fetch_wikipedia(self, claim):
        try:
            import urllib.request
            import urllib.parse
            import json
            query = urllib.parse.quote(claim[:120])
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{query}"
            req = urllib.request.Request(url, headers={"User-Agent": "TruthLensAI/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            summary = data.get("extract", "")[:self.WIKIPEDIA_MAX_CHARS]
            page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
            if summary:
                return [RetrievedDoc(content=summary, source=page_url or "Wikipedia", relevance=0.75)]
        except Exception as e:
            logger.debug("Wikipedia fetch failed: %s", e)
        return []

    def _chroma_retrieve(self, claim, top_k):
        if self._collection is None:
            return []
        try:
            n = min(top_k, self._collection.count())
            if n == 0:
                return []
            results = self._collection.query(
                query_texts=[claim],
                n_results=n,
                include=["documents", "metadatas", "distances"],
            )
            docs = []
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                docs.append(RetrievedDoc(
                    content=doc,
                    source=meta.get("source", "KB"),
                    relevance=max(0.0, 1.0 - dist),
                ))
            return docs
        except Exception as e:
            logger.error("ChromaDB query failed: %s", e)
            return []

    def ingest(self, doc_id, text, source):
        if self._collection:
            self._collection.upsert(
                ids=[doc_id],
                documents=[text],
                metadatas=[{"source": source}],
            )

    def retrieve(self, claim, top_k=5):
        chroma_docs = self._chroma_retrieve(claim, top_k)
        wiki_docs = self._fetch_wikipedia(claim)
        all_docs = chroma_docs + wiki_docs
        seen, unique = set(), []
        for d in all_docs:
            k = d.content[:80]
            if k not in seen:
                seen.add(k)
                unique.append(d)
        unique.sort(key=lambda d: d.relevance, reverse=True)
        return unique[:top_k]