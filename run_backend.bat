@echo off
echo Starting Leo Micro Service Backend...

REM Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo Virtual environment not found. Please run: python -m venv venv
    pause
    exit /b 1
)

REM Check if dependencies are installed
echo Checking dependencies...
python -c "import fastapi, uvicorn, supabase, openai, google.genai" 2>nul
if errorlevel 1 (
    echo Installing/updating dependencies...
    pip install -r requirements.txt
) else (
    echo Dependencies already installed.
)

REM Run the FastAPI server
echo Starting FastAPI server on http://localhost:8000
echo API Documentation available at: http://localhost:8000/docs
echo Press Ctrl+C to stop the server
echo.
python main.py

pause