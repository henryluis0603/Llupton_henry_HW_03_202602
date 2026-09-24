"""Interfaz comun de embeddings con dos implementaciones (local / OpenAI),
como exige el enunciado: "Your embeddings code must expose one common
interface with two implementations, so that switching models is a
configuration change."

Ambas exponen: .name, .dim, .encode(texts) -> np.ndarray (normalizado,
listo para similitud coseno via producto punto).
"""
from __future__ import annotations

import numpy as np

from .secrets_store import get_openai_api_key


class LocalEmbeddingBackend:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.name = model_name
        self.provider = "local"
        self._model = SentenceTransformer(model_name)
        self.dim = self._model.get_embedding_dimension()

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.array(
            self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False),
            dtype="float32",
        )


class OpenAIEmbeddingBackend:
    """Cliente real de la API de OpenAI. Requiere la key en el entorno
    (.env) o en el llavero del sistema (ver src/secrets_store.py -- mas
    seguro, la key nunca toca un archivo de texto plano). No hay fallback
    simulado: si la key no esta en ningun lado, se lanza un error
    explicito en vez de inventar un resultado."""

    _DIMENSIONS = {"text-embedding-3-small": 1536}

    def __init__(self, model_name: str = "text-embedding-3-small"):
        api_key = get_openai_api_key()
        if not api_key:
            raise RuntimeError(
                "No se encontro OPENAI_API_KEY ni en el entorno/.env ni en el llavero del "
                "sistema. Ver src/secrets_store.py para las dos formas de configurarla "
                "(nunca pegarla en el codigo ni en el chat)."
            )
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self.name = model_name
        self.provider = "openai"
        self.dim = self._DIMENSIONS.get(model_name, 1536)
        self.total_tokens_used = 0  # se acumula en cada llamada real, para el costo

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = []
        batch_size = 100  # limite prudente por request, no un limite duro de la API
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            resp = self._client.embeddings.create(model=self.name, input=batch)
            self.total_tokens_used += resp.usage.total_tokens
            vectors.extend(d.embedding for d in resp.data)
        arr = np.array(vectors, dtype="float32")
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return arr / norms


def get_backend(provider: str, model_name: str):
    if provider == "local":
        return LocalEmbeddingBackend(model_name)
    if provider == "openai":
        return OpenAIEmbeddingBackend(model_name)
    raise ValueError(f"Proveedor de embeddings desconocido: {provider!r}")
