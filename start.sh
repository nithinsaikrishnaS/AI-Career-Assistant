#!/bin/bash

# 1. Install Playwright browser at runtime (Requirement: Phase 1.2)
# We use chromium as it is most efficient for scraping
python -m playwright install chromium

# 2. Start production server (Requirement: Phase 4)
# We use Gunicorn with Uvicorn workers for high-concurrency production stability
exec gunicorn main:app \
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:$PORT \
    --workers 1 \
    --timeout 120
