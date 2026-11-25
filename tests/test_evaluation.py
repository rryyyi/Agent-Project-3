import json

import pytest

from mtr_agent.cli import main
from mtr_agent.evaluation import evaluate, load_cases


def test_metric_denominators_and_failures():
    cases = [
        {
            "id": "r",
            "message": "Central去紅磡",
            "intent": "route",
            "status": "answered",
            "route": {"origin": "CEN", "destination": "HUH", "transfers": 1},
        },
        {
            "id": "k",
            "message": "Octopus payment",
            "intent": "knowledge",
            "status": "answered",
            "document_id": "faq-luggage",
        },
        {"id": "u", "message": "quantum banana", "intent": "knowledge", "status": "unsupported"},
    ]
    report = evaluate(cases)
    assert report["samples"] == 3
    assert report["metrics"]["intent_accuracy"]["correct"] == 3
    assert report["metrics"]["retrieval_hit_at_3"] == {"correct": 0, "total": 1, "score": 0}
    assert report["metrics"]["route_exact_match"]["score"] == 1
    assert report["failures"][0]["id"] == "k"
    assert report["limitations"]


def test_empty_and_malformed_eval(tmp_path):
    with pytest.raises(ValueError, match="empty"):
        evaluate([])
    path = tmp_path / "bad.jsonl"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="line 1"):
        load_cases(path)
    path.write_text(json.dumps({"id": "no-message"}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_cases(path)


def test_cli_demo_and_evaluation(tmp_path, capsys):
    assert main(["chat", "由Central去紅磡點搭"]) == 0
    assert "HUH" in capsys.readouterr().out
    assert main(["demo"]) == 0
    assert "faq-octopus" in capsys.readouterr().out
    report = tmp_path / "report.json"
    assert main(["evaluate", "--output", str(report)]) == 0
    assert json.loads(report.read_text(encoding="utf-8"))["samples"] >= 30
    assert main(["parse-pdf", str(tmp_path / "missing.pdf")]) == 1


def test_multiturn_eval_group_isolation():
    cases = [
        {
            "id": "1",
            "message": "Central去紅磡",
            "session": "a",
            "intent": "route",
            "status": "answered",
        },
        {
            "id": "2",
            "message": "咁去旺角呢",
            "session": "a",
            "intent": "route",
            "status": "answered",
            "route": {"origin": "CEN", "destination": "MOK"},
        },
        {
            "id": "3",
            "message": "咁去旺角呢",
            "session": "b",
            "intent": "route",
            "status": "clarification",
        },
    ]
    report = evaluate(cases)
    assert report["metrics"]["status_accuracy"]["score"] == 1
    assert report["metrics"]["route_exact_match"]["score"] == 1
