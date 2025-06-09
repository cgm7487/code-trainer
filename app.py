import json
import random
import asyncio
import os
import sys
import tempfile
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

SOLVE_HTML = """
<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\">
    <title>Solve Problem</title>
    <link href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css\" rel=\"stylesheet\">
  </head>
  <body class=\"bg-light\">
    <div class=\"container py-5\">
      <h1 class=\"mb-4\">{{ problem.title }}</h1>
      <div class=\"mb-3\">{{ problem.content or 'No description available.' }}</div>
      <form id=\"code-form\" class=\"mb-3\">
        <textarea class=\"form-control\" name=\"code\" rows=\"10\" placeholder=\"print('hello')\"></textarea>
        <button type=\"submit\" class=\"btn btn-primary mt-3\">Run Code</button>
      </form>
      <pre id=\"output\" class=\"bg-dark text-white p-3\"></pre>
    </div>
    <script>
      document.getElementById('code-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const code = e.target.code.value;
        const resp = await fetch('/execute', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({code})});
        const data = await resp.json();
        document.getElementById('output').textContent = data.stdout + data.stderr;
      });
    </script>
  </body>
</html>
"""

TEMPLATE = Template(INDEX_HTML)
SOLVE_TEMPLATE = Template(SOLVE_HTML)


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


def get_problem_by_slug(slug: str) -> Optional[dict]:
    """Return a problem dict for the given slug."""
    problems = fetch_problems()
    for p in problems:
        if p.get("url", "").rstrip("/").split("/")[-1] == slug:
            if not p.get("content"):
                p.update(fetch_problem_detail(slug))
            return p
    return None


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


@app.get("/solve/{slug}", response_class=HTMLResponse)
async def solve_page(slug: str):
    problem = get_problem_by_slug(slug)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return HTMLResponse(SOLVE_TEMPLATE.render(problem=problem))


@app.post("/execute")
async def execute_code(request: Request):
    data = await request.json()
    code = data.get("code", "")
    with tempfile.NamedTemporaryFile("w+", suffix=".py", delete=False) as tmp:
        tmp.write(code)
        tmp.flush()
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            tmp.name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
        except asyncio.TimeoutError:
            proc.kill()
            return {"stdout": "", "stderr": "Execution timed out", "returncode": 1}
    os.unlink(tmp.name)
    return {
        "stdout": stdout.decode(),
        "stderr": stderr.decode(),
        "returncode": proc.returncode,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
