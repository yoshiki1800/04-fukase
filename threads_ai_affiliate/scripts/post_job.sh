#!/bin/bash
# 投稿時刻に起動：キューから1件投稿する

BASE_DIR="/Users/y.tsuka/claudecodefolda/04_投稿自動化/threads_ai_affiliate"
LOG_DIR="$BASE_DIR/logs"
LOG_FILE="$LOG_DIR/post_job_$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

echo "--- post_job.sh 開始: $(date) ---" >> "$LOG_FILE"
python3 "$BASE_DIR/agents/poster.py" >> "$LOG_FILE" 2>&1
echo "--- post_job.sh 終了: $(date) ---" >> "$LOG_FILE"
