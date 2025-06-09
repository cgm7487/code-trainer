import json
import random
import asyncio
import os
import sys
import tempfile
from typing import Optional, Tuple

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
    <title>Code Trainer</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
  </head>
  <body class="bg-light">
    <div class="container py-5">
      <h1 class="mb-2 text-center">Code Trainer</h1>
      <form class="row g-3 justify-content-center" action="/random" method="get">
        <div class="col-auto">
          <label for="difficulty-select" class="form-label me-2">Select Difficulty</label>
          <select id="difficulty-select" class="form-select" name="difficulty">
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
          <input type="hidden" id="sample-case" value="{{ problem.sampleTestCase|e }}">
          {% endif %}
          <form id="code-form" class="mt-3">
            <select class="form-select mb-2" name="language">
              <option value="cpp">C++</option>
              <option value="python">Python</option>
              <option value="java">Java</option>
              <option value="go">Go</option>
            </select>
            <textarea class="form-control" name="code" rows="10" placeholder="print('hello')"></textarea>
            <button type="button" id="fill-snippet-btn" class="btn btn-secondary mt-2">Start Code</button>
            <button type="submit" class="btn btn-primary mt-3">Run Code</button>
          </form>
          <pre id="output" class="bg-dark text-white p-3"></pre>
        </div>
      </div>
      <script id="snippets-data" type="application/json">{{ snippets_json | tojson | safe }}</script>
      <script>
        let snippets = [];
        try {
          const raw = document.getElementById('snippets-data')?.textContent || '[]';
          snippets = JSON.parse(raw);
        } catch (e) {
          console.error('Failed to parse snippets JSON:', e);
        }
        const langSelect = document.querySelector('#code-form select[name="language"]');
        const codeInput = document.querySelector('#code-form textarea[name="code"]');
        function fillSnippet() {
          const lang = langSelect.value;
          const s = snippets.find(sn => sn.langSlug === lang);
          if (s) {
            codeInput.value = s.code;
          }
        }
        langSelect.addEventListener('change', fillSnippet);
        document.getElementById('fill-snippet-btn').addEventListener('click', fillSnippet);
        fillSnippet();
        document.getElementById('code-form').addEventListener('submit', async (e) => {
          e.preventDefault();
          const code = e.target.code.value;
          const language = e.target.language.value;
          const sampleCaseEl = document.getElementById('sample-case');
          const sampleCase = sampleCaseEl ? sampleCaseEl.value : '';
          const resp = await fetch('/execute', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({code, language, sampleCase})});
          const data = await resp.json();
          let output = data.stdout + data.stderr;
          if (typeof data.passed !== 'undefined') {
            output += '\nPassed: ' + data.passed;
          }
          document.getElementById('output').textContent = output;
        });
      </script>
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
    <title>Code Trainer</title>
    <link href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css\" rel=\"stylesheet\">
  </head>
  <body class=\"bg-light\">
    <div class=\"container py-5\">
      <h1 class=\"mb-4\">{{ problem.title }}</h1>
      <div class=\"mb-3\">{{ problem.content or 'No description available.' }}</div>
      {% if problem.sampleTestCase %}
      <pre class=\"mt-3 bg-dark text-white p-3\">{{ problem.sampleTestCase }}</pre>
      <input type=\"hidden\" id=\"sample-case\" value="{{ problem.sampleTestCase|e }}">
      {% endif %}
      <form id=\"code-form\" class=\"mb-3\">
        <select class=\"form-select mb-2\" name=\"language\">
          <option value=\"cpp\">C++</option>
          <option value=\"python\">Python</option>
          <option value=\"java\">Java</option>
          <option value=\"go\">Go</option>
        </select>
        <textarea class=\"form-control\" name=\"code\" rows=\"10\" placeholder=\"print('hello')\"></textarea>
        <button type=\"button\" id=\"fill-snippet-btn\" class=\"btn btn-secondary mt-2\">Start Code</button>
        <button type=\"submit\" class=\"btn btn-primary mt-3\">Run Code</button>
      </form>
      <pre id=\"output\" class=\"bg-dark text-white p-3\"></pre>
    </div>
    <script id=\"snippets-data\" type=\"application/json\">{{ snippets_json | tojson | safe }}</script>
    <script>
      let snippets = [];
      try {
        const raw = document.getElementById('snippets-data')?.textContent || '[]';
        snippets = JSON.parse(raw);
      } catch (e) {
        console.error('Failed to parse snippets JSON:', e);
      }
      const langSelect = document.querySelector('#code-form select[name="language"]');
      const codeInput = document.querySelector('#code-form textarea[name="code"]');
      function fillSnippet() {
        const lang = langSelect.value;
        const s = snippets.find(sn => sn.langSlug === lang);
        if (s) {
          codeInput.value = s.code;
        }
      }
      langSelect.addEventListener('change', fillSnippet);
      document.getElementById('fill-snippet-btn').addEventListener('click', fillSnippet);
      fillSnippet();
      document.getElementById('code-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const code = e.target.code.value;
        const language = e.target.language.value;
        const sampleCaseEl = document.getElementById('sample-case');
        const sampleCase = sampleCaseEl ? sampleCaseEl.value : '';
        const resp = await fetch('/execute', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({code, language, sampleCase})});
        const data = await resp.json();
        let output = data.stdout + data.stderr;
        if (typeof data.passed !== 'undefined') {
          output += '\nPassed: ' + data.passed;
        }
        document.getElementById('output').textContent = output;
      });
    </script>
  </body>
</html>
"""

TEMPLATE = Template(INDEX_HTML)
SOLVE_TEMPLATE = Template(SOLVE_HTML)


def parse_sample_test_case(case: str) -> tuple[str, str]:
    """Extract input and expected output from a sample test case string."""
    if not case:
        return "", ""
    input_data = ""
    expected = ""
    for line in case.splitlines():
        line = line.strip()
        if line.lower().startswith("input") and ":" in line:
            input_data = line.split(":", 1)[1].strip()
        elif line.lower().startswith("output") and ":" in line:
            expected = line.split(":", 1)[1].strip()
    return input_data, expected


async def fetch_problem_detail(slug: str) -> dict:
    """Retrieve problem content and sample test case from LeetCode."""
    query = (
        "query getQuestion($titleSlug: String!) {\n"
        "  question(titleSlug: $titleSlug) {\n"
        "    content\n"
        "    sampleTestCase\n"
        "    codeSnippets {\n"
        "      lang\n"
        "      langSlug\n"
        "      code\n"
        "    }\n"
        "  }\n"
        "}"
    )
    payload = {"query": query, "variables": {"titleSlug": slug}}
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(GRAPHQL_API, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            q = data.get("data", {}).get("question", {})
            return {
                "content": q.get("content", ""),
                "sampleTestCase": q.get("sampleTestCase", ""),
                "codeSnippets": q.get("codeSnippets", []),
            }
    except Exception:
        return {"content": "", "sampleTestCase": "", "codeSnippets": []}




async def fetch_problems() -> list[dict]:

    """Fetch the list of problems from LeetCode or fallback to local data."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(LEETCODE_API, headers=headers)
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


async def get_problem_by_slug(slug: str) -> Optional[dict]:
    """Return a problem dict for the given slug."""
    problems = await fetch_problems()
    for p in problems:
        if p.get("url", "").rstrip("/").split("/")[-1] == slug:
            if not p.get("content") or not p.get("codeSnippets"):
                p.update(await fetch_problem_detail(slug))
            return p
    return None


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, difficulty: Optional[str] = None):
    problems = await fetch_problems()
    problem = None
    if difficulty:
        matches = [p for p in problems if p["difficulty"].lower() == difficulty.lower()]
        if matches:
            problem = random.choice(matches).copy()
            if not problem.get("content") or not problem.get("codeSnippets"):
                slug = problem.get("url", "").rstrip("/").split("/")[-1]
                if slug:
                    detail = await fetch_problem_detail(slug)
                    if detail.get("content") or detail.get("codeSnippets"):
                        problem.update(detail)
    if problem:
        snippets = problem.get("codeSnippets") or []
        if not snippets:
            snippets = [
                {"lang": "Python3", "langSlug": "python", "code": generate_template(problem, "python")},
                {"lang": "C++", "langSlug": "cpp", "code": generate_template(problem, "cpp")},
                {"lang": "Java", "langSlug": "java", "code": generate_template(problem, "java")},
                {"lang": "Go", "langSlug": "go", "code": generate_template(problem, "go")},
            ]
            problem["codeSnippets"] = snippets
        snippets_json = snippets
    else:
        snippets_json = []
    return HTMLResponse(TEMPLATE.render(problem=problem, snippets_json=snippets_json))


@app.get("/random")
async def random_problem(request: Request, difficulty: str = ""):
    problems = await fetch_problems()
    matches = [p for p in problems if p["difficulty"].lower() == difficulty.lower()]
    if not matches:
        raise HTTPException(status_code=404, detail="No problems found for difficulty")
    problem = random.choice(matches)
    if not problem.get("content"):
        slug = problem.get("url", "").rstrip("/").split("/")[-1]
        if slug:
            problem.update(await fetch_problem_detail(slug))
    if request.headers.get("accept", "").startswith("text/html"):
        snippets_json = problem.get("codeSnippets") or []
        return HTMLResponse(TEMPLATE.render(problem=problem, snippets_json=snippets_json))
    return problem


@app.get("/solve/{slug}", response_class=HTMLResponse)
async def solve_page(slug: str):
    problem = await get_problem_by_slug(slug)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    snippets = problem.get("codeSnippets") or []
    if not snippets:
        snippets = [
            {"lang": "Python3", "langSlug": "python", "code": generate_template(problem, "python")},
            {"lang": "C++", "langSlug": "cpp", "code": generate_template(problem, "cpp")},
            {"lang": "Java", "langSlug": "java", "code": generate_template(problem, "java")},
            {"lang": "Go", "langSlug": "go", "code": generate_template(problem, "go")},
        ]
        problem["codeSnippets"] = snippets
    snippets_json = snippets
    return HTMLResponse(SOLVE_TEMPLATE.render(problem=problem, snippets_json=snippets_json))


async def _run_python(code: str, stdin: str = "") -> dict:
    with tempfile.NamedTemporaryFile("w+", suffix=".py", delete=False) as tmp:
        tmp.write(code)
        tmp.flush()
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            tmp.name,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(stdin.encode()), timeout=15)
        except asyncio.TimeoutError:
            proc.kill()
            return {"stdout": "", "stderr": "Execution timed out", "returncode": 1}
    os.unlink(tmp.name)
    return {
        "stdout": stdout.decode(),
        "stderr": stderr.decode(),
        "returncode": proc.returncode,
    }


async def _run_cpp(code: str, stdin: str = "") -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        src = os.path.join(tmpdir, "main.cpp")
        exe = os.path.join(tmpdir, "main")
        with open(src, "w") as f:
            f.write(code)
        compile_proc = await asyncio.create_subprocess_exec(
            "g++",
            src,
            "-o",
            exe,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        cout, cerr = await compile_proc.communicate()
        if compile_proc.returncode != 0:
            return {"stdout": cout.decode(), "stderr": cerr.decode(), "returncode": compile_proc.returncode}
        run_proc = await asyncio.create_subprocess_exec(
            exe,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(run_proc.communicate(stdin.encode()), timeout=5)
        except asyncio.TimeoutError:
            run_proc.kill()
            return {"stdout": "", "stderr": "Execution timed out", "returncode": 1}
        return {"stdout": stdout.decode(), "stderr": stderr.decode(), "returncode": run_proc.returncode}


async def _run_java(code: str, stdin: str = "") -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        src = os.path.join(tmpdir, "Main.java")
        with open(src, "w") as f:
            f.write(code)
        compile_proc = await asyncio.create_subprocess_exec(
            "javac",
            src,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        cout, cerr = await compile_proc.communicate()
        if compile_proc.returncode != 0:
            return {"stdout": cout.decode(), "stderr": cerr.decode(), "returncode": compile_proc.returncode}
        run_proc = await asyncio.create_subprocess_exec(
            "java",
            "-cp",
            tmpdir,
            "Main",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(run_proc.communicate(stdin.encode()), timeout=5)
        except asyncio.TimeoutError:
            run_proc.kill()
            return {"stdout": "", "stderr": "Execution timed out", "returncode": 1}
        return {"stdout": stdout.decode(), "stderr": stderr.decode(), "returncode": run_proc.returncode}


async def _run_go(code: str, stdin: str = "") -> dict:
    with tempfile.NamedTemporaryFile("w+", suffix=".go", delete=False) as tmp:
        tmp.write(code)
        tmp.flush()
        proc = await asyncio.create_subprocess_exec(
            "go",
            "run",
            tmp.name,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(stdin.encode()), timeout=15)
        except asyncio.TimeoutError:
            proc.kill()
            return {"stdout": "", "stderr": "Execution timed out", "returncode": 1}
    os.unlink(tmp.name)
    return {
        "stdout": stdout.decode(),
        "stderr": stderr.decode(),
        "returncode": proc.returncode,
    }


def generate_template(problem: dict, language: str) -> str:
    """Return the code template for a given problem and language."""
    lang = language.lower()
    for snippet in problem.get("codeSnippets", []):
        if snippet.get("langSlug", "").lower() == lang:
            return snippet.get("code", "")
    defaults = {
        "python": "# Write your solution here\n",
        "cpp": "#include <bits/stdc++.h>\nusing namespace std;\nint main() {\n    return 0;\n}\n",
        "java": "public class Main {\n    public static void main(String[] args) {\n    }\n}\n",
        "go": "package main\nfunc main() {\n}\n",
    }
    return defaults.get(lang, "")


async def run_code(language: str, code: str, stdin: str = "") -> dict:
    """Dispatch execution to the correct runtime based on language."""
    lang = language.lower()
    if lang == "python":
        return await _run_python(code, stdin)
    if lang in {"cpp", "c++"}:
        return await _run_cpp(code, stdin)
    if lang == "java":
        return await _run_java(code, stdin)
    if lang == "go":
        return await _run_go(code, stdin)
    return {"stdout": "", "stderr": "Unsupported language", "returncode": 1}


@app.post("/execute")
async def execute_code(request: Request):
    data = await request.json()
    code = data.get("code", "")
    language = data.get("language", "python").lower()
    sample_case = data.get("sampleCase", "")
    input_data, expected = parse_sample_test_case(sample_case)
    stdin = input_data + "\n" if input_data else ""
    result = await run_code(language, code, stdin)
    if expected:
        result["passed"] = result.get("returncode") == 0 and result.get("stdout", "").strip() == expected
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
