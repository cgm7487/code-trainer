# Code Trainer

This repository provides a small web application to help you practice LeetCode problems. The backend is built with **FastAPI** and tries to fetch the latest problem list from LeetCode. If the remote request fails, it falls back to the local `problems.json` file.

## Running the app

1. Install `uv` and the project dependencies pinned in `requirements.txt`:
   ```bash
   pip install uv
   uv pip install -r requirements.txt
   ```

   These pins currently install:
   `fastapi==0.110.0`, `starlette==0.36.3`,
   `httpx==0.27.2`, `uvicorn==0.29.0` and `jinja2==3.1.2`.
2. Start the server using `uvicorn`:
   ```bash
   uvicorn app:app --reload
   ```
3. Open `http://localhost:8000` in your browser and choose a difficulty.

For languages other than Python you also need local compilers available. On
Debian/Ubuntu you can install them with:

```bash
sudo apt install g++ openjdk-17-jdk-headless golang-go
```

If you run the app via Docker these are installed automatically.

## Online Code Runner

Once you select a problem you can run code directly on the problem page. Select
the desired language (Python, C++, Java or Go), write your solution and press
**Run Code**. The `/execute` endpoint will compile/execute the submitted code
with the corresponding local interpreter and return the output.

## Docker

You can also run the application using Docker Compose:

```bash
docker compose up --build
```

## MCP Server

Add Code Trainer to your MCP server path, e.g. ""**~/Library/Application Support/Claude/claude_desktop_config.json"**

```
{
  "mcpServers": {
   "code-trainer": {
      "command": "/you-mcp-proxy-path/mcp-proxy",
      "args": ["http://127.0.0.1:8877/mcp"]
   }
  }
}

```

## Running Tests

Run the unit tests with:

```bash
pip install -r requirements.txt && pytest
```

The default code template can be inspected in the page's `snippets-data` script tag or verified via the `test_generate_template_fallback` test.

The fallback problems are defined in `problems.json`. Feel free to extend this file with more LeetCode problems.
