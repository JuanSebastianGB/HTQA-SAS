# Use official Python image
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy poetry.lock or requirements equivalent
COPY pyproject.toml .

# Install dependencies
RUN pip install --no-cache-dir -e .

# Copy source code
COPY src ./src
COPY tests ./tests
# Copy alembic if it exists (using shell form to handle missing directory)
RUN if [ -d alembic ]; then cp -r alembic ./alembic; fi || true
# Copy .env.example if it exists (using shell form to handle missing file)
RUN if [ -f .env.example ]; then cp .env.example .; fi || true

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]