@echo off
cd /d C:\ProjectS\ai-knowledge-assistant
if not exist logs mkdir logs
.venv\Scripts\python.exe -m collector run >> logs\collector.log 2>&1
