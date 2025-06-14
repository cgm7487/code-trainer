import sys
from pathlib import Path
import httpx
import random
import asyncio
from fastapi.testclient import TestClient
import pytest

# Ensure the application module can be imported when tests run in isolation
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app

client = TestClient(app.app)


@pytest.mark.asyncio
async def test_fetch_problems_fallback(monkeypatch):
    async def fake_get(self, *args, **kwargs):
        raise httpx.RequestError("fail")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    assert await app.fetch_problems() == app.LOCAL_PROBLEMS


@pytest.mark.asyncio
async def test_fetch_problems_remote(monkeypatch):
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

    async def fake_get(self, *a, **k):
        return FakeResp()

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    problems = await app.fetch_problems()
    assert problems == [
        {
            "id": 123,
            "title": "Sample Problem",
            "difficulty": "Medium",
            "url": "https://leetcode.com/problems/sample-problem/",
        }
    ]


@pytest.mark.asyncio
async def test_fetch_problems_remote_enrich(monkeypatch):
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

    async def fake_get(self, *a, **k):
        return FakeResp()

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    problems = await app.fetch_problems()
    assert problems[0]["content"]
    assert problems[0]["sampleTestCase"]


def _async_return(value):
    async def _inner(*args, **kwargs):
        return value
    return _inner


def test_index_no_difficulty(monkeypatch):
    monkeypatch.setattr(app, "fetch_problems", _async_return(app.LOCAL_PROBLEMS))
    response = client.get("/")
    assert response.status_code == 200
    assert "Select Difficulty" in response.text


def test_index_with_difficulty(monkeypatch):
    monkeypatch.setattr(app, "fetch_problems", _async_return(app.LOCAL_PROBLEMS))
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    response = client.get("/?difficulty=Easy")
    assert response.status_code == 200
    assert "Two Sum" in response.text
    assert "indices of the two numbers" in response.text


def test_random_problem_json(monkeypatch):
    monkeypatch.setattr(app, "fetch_problems", _async_return(app.LOCAL_PROBLEMS))
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    response = client.get("/random?difficulty=Easy")
    assert response.status_code == 200
    assert response.json()["title"] == "Two Sum"


def test_random_problem_html(monkeypatch):
    monkeypatch.setattr(app, "fetch_problems", _async_return(app.LOCAL_PROBLEMS))
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])
    response = client.get("/random?difficulty=Easy", headers={"accept": "text/html"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Two Sum" in response.text
    assert "Input: nums" in response.text


def test_random_problem_not_found(monkeypatch):
    monkeypatch.setattr(app, "fetch_problems", _async_return(app.LOCAL_PROBLEMS))
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

    monkeypatch.setattr(app, "fetch_problems", _async_return(problems))
    monkeypatch.setattr(random, "choice", lambda seq: seq[0])

    async def fake_detail(slug):
        assert slug == "burst-balloons"
        return {"content": "Some description", "sampleTestCase": "case"}

    monkeypatch.setattr(app, "fetch_problem_detail", fake_detail)
    response = client.get("/random?difficulty=Hard", headers={"accept": "text/html"})
    assert response.status_code == 200
    assert "Some description" in response.text


def test_solve_page(monkeypatch):
    monkeypatch.setattr(app, "fetch_problems", _async_return(app.LOCAL_PROBLEMS))

    async def fake_detail(slug):
        return {"codeSnippets": [{"lang": "Python3", "langSlug": "python", "code": "print('hi')"}]}

    monkeypatch.setattr(app, "fetch_problem_detail", fake_detail)
    response = client.get("/solve/two-sum")
    assert response.status_code == 200
    assert "textarea" in response.text


def test_solve_page_contains_snippet(monkeypatch):
    monkeypatch.setattr(app, "fetch_problems", _async_return(app.LOCAL_PROBLEMS))

    async def fake_detail(slug):
        return {
            "content": "desc",
            "sampleTestCase": "",
            "codeSnippets": [
                {"lang": "Python3", "langSlug": "python", "code": "print('hi')"}
            ],
        }

    monkeypatch.setattr(app, "fetch_problem_detail", fake_detail)
    response = client.get("/solve/two-sum")
    assert response.status_code == 200
    import re, json
    m = re.search(r'id="snippets-data" type="application/json">(.*?)</script>', response.text)
    assert m, 'snippets-data script not found'
    data = json.loads(m.group(1))
    assert any(sn["code"] == "print('hi')" for sn in data)


def test_solve_page_default_snippets(monkeypatch):
    import copy, json
    with open("problems.json") as f:
        original = json.load(f)
    monkeypatch.setattr(app, "fetch_problems", _async_return(copy.deepcopy(original)))

    async def fake_detail(slug):
        return {"content": "desc", "sampleTestCase": "", "codeSnippets": []}

    monkeypatch.setattr(app, "fetch_problem_detail", fake_detail)
    response = client.get("/solve/two-sum")
    assert response.status_code == 200
    assert "using namespace std" in response.text


def test_execute_code_python():
    response = client.post("/execute", json={"code": "print('hi')", "language": "python"})
    assert response.status_code == 200
    assert response.json()["stdout"].strip() == "hi"


def test_execute_code_cpp():
    code = "#include <iostream>\nint main(){std::cout<<\"hi\";return 0;}"
    resp = client.post("/execute", json={"code": code, "language": "cpp"})
    assert resp.status_code == 200
    assert resp.json()["stdout"].strip() == "hi"


def test_execute_code_java():
    code = "public class Main { public static void main(String[] args){ System.out.println(\"hi\"); } }"
    resp = client.post("/execute", json={"code": code, "language": "java"})
    assert resp.status_code == 200
    assert resp.json()["stdout"].strip() == "hi"


def test_execute_code_go():
    code = "package main\nimport \"fmt\"\nfunc main(){fmt.Print(\"hi\")}"
    resp = client.post("/execute", json={"code": code, "language": "go"})
    assert resp.status_code == 200
    assert resp.json()["stdout"].strip() == "hi"


def test_execute_with_sample_case():
    code = "print(int(input()) * 2)"
    sample = "Input: 2\nOutput: 4"
    resp = client.post("/execute", json={"code": code, "language": "python", "sampleCase": sample})
    data = resp.json()
    assert data["stdout"].strip() == "4"
    assert data["passed"] is True


def test_generate_template_from_snippet():
    problem = {"codeSnippets": [{"lang": "Python", "langSlug": "python", "code": "print('x')"}]}
    assert app.generate_template(problem, "python") == "print('x')"


def test_generate_template_fallback():
    assert "Write your solution" in app.generate_template({}, "python")


def test_run_code_dispatch_python():
    result = asyncio.run(app.run_code("python", "print('hi')"))
    assert result["stdout"].strip() == "hi"


def test_run_code_unsupported():
    result = asyncio.run(app.run_code("ruby", "puts 'hi'"))
    assert result["stderr"] == "Unsupported language"


@pytest.mark.asyncio
async def test_fetch_problem_detail_snippets(monkeypatch):
    sample = {
        "data": {
            "question": {
                "content": "desc",
                "sampleTestCase": "case",
                "codeSnippets": [
                    {"lang": "Python3", "langSlug": "python", "code": "class Solution:"}
                ],
            }
        }
    }

    class FakeResp:
        def json(self):
            return sample

        def raise_for_status(self):
            pass

    async def fake_post(self, *a, **k):
        return FakeResp()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    detail = await app.fetch_problem_detail("two-sum")
    assert detail["codeSnippets"]
    assert detail["codeSnippets"][0]["langSlug"] == "python"
