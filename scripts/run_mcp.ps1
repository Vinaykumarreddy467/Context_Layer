# Context Layer MCP Server Startup Script
# Run this in PowerShell

Write-Host "Starting Context Layer MCP Server..." -ForegroundColor Green
Write-Host ""

Write-Host "Database and API configuration will be loaded from the project .env file." -ForegroundColor Cyan

Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

Write-Host ""
Write-Host "Starting MCP server (stdio mode)..." -ForegroundColor Green
Write-Host "This window must stay open for the MCP to work." -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop." -ForegroundColor Yellow
Write-Host ""

python mcp_server.py
