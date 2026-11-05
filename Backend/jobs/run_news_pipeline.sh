#!/bin/sh
cd /app
export PYTHONPATH=/app
exec /usr/local/bin/python /app/Backend/jobs/run_news_pipeline.py