from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .embeddings import Embedder
from .vector_store import LocalVectorStore


@dataclass
class RetrievalEngine:
    embedder: Embedder
    store: LocalVectorStore

    def index(self, files: list[dict[str, str]]) -> int:
        payloads: list[dict[str, Any]] = []
        texts: list[str] = []

        for file in files:
            raw = file.get("text", "")
            path = file.get("path", "")

            if not raw.strip():
                continue

            # Slight overlap so important code isn't cut exactly
            # at chunk boundaries.
            chunk_size = 1800
            step = 1450

            chunks = [
                raw[i : i + chunk_size]
                for i in range(0, len(raw), step)
            ]

            if not chunks:
                chunks = [""]

            for idx, chunk in enumerate(chunks):
                texts.append(chunk)

                payloads.append(
                    {
                        "path": path,
                        "chunk": idx,
                        "text": chunk,
                    }
                )

        if not texts:
            return 0

        vectors = self.embedder.encode(texts)

        self.store.upsert(
            vectors,
            payloads,
        )

        return len(texts)

    @staticmethod
    def _tokens(text: str) -> set[str]:
        stopwords = {
            "the",
            "and",
            "are",
            "what",
            "where",
            "which",
            "how",
            "does",
            "this",
            "that",
            "with",
            "from",
            "into",
            "used",
            "use",
            "main",
            "show",
            "tell",
            "give",
            "application",
            "repository",
            "repo",
        }

        tokens = re.findall(
            r"[a-zA-Z_][a-zA-Z0-9_]{2,}",
            text.lower(),
        )

        return {
            token
            for token in tokens
            if token not in stopwords
        }

    @classmethod
    def _lexical_score(
        cls,
        query: str,
        payload: dict[str, Any],
    ) -> float:

        query_tokens = cls._tokens(query)

        if not query_tokens:
            return 0.0

        path = str(payload.get("path", "")).lower()
        text = str(payload.get("text", "")).lower()

        path_tokens = cls._tokens(path)
        text_tokens = cls._tokens(text)

        path_matches = len(query_tokens & path_tokens)
        text_matches = len(query_tokens & text_tokens)

        # Path matches are stronger because a question such as
        # "what is in server.js" should strongly favor server.js.
        return (
            path_matches * 0.35
            + min(text_matches, 8) * 0.08
        )

    @staticmethod
    def _intent_boost(
        query: str,
        payload: dict[str, Any],
    ) -> float:

        q = query.lower()
        path = str(payload.get("path", "")).lower()
        text = str(payload.get("text", "")).lower()

        boost = 0.0

        # Entrypoint/startup questions
        if any(
            word in q
            for word in (
                "entrypoint",
                "entry point",
                "start",
                "startup",
                "bootstrap",
                "main",
                "server",
            )
        ):
            if any(
                name in path
                for name in (
                    "server.",
                    "main.",
                    "index.",
                    "app.",
                    "vite.config",
                    "next.config",
                )
            ):
                boost += 0.25

            if any(
                signal in text
                for signal in (
                    "app.listen",
                    "createapp",
                    "fastapi(",
                    "uvicorn",
                    "root.render",
                    "next(",
                    "express(",
                )
            ):
                boost += 0.20

        # Technology/stack questions
        if any(
            word in q
            for word in (
                "technology",
                "technologies",
                "tech stack",
                "stack",
                "framework",
                "language",
                "dependencies",
            )
        ):
            if path.endswith("package.json"):
                boost += 0.35

            if path.endswith(
                (
                    "requirements.txt",
                    "pyproject.toml",
                    "package-lock.json",
                )
            ):
                boost += 0.30

            if any(
                marker in path
                for marker in (
                    "config",
                    "dockerfile",
                    "readme",
                )
            ):
                boost += 0.12

        # API/route questions
        if any(
            word in q
            for word in (
                "api",
                "route",
                "endpoint",
                "request",
                "response",
            )
        ):
            if any(
                marker in path
                for marker in (
                    "route",
                    "routes",
                    "controller",
                    "api",
                    "server",
                )
            ):
                boost += 0.25

            if any(
                marker in text
                for marker in (
                    "router",
                    "app.get",
                    "app.post",
                    "app.put",
                    "app.delete",
                    "express.router",
                    "@app.get",
                    "@app.post",
                )
            ):
                boost += 0.18

        return boost

    def retrieve(
        self,
        query: str,
        limit: int = 8,
    ) -> list[dict[str, Any]]:

        if not query.strip():
            return []

        # Retrieve a wider candidate pool first.
        vector = self.embedder.encode([query])[0]

        candidate_count = max(
            limit * 4,
            20,
        )

        hits = self.store.search(
            vector,
            limit=candidate_count,
        )

        scored: list[dict[str, Any]] = []

        for hit in hits:
            payload = dict(hit.payload)

            vector_score = float(hit.score)
            lexical_score = self._lexical_score(
                query,
                payload,
            )
            intent_score = self._intent_boost(
                query,
                payload,
            )

            combined = (
                vector_score * 0.62
                + lexical_score
                + intent_score
            )

            payload["score"] = round(
                combined,
                4,
            )

            payload["_vector_score"] = round(
                vector_score,
                4,
            )

            payload["_lexical_score"] = round(
                lexical_score,
                4,
            )

            scored.append(payload)

        scored.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        # Avoid returning many consecutive chunks from the same file
        # unless there are not enough distinct files.
        selected: list[dict[str, Any]] = []
        file_counts: dict[str, int] = {}

        for item in scored:
            path = item["path"]

            count = file_counts.get(path, 0)

            if count >= 2 and len(selected) < limit:
                continue

            selected.append(item)
            file_counts[path] = count + 1

            if len(selected) >= limit:
                break

        return selected