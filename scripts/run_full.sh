#!/bin/bash
# Full pipeline runner
# Usage: ./scripts/run_full.sh [--demo] [--live] [--skip-llm]

PYTHON="python3.12"

echo "=========================================="
echo " SharkNinja Review Intelligence Pipeline"
echo "=========================================="

if [ "$1" = "--demo" ]; then
    echo "Running in DEMO mode (no API keys needed)"
    $PYTHON run_demo.py
elif [ "$1" = "--live" ]; then
    echo "Running with LIVE scraping + LLM classification"
    $PYTHON run_pipeline.py --live "${@:2}"
else
    echo "Running with synthetic data + LLM classification"
    $PYTHON run_pipeline.py "$@"
fi

echo ""
echo "Exporting Tableau data..."
$PYTHON -c "import sys; sys.path.insert(0,'.'); from src.analysis.tableau_export import export_for_tableau; export_for_tableau()"

echo ""
echo "Launching dashboard..."
$PYTHON -m streamlit run src/dashboard/app.py --server.headless true --server.port 8501
