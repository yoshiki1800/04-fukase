#!/bin/bash
# 毎夜23:30：データ収集＋分析して翌日の投稿に活かす

BASE_DIR="/Users/y.tsuka/claudecodefolda/04_投稿自動化/threads_ai_affiliate"
LOG_DIR="$BASE_DIR/logs"
LOG_FILE="$LOG_DIR/nightly_analysis_$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

echo "=== nightly_analysis.sh 開始: $(date) ===" >> "$LOG_FILE"

echo "フェッチャー起動（データ収集）..." >> "$LOG_FILE"
python3 "$BASE_DIR/agents/fetcher.py" >> "$LOG_FILE" 2>&1

echo "アナリスト起動（分析）..." >> "$LOG_FILE"
python3 "$BASE_DIR/agents/analyst.py" >> "$LOG_FILE" 2>&1

echo "リサーチャー起動（翌日分ネタ補充）..." >> "$LOG_FILE"
python3 "$BASE_DIR/agents/researcher.py" >> "$LOG_FILE" 2>&1

echo "=== nightly_analysis.sh 終了: $(date) ===" >> "$LOG_FILE"
