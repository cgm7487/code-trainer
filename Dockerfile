FROM python:3.11-slim

# Install uv - a fast Python package manager
RUN pip install --no-cache-dir uv

WORKDIR /app

# Install dependencies using uv
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
