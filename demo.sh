#!/usr/bin/env bash
# Record this with `script` or a screencast tool. Reproduces the live demo.
# Environment: D:\dev\giveaway\deductible, venv at ../.venv-llm
cd /d/dev/giveaway/deductible

echo "=== STEP 1: categorize a real, messy bank export (hybrid, fully offline) ==="
../.venv-llm/Scripts/python.exe deductible.py --csv sample_data/transactions_messy.csv \
    --out demo_out.csv --mode hybrid

echo ""
echo "=== STEP 2: talk to your books (grounded in precomputed Python facts) ==="
../.venv-llm/Scripts/python.exe ask.py --csv demo_out.csv \
    --question "What are my biggest deductible expenses, and what should I double-check before filing?"

echo ""
echo "=== STEP 3: swap the model by changing one path (open-weights sell point) ==="
../.venv-llm/Scripts/python.exe deductible.py --csv sample_data/transactions_messy.csv \
    --out demo_out_3b.csv --mode model --model models/qwen2.5-3b-instruct-q4_k_m.gguf
