@echo off
chcp 65001 >nul
cd /d "D:\AIcodes\openclaw"
wsl.exe bash -lc "cd /mnt/d/AIcodes/openclaw && /mnt/d/AIcodes/openclaw/.venv/bin/python -m ai_digest.webapp.app"
