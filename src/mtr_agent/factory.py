"""Environment-based, explicit optional integration wiring (no dotenv magic)."""

import os

from .adapters import BGEEncoder, CrossEncoderReranker, OpenAICompatibleLLM
from .agent import Agent
from .cache import ToolCache
from .knowledge import Knowledge
from .retrieval import Retriever
from .tools import Tools


def build_agent() -> Agent:
    kb = Knowledge.load()
    dense_model = os.environ.get("MTR_DENSE_MODEL", "")
    rerank_model = os.environ.get("MTR_RERANK_MODEL", "")
    device = os.environ.get("MTR_MODEL_DEVICE", "cpu")
    dense = BGEEncoder(dense_model, device) if dense_model else None
    reranker = CrossEncoderReranker(rerank_model, device) if rerank_model else None
    retriever = Retriever(kb, dense=dense, reranker=reranker)
    retriever.profile = f"bm25-v1:dense={dense_model}:rerank={rerank_model}"
    redis_client = None
    if redis_url := os.environ.get("REDIS_URL", ""):
        try:
            from redis import Redis
        except ImportError as exc:
            raise RuntimeError('Install the "redis" extra to configure REDIS_URL') from exc
        redis_client = Redis.from_url(redis_url, socket_timeout=0.3, socket_connect_timeout=0.3)
    llm = None
    base_url, model = os.environ.get("LLM_BASE_URL", ""), os.environ.get("LLM_MODEL", "")
    if bool(base_url) != bool(model):
        raise ValueError("Set both LLM_BASE_URL and LLM_MODEL to enable model synthesis")
    if base_url and model:
        llm = OpenAICompatibleLLM(base_url, model)
    return Agent(tools=Tools(kb, retriever, ToolCache(redis_client=redis_client)), llm=llm)
