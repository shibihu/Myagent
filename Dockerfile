# Use official stable slim Python image
FROM python:3.12-slim

# Install system dependencies (git is needed for GitHub cloning support)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory inside container
WORKDIR /app

# Copy dependency requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source files into the container
COPY . .

# Expose port for Koyeb to target (Koyeb defaults to routing to 8000 or custom)
EXPOSE 8000

# Set production/secure environment defaults
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Run uvicorn server on port 8000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
