$ErrorActionPreference = "Stop"

Write-Host "Checking/Installing Dependencies..."
# Assume installed via step, but can check here if needed.

Write-Host "Applying Migrations..."
.\.venv\Scripts\python manage.py migrate

Write-Host "Starting Server..."
.\.venv\Scripts\python manage.py runserver 8000
