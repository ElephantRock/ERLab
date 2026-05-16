@echo off
:: Reranker Microservice Startup
:: Starts jina-reranker-v3 on port 8100
:: Run manually or via Task Scheduler for persistence

cd /d C:\Next-Era\elephant-rock-platform
set PYTHONPATH=.

echo [%date% %time%] Starting reranker service on port 8100...
python -m uvicorn scripts.reranker_service:app --host 0.0.0.0 --port 8100 --log-level info

if %ERRORLEVEL% neq 0 (
    echo [%date% %time%] Reranker service exited with error %ERRORLEVEL%
    pause
)
