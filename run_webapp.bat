@echo off
chcp 65001 >nul
cd /d "D:\AIcodes\openclaw"
py -3 -m ai_digest.webapp.app
