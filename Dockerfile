FROM python:3.11-slim

# Ensure consistent HOME and Playwright browser path
ENV HOME=/root
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

# Install system dependencies for Playwright Chromium
# Let Playwright install its own system dependencies to avoid version mismatches
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Install Python dependencies
RUN uv sync --no-dev --frozen

# Install Playwright Chromium browser with system dependencies
RUN uv run playwright install --with-deps chromium

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data

EXPOSE 8080

VOLUME /app/data

CMD ["uv", "run", "uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8080"]
