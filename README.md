# Code Trainer

This repository provides a small web application to help you practice LeetCode problems. The backend is built with **FastAPI** and tries to fetch the latest problem list from LeetCode. If the remote request fails, it falls back to the local `problems.json` file.

## Running the app

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Start the server using `uvicorn`:
   ```bash
   uvicorn app:app --reload
   ```
3. Open `http://localhost:8000` in your browser and choose a difficulty.

The fallback problems are defined in `problems.json`. Feel free to extend this file with more LeetCode problems.
