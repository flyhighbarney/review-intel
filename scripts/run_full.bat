@echo off
REM Full pipeline runner for Windows
REM Usage: scripts\run_full.bat [--demo] [--live] [--skip-llm]

set PYTHON=C:\Users\lordm\AppData\Local\Programs\Python\Python312\python.exe

echo ==========================================
echo  SharkNinja Review Intelligence Pipeline
echo ==========================================

if "%1"=="--demo" (
    echo Running in DEMO mode (no API keys needed)
    %PYTHON% run_demo.py
) else if "%1"=="--live" (
    echo Running with LIVE scraping + LLM classification
    %PYTHON% run_pipeline.py --live %2 %3
) else (
    echo Running with synthetic data + LLM classification
    %PYTHON% run_pipeline.py %1 %2 %3
)

echo.
echo Exporting Tableau data...
%PYTHON% -c "import sys; sys.path.insert(0,'.'); from src.analysis.tableau_export import export_for_tableau; export_for_tableau()"

echo.
echo Launching dashboard...
%PYTHON% -m streamlit run src/dashboard/app.py --server.headless true --server.port 8501
