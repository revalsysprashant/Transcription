# Model setup: cache the local Silero model and create clients for Groq's remote models.
from functools import lru_cache

from groq import AsyncGroq
from silero_vad import load_silero_vad


@lru_cache(maxsize=1)
def load_silero_model():
    """Load and reuse the packaged CPU ONNX model.

    Input: none; weights are included in the installed Silero package.
    Output: a stateful model. The speech repository holds its lock during use.
    """
    return load_silero_vad(onnx=True)


def create_groq_client(api_key: str) -> AsyncGroq:
    """Create an async client for Groq's hosted transcription model.

    Input: the configured API key, already checked by the provider.
    Output: a new client with a timeout and automatic retries disabled.
    The provider closes it using async with. No model weights are loaded locally.
    """
    return AsyncGroq(api_key=api_key, timeout=60.0, max_retries=0)
