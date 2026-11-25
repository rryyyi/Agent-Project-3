import httpx

from mtr_agent.adapters import OpenAICompatibleLLM
from mtr_agent.agent import Agent
from mtr_agent.factory import build_agent


def test_llm_client_sends_evidence_with_bounded_timeout(monkeypatch):
    captured = {}

    def respond(url, **kwargs):
        captured.update(kwargs)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Evidence answer"}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", respond)
    llm = OpenAICompatibleLLM("https://example.test/v1", "test", "placeholder")
    assert llm.generate("question", [{"text": "evidence"}]) == "Evidence answer"
    assert captured["timeout"].read == 20
    assert captured["follow_redirects"] is False
    assert "evidence" in captured["json"]["messages"][1]["content"]


def test_llm_failure_uses_extractive_answer():
    class Offline:
        def generate(self, query, evidence):
            raise TimeoutError()

    result = Agent(llm=Offline()).chat("Octopus payment")
    assert result["status"] == "answered"
    assert result["mode"] == "offline"
    assert "faq-octopus" in result["answer"]
    assert any(t["step"] == "fallback" for t in result["trace"])


def test_factory_default_and_explicit_llm(monkeypatch):
    for name in ["MTR_DENSE_MODEL", "MTR_RERANK_MODEL", "LLM_BASE_URL", "LLM_MODEL", "REDIS_URL"]:
        monkeypatch.delenv(name, raising=False)
    assert build_agent().llm is None
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    assert build_agent().llm.model == "test-model"
