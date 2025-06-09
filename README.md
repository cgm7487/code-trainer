# Code Trainer

This repository provides a small web application to help you practice LeetCode problems. The backend is built with **FastAPI** and tries to fetch the latest problem list from LeetCode. If the remote request fails, it falls back to the local `problems.json` file.

## Running the app

1. Install `uv` and the project dependencies:
   ```bash
   pip install uv
   uv pip install -r requirements.txt
   ```
2. Start the server using `uvicorn`:
   ```bash
   uvicorn app:app --reload
   ```
3. Open `http://localhost:8000` in your browser and choose a difficulty.

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

The fallback problems are defined in `problems.json`. Feel free to extend this file with more LeetCode problems.
