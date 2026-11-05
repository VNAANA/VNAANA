# Use Python 3.12
FROM python:3.12-slim

# Set working directory inside the container
WORKDIR /app

# Prevent Python from writing bytecode and enable unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code and database migration configuration
COPY Backend/ ./Backend/
COPY Backend/jobs/run_news_pipeline.sh /app/run_news_pipeline.sh
RUN chmod +x /app/run_news_pipeline.sh
COPY alembic.ini .

# Expose the FastAPI port
EXPOSE 8000

# Start the FastAPI application
CMD ["uvicorn", "Backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
