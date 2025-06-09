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

INDEX_HTML = """
<!doctype html>
<title>LeetCode Random Selector</title>
<h1>Select Difficulty</h1>
<form action="/random" method="get">
  <select name="difficulty">
    <option value="Easy">Easy</option>
    <option value="Medium">Medium</option>
    <option value="Hard">Hard</option>
  </select>
  <button type="submit">Get Problem</button>
</form>
{% if problem %}
<h2>{{ problem.title }} ({{ problem.difficulty }})</h2>
<p><a href="{{ problem.url }}" target="_blank">{{ problem.url }}</a></p>
<div>{{ problem.content or "No description available." }}</div>
{% if problem.sampleTestCase %}
<pre>{{ problem.sampleTestCase }}</pre>
{% endif %}
{% endif %}
"""

TEMPLATE = Template(INDEX_HTML)


def fetch_problems() -> list[dict]:
    """Fetch the list of problems from LeetCode or fallback to local data."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = httpx.get(LEETCODE_API, headers=headers, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        problems = []
        for item in data.get("stat_status_pairs", []):
            stat = item.get("stat", {})
            problems.append(
                {
                    "id": stat.get("frontend_question_id"),
                    "title": stat.get("question__title"),
                    "difficulty": ["", "Easy", "Medium", "Hard"][
                        item.get("difficulty", {}).get("level", 0)
                    ],
                    "url": f"https://leetcode.com/problems/{stat.get('question__title_slug')}/",
                }
            )
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
    if request.headers.get("accept", "").startswith("text/html"):
        return HTMLResponse(TEMPLATE.render(problem=problem))
    return problem


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
