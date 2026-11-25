from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from mtr_agent.api import create_app


def test_chat_health_metrics_and_validation(monkeypatch):
    monkeypatch.delenv("MTR_API_KEY", raising=False)
    with TestClient(create_app()) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/ready").json()["knowledge_version"]
        response = client.post("/v1/chat", json={"message": "Central去紅磡"})
        assert response.status_code == 200
        assert response.json()["request_id"] == response.headers["x-request-id"]
        assert response.json()["route"]["transfers"] == 1
        for payload in [
            {"message": ""},
            {"message": " "},
            {"message": "a" * 2001},
            {"message": "hello", "session_id": "../bad"},
            {"message": "hello", "extra": 1},
        ]:
            assert client.post("/v1/chat", json=payload).status_code == 422
        assert "mtr_requests_total" in client.get("/metrics").text
        assert len(client.get("/v1/tools").json()["tools"]) == 2
        assert (
            client.post(
                "/v1/tools/route_plan", json={"origin": "Central", "destination": "Hung Hom"}
            ).status_code
            == 200
        )
        assert client.post("/v1/tools/bad", json={}).status_code == 400
        assert client.delete("/v1/sessions/missing").json()["deleted"] is False


def test_bearer_auth_protects_data_and_metrics():
    with TestClient(create_app(api_key="secret")) as client:
        assert client.get("/health").status_code == 200
        for path in ["/ready", "/metrics", "/v1/tools"]:
            assert client.get(path).status_code == 401
            assert client.get(path, headers={"Authorization": "Bearer secret"}).status_code == 200
        assert client.post("/v1/chat", json={"message": "hello"}).status_code == 401


def test_parallel_requests_and_session_delete():
    with TestClient(create_app(api_key="")) as client:

        def query(i):
            return client.post("/v1/chat", json={"message": "HKU去灣仔", "session_id": f"user{i}"})

        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(query, range(16)))
        assert all(r.status_code == 200 for r in responses)
        assert len({r.json()["request_id"] for r in responses}) == 16
        assert client.delete("/v1/sessions/user1").json()["deleted"] is True
