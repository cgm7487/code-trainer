import json
import random
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from jinja2 import Template

app = FastAPI()

# Load problems from local file as a fallback
with open("problems.json") as f:
    LOCAL_PROBLEMS = json.load(f)

LEETCODE_API = "https://leetcode.com/api/problems/all/"

GRAPHQL_API = "https://leetcode.com/graphql"

INDEX_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>LeetCode Random Selector</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
  </head>
  <body class="bg-light">
    <div class="container py-5">
      <h1 class="mb-4 text-center">Select Difficulty</h1>
      <form class="row g-3 justify-content-center" action="/random" method="get">
        <div class="col-auto">
          <select class="form-select" name="difficulty">
            <option value="Easy">Easy</option>
            <option value="Medium">Medium</option>
            <option value="Hard">Hard</option>
          </select>
        </div>
        <div class="col-auto">
          <button class="btn btn-primary" type="submit">
            <i class="fa-solid fa-dice"></i>
            Get Problem
          </button>
        </div>
      </form>
      {% if problem %}
      <div class="card mt-4">
        <div class="card-body">
          <h2 class="card-title">
            <a href="{{ problem.url }}" target="_blank">{{ problem.title }}</a>
            <span class="badge bg-secondary">{{ problem.difficulty }}</span>
          </h2>
          <div class="card-text">{{ problem.content or "No description available." }}</div>
          {% if problem.sampleTestCase %}
          <pre class="mt-3 bg-dark text-white p-3">{{ problem.sampleTestCase }}</pre>
          {% endif %}
        </div>
      </div>
      {% endif %}
    </div>
  </body>
</html>
"""

TEMPLATE = Template(INDEX_HTML)


def fetch_problem_detail(slug: str) -> dict:
    """Retrieve problem content and sample test case from LeetCode."""
    query = (
        "query getQuestion($titleSlug: String!) {\n"
        "  question(titleSlug: $titleSlug) {\n"
        "    content\n"
        "    sampleTestCase\n"
        "  }\n"
        "}"
    )
    payload = {"query": query, "variables": {"titleSlug": slug}}
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = httpx.post(GRAPHQL_API, json=payload, headers=headers, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        q = data.get("data", {}).get("question", {})
        return {
            "content": q.get("content", ""),
            "sampleTestCase": q.get("sampleTestCase", ""),
        }
    except Exception:
        return {"content": "", "sampleTestCase": ""}


def fetch_problems() -> list[dict]:
    """Fetch the list of problems from LeetCode or fallback to local data."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = httpx.get(LEETCODE_API, headers=headers, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        problems = []
        local_by_id = {p["id"]: p for p in LOCAL_PROBLEMS}
        for item in data.get("stat_status_pairs", []):
            stat = item.get("stat", {})
            pid = stat.get("frontend_question_id")
            entry = {
                "id": pid,
                "title": stat.get("question__title"),
                "difficulty": ["", "Easy", "Medium", "Hard"][
                    item.get("difficulty", {}).get("level", 0)
                ],
                "url": f"https://leetcode.com/problems/{stat.get('question__title_slug')}/",
            }
            if pid in local_by_id:
                entry["content"] = local_by_id[pid].get("content", "")
                entry["sampleTestCase"] = local_by_id[pid].get("sampleTestCase", "")
            problems.append(entry)
        if problems:
            return problems
    except Exception:
        pass
    return LOCAL_PROBLEMS


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, difficulty: Optional[str] = None):
    problems = fetch_problems()
    problem = None
    if difficulty:
        matches = [p for p in problems if p["difficulty"].lower() == difficulty.lower()]
        if matches:
            problem = random.choice(matches)
    return HTMLResponse(TEMPLATE.render(problem=problem))


@app.get("/random")
async def random_problem(request: Request, difficulty: str = ""):
    problems = fetch_problems()
    matches = [p for p in problems if p["difficulty"].lower() == difficulty.lower()]
    if not matches:
        raise HTTPException(status_code=404, detail="No problems found for difficulty")
    problem = random.choice(matches)
    if not problem.get("content"):
        slug = problem.get("url", "").rstrip("/").split("/")[-1]
        if slug:
            problem.update(fetch_problem_detail(slug))
    if request.headers.get("accept", "").startswith("text/html"):
        return HTMLResponse(TEMPLATE.render(problem=problem))
    return problem


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
