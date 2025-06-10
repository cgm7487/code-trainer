FROM python:3.11-slim

# Install compilers for the online code runner
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        g++ \
        openjdk-17-jdk-headless \
        golang-go && \
    rm -rf /var/lib/apt/lists/*

# Install uv - a fast Python package manager
RUN pip install --no-cache-dir uv

WORKDIR /app

# Install dependencies using uv
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8877

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8877"]
