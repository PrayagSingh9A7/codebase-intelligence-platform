from __future__ import annotations

from typing import Sequence
import hashlib
import re

import numpy as np


class Embedder:
    """
    Lightweight, dependency-free local embeddings for small Render instances.

    This intentionally does not import sentence-transformers / PyTorch.
    The previous implementation loaded a Torch + CUDA stack at API startup,
    which can exceed Render's 512 MiB memory limit.

    The vectors are deterministic and normalized, so they remain compatible
    with the existing vector-store interface.
    """

    dimension = 384

    def __init__(self) -> None:
        pass

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return re.findall(r"[A-Za-z_][A-Za-z0-9_./:-]{1,63}", text.lower())

    def _encode_one(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dimension, dtype=np.float32)

        tokens = self._tokens(text)
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.blake2b(
                token.encode("utf-8"),
                digest_size=16,
            ).digest()

            idx = int.from_bytes(digest[:4], "little") % self.dimension
            sign = 1.0 if (digest[4] & 1) else -1.0
            weight = 1.0 + (digest[5] / 255.0)

            vector[idx] += sign * weight

            # Second hashed feature reduces collisions for short code symbols.
            idx2 = int.from_bytes(digest[8:12], "little") % self.dimension
            vector[idx2] += sign * 0.5

        norm = float(np.linalg.norm(vector))
        if norm:
            vector /= norm

        return vector

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        return np.asarray(
            [self._encode_one(text) for text in texts],
            dtype=np.float32,
        )git add apps/api/requirements.txt apps/api/app/services/embeddings.py
git commit -m "reduce backend memory usage for Render"
git push