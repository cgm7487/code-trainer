import asyncio
import base64
import json
import os
import random
import sys
import tempfile
from typing import Optional, Tuple

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from jinja2 import Template

from fastapi_mcp import FastApiMCP

from pydantic import BaseModel, Field


class ExecRequest(BaseModel):
    code: str | None = Field(
        None, description="Raw code string to execute (UTF-8 encoded)"
    )
    codeB64: str | None = Field(
        None, description="Base-64 encoded code string (UTF-8)"
    )
    language: str = Field("python", description="python | cpp | java | go")
    sampleCase: str | None = Field(None, description="LeetCode sample case string")


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
    <style>
      body {
        font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
        background-color:#f4f7f9;color:#333;line-height:1.7;margin:0;padding:20px;
        display:flex;justify-content:center;align-items:flex-start;min-height:100vh;
      }
      .container{width:100%;max-width:960px;background:#fff;padding:2rem;border-radius:12px;
        box-shadow:0 8px 30px rgba(0,0,0,.08);box-sizing:border-box;}
      header{text-align:center;border-bottom:1px solid #e0e0e0;padding-bottom:20px;margin-bottom:30px;}
      header h1{color:#007aff;margin:0 0 10px 0;font-size:2em;}
      header p{color:#666;font-size:1.1em;}
      .controls{display:flex;justify-content:center;align-items:center;gap:20px;margin-bottom:40px;flex-wrap:wrap;}
      .controls label{font-size:1em;font-weight:500;}
      #difficulty-select{padding:12px 15px;font-size:1em;border-radius:8px;border:1px solid #ccc;background:#fff;}
      #get-problem-btn{padding:12px 25px;font-size:1em;font-weight:600;color:#fff;
        background:linear-gradient(45deg,#28a745,#218838);border:none;border-radius:8px;cursor:pointer;
        transition:transform .2s ease,box-shadow .2s ease;box-shadow:0 4px 15px rgba(40,167,69,.2);}
      #get-problem-btn:hover{transform:translateY(-2px);box-shadow:0 6px 20px rgba(40,167,69,.3);}
      #get-problem-btn:active{transform:translateY(0);}
      .content-section{margin-top:25px;padding:25px;border:1px solid #e9ecef;border-radius:10px;background:#fdfdfd;}
      .title-bar{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #eee;padding-bottom:10px;margin-bottom:15px;}
      .title-bar h2,.title-bar h3{margin:0;padding:0;border:none;}
      #go-to-problem-link{font-size:.8em;padding:6px 12px;background:#007aff;color:#fff;text-decoration:none;border-radius:5px;transition:background-color .2s;}
      #go-to-problem-link:hover{background-color:#0056b3;}
      #copy-code-btn{padding:6px 12px;font-size:.8em;background:#6c757d;color:#fff;border:none;border-radius:5px;cursor:pointer;}
      #copy-code-btn:hover{background:#5a6268;}
      #copy-feedback{font-size:.8em;color:#28a745;font-weight:bold;}
      #code-editor{width:100%;box-sizing:border-box;padding:15px;font-family:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,Courier,monospace;
        font-size:15px;border:1px solid #3c3c3c;border-radius:8px;background:#2b2b2b;color:#a9b7c6;resize:vertical;min-height:300px;line-height:1.5;}
      #code-editor:focus{outline:2px solid #007aff;outline-offset:2px;}
      .hidden{display:none;}
    </style>
  </head>
  <body>
    <div class="container">
      <header>
        <h1>Code Trainer</h1>
        <p>Select a difficulty and get a random problem.</p>
      </header>
      <form class="controls" action="/random" method="get">
        <label for="difficulty-select">Select Difficulty:</label>
        <select id="difficulty-select" name="difficulty">
          <option value="Easy">Easy</option>
          <option value="Medium">Medium</option>
          <option value="Hard">Hard</option>
        </select>
        <button id="get-problem-btn" type="submit">Get Problem</button>
      </form>
      <div id="recent-area" class="content-section" style="display:none;">
        <h3>Recent Problems</h3>
        <ul id="recent-list" class="mb-0"></ul>
      </div>
      {% if problem %}
      <div id="problem-display-area" class="content-section">
        <div class="title-bar">
          <h2 id="problem-title">{{ problem.title }}</h2>
          <a id="go-to-problem-link" href="{{ problem.url }}" target="_blank">Go to LeetCode &rarr;</a>
        </div>
        <div id="problem-description">{{ problem.content or 'No description available.' }}</div>
        {% if problem.sampleTestCase %}
        <h3>Example:</h3>
        <div id="problem-examples"><pre>{{ problem.sampleTestCase }}</pre></div>
        <input type="hidden" id="sample-case" value="{{ problem.sampleTestCase|e }}">
        {% endif %}
      </div>
      <div id="code-area" class="content-section">
        <div class="code-actions d-flex justify-content-between align-items-center mb-2">
          <h3 class="mb-0">Code Editor</h3>
          <div>
            <span id="copy-feedback" class="hidden">Copied!</span>
            <button id="copy-code-btn" type="button">Copy Code</button>
          </div>
        </div>
        <form id="code-form">
          <select id="language-select" name="language" class="form-select w-auto mb-2">
            <option value="cpp">C++</option>
            <option value="python">Python</option>
            <option value="java">Java</option>
            <option value="go">Go</option>
          </select>
          <textarea id="code-editor" name="code" rows="10" placeholder="print('hello')"></textarea>
          <button type="button" id="reset-code-btn" class="btn btn-outline-primary me-2">Reset</button>
          <button type="submit" class="btn btn-primary">Run Code</button>
        </form>
        <pre id="output" class="bg-dark text-white p-3 mt-3"></pre>
      </div>
      <script id="snippets-data" type="application/json">{{ snippets_b64 }}</script>
    <script>
      let snippets = [];
      try {
        const rawB64 = document.getElementById('snippets-data')?.textContent || '';
        if (rawB64) snippets = JSON.parse(atob(rawB64));   // ← 先 atob 解碼！
      } catch (e) {
        console.error('Failed to decode snippets', e);
      }

      function loadHistory(){
        try{ return JSON.parse(localStorage.getItem('recentProblems')||'[]'); }catch(e){ return []; }
      }
      function saveHistory(list){ localStorage.setItem('recentProblems', JSON.stringify(list.slice(0,3))); }
      function renderHistory(){
        const area=document.getElementById('recent-area');
        if(!area) return; const listEl=document.getElementById('recent-list');
        const data=loadHistory();
        area.style.display=data.length?'':'none';
        listEl.innerHTML='';
        for(const p of data){ const li=document.createElement('li'); const a=document.createElement('a'); a.href='/solve/'+p.slug; a.textContent=p.title; li.appendChild(a); listEl.appendChild(li);} }
      function addHistory(problem){
        const data=loadHistory().filter(p=>p.slug!==problem.slug);
        data.unshift({slug:problem.slug,title:problem.title});
        saveHistory(data); renderHistory();
      }

        const langSelect=document.querySelector('#language-select');
        const codeInput=document.querySelector('#code-editor');
        function fillSnippet(){
          const lang=langSelect.value;
          const s=snippets.find(sn=>sn.langSlug.startsWith(lang));
          if(s){codeInput.value=s.code;}
        }
        langSelect.addEventListener('change',fillSnippet);
        document.getElementById('reset-code-btn').addEventListener('click',fillSnippet);
        fillSnippet();
        renderHistory();
        {% if problem %}addHistory({slug: '{{ problem.slug }}', title: '{{ problem.title }}'});{% endif %}
        document.getElementById('code-form').addEventListener('submit',async(e)=>{
          e.preventDefault();
          const code=e.target.code.value;
          const language=e.target.language.value;
          const sampleCaseEl=document.getElementById('sample-case');
          const sampleCase=sampleCaseEl?sampleCaseEl.value:'';
          const resp=await fetch('/execute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code,language,sampleCase})});
          const data=await resp.json();
          let output=data.stdout+data.stderr;
          if(typeof data.passed!=='undefined'){output+='\\nPassed: '+data.passed;}
          document.getElementById('output').textContent=output;
        });
        document.getElementById('copy-code-btn').addEventListener('click',()=>{
          navigator.clipboard.writeText(document.getElementById('code-editor').value)
            .then(()=>{const fb=document.getElementById('copy-feedback');fb.classList.remove('hidden');setTimeout(()=>fb.classList.add('hidden'),2000);})
            .catch(console.error);
        });
      </script>
      {% endif %}
    </div>
  </body>
</html>
"""

SOLVE_HTML = INDEX_HTML

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

def generate_template(language: str) -> str:
    """Return an empty solution template for given language."""
    return {
        "python": "# Write your solution here\n",
        "cpp": "#include <bits/stdc++.h>\nusing namespace std;\nint main() {\n    return 0;\n}\n",
        "java": "public class Main {\n    public static void main(String[] args) {\n    }\n}\n",
        "go": "package main\nfunc main() {}\n",
    }

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


async def inject_snippets(problem: dict) -> None:
    """確保 problem 內含 codeSnippets；若缺失則以預設碼補齊。"""
    if not problem.get("codeSnippets"):
        problem["codeSnippets"] = [
            {"lang": "Python3", "langSlug": "python", "code": generate_template("python")},
            {"lang": "C++", "langSlug": "cpp", "code": generate_template("cpp")},
            {"lang": "Java", "langSlug": "java", "code": generate_template("java")},
            {"lang": "Go", "langSlug": "go", "code": generate_template("go")},
        ]

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
            p["slug"] = slug
            return p
    return None


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, difficulty: Optional[str] = None):
    problems = await fetch_problems()
    problem = None
    if difficulty:
        cand = [p for p in problems if p["difficulty"].lower() == difficulty.lower()]
        if cand:
            problem = random.choice(cand).copy()
            slug = problem["url"].rstrip("/").split("/")[-1]
            detail = await fetch_problem_detail(slug)
            problem.update(detail)
            problem["slug"] = slug
    snippets_b64 = ""
    if problem:
        await inject_snippets(problem)
        snippets_b64 = base64.b64encode(json.dumps(problem["codeSnippets"]).encode()).decode()
    return HTMLResponse(TEMPLATE.render(problem=problem, snippets_b64=snippets_b64))


@app.get("/random", response_class=HTMLResponse)
async def random_problem(request: Request, difficulty: str):
    problems = await fetch_problems()
    matches = [p for p in problems if p["difficulty"].lower() == difficulty.lower()]
    if not matches:
        raise HTTPException(404, "No problems for difficulty")
    problem = random.choice(matches)
    slug = problem["url"].rstrip("/").split("/")[-1]
    problem.update(await fetch_problem_detail(slug))
    problem["slug"] = slug
    await inject_snippets(problem)
    snippets_b64 = base64.b64encode(json.dumps(problem["codeSnippets"]).encode()).decode()
    return HTMLResponse(TEMPLATE.render(problem=problem, snippets_b64=snippets_b64))


@app.get("/solve/{slug}", response_class=HTMLResponse)
async def solve_page(slug: str):
    problem = await get_problem_by_slug(slug)
    if not problem:
        raise HTTPException(404, "Problem not found")
    await inject_snippets(problem)
    snippets_b64 = base64.b64encode(json.dumps(problem["codeSnippets"]).encode()).decode()
    return HTMLResponse(SOLVE_TEMPLATE.render(problem=problem, snippets_b64=snippets_b64))


@app.post("/execute")
async def execute_code(req: ExecRequest):
    if req.code is not None:
        code = req.code
    elif req.codeB64 is not None:
        try:
            code = base64.b64decode(req.codeB64).decode()
        except Exception as e:
            return JSONResponse(
                status_code=400,
                content={"error": f"codeB64 parse failed：{e}"},
            )
    else:
        return JSONResponse(
            status_code=400,
            content={"error": "code or codeB64 must be provided"},
        )

    language = req.language.lower()
    sample = req.sampleCase or ""
    input_data, expected = parse_sample_test_case(sample)

    if language == "python":
        result = await _run_python(code, input_data)
    elif language in {"cpp", "c++"}:
        result = await _run_cpp(code, input_data)
    elif language == "java":
        result = await _run_java(code, input_data)
    elif language == "go":
        result = await _run_go(code, input_data)
    else:
        result = {"stdout": "", "stderr": "Unsupported language", "returncode": 1}

    if expected:
        result["passed"] = (
            result["returncode"] == 0 and result["stdout"].strip() == expected
        )
    return result



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


mcp_server = FastApiMCP(app)
mcp_server.mount()
