import sys
from pathlib import Path
import httpx
import random
from fastapi.testclient import TestClient
import pytest

# Ensure the application module can be imported when tests run in isolation
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app

client = TestClient(app.app)


def test_fetch_problems_fallback(monkeypatch):
    def fake_get(*args, **kwargs):
        raise httpx.RequestError("fail")
    monkeypatch.setattr(httpx, "get", fake_get)
    assert app.fetch_problems() == app.LOCAL_PROBLEMS


def test_fetch_problems_remote(monkeypatch):
    sample = {
        "stat_status_pairs": [
            {
                "stat": {
                    "frontend_question_id": 123,
                    "question__title": "Sample Problem",
                    "question__title_slug": "sample-problem",
                },
                "difficulty": {"level": 2},
            }
        ]
    }

    class FakeResp:
        def json(self):
            return sample

        def raise_for_status(self):
            pass

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResp())

    problems = app.fetch_problems()
    assert problems == [
        {
            "id": 123,
            "title": "Sample Problem",
            "difficulty": "Medium",
            "url": "https://leetcode.com/problems/sample-problem/",
        }
    ]


def test_fetch_problems_remote_enrich(monkeypatch):
    sample = {
        "stat_status_pairs": [
            {
                "stat": {
                    "frontend_question_id": 1,
                    "question__title": "Two Sum",
                    "question__title_slug": "two-sum",
                },
                "difficulty": {"level": 1},
            }
        ]
    }

    class FakeResp:
        def json(self):
            return sample

        def raise_for_status(self):
            pass

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResp())
    problems = app.fetch_problems()
    assert problems[0]["content"]
    assert problems[0]["sampleTestCase"]


def test_index_no_difficulty(monkeypatch):
    monkeypatch.setattr(app, "fetch_problems", lambda: app.LOCAL_PROBLEMS)
    response = client.get("/")
    assert response.status_code == 200
    assert "Select Difficulty" in response.text


def test_index_with_difficulty(monkeypatch):
    monkeypatch.setattr(app, "fetch_problems", lambda: app.LOCAL_PROBLEMS)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    response = client.get("/?difficulty=Easy")
    assert response.status_code == 200
    assert "Two Sum" in response.text
    assert "indices of the two numbers" in response.text


def test_random_problem_json(monkeypatch):
    monkeypatch.setattr(app, "fetch_problems", lambda: app.LOCAL_PROBLEMS)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    response = client.get("/random?difficulty=Easy")
    assert response.status_code == 200
    assert response.json()["title"] == "Two Sum"


def test_random_problem_html(monkeypatch):
    monkeypatch.setattr(app, "fetch_problems", lambda: app.LOCAL_PROBLEMS)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    response = client.get("/random?difficulty=Easy", headers={"accept": "text/html"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Two Sum" in response.text
    assert "Input: nums" in response.text


def test_random_problem_not_found(monkeypatch):
    monkeypatch.setattr(app, "fetch_problems", lambda: app.LOCAL_PROBLEMS)
    response = client.get("/random?difficulty=Impossible")
    assert response.status_code == 404


def test_random_problem_fetch_detail(monkeypatch):
    problems = [
        {
            "id": 1234,
            "title": "Burst Balloons",
            "difficulty": "Hard",
            "url": "https://leetcode.com/problems/burst-balloons/",
            "content": "",
            "sampleTestCase": "",
        }
    ]

    monkeypatch.setattr(app, "fetch_problems", lambda: problems)
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    def fake_detail(slug):
        assert slug == "burst-balloons"
        return {"content": "Some description", "sampleTestCase": "case"}

    monkeypatch.setattr(app, "fetch_problem_detail", fake_detail)
    response = client.get("/random?difficulty=Hard", headers={"accept": "text/html"})
    assert response.status_code == 200
    assert "Some description" in response.text
