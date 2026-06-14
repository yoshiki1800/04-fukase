#!/bin/bash
# 毎朝7時：今日分の投稿をライターが生成する

BASE_DIR="/Users/y.tsuka/claudecodefolda/04_投稿自動化/threads_ai_affiliate"
LOG_DIR="$BASE_DIR/logs"
LOG_FILE="$LOG_DIR/daily_writer_$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

echo "=== daily_writer.sh 開始: $(date) ===" >> "$LOG_FILE"

# キューが少なければライターを起動
QUEUE_COUNT=$(python3 -c "
import json
try:
    with open('$BASE_DIR/data/post_queue.json') as f:
        q = json.load(f)
    print(len([p for p in q if p.get('status') == 'queued']))
except:
    print(0)
")

echo "現在のキュー数: $QUEUE_COUNT" >> "$LOG_FILE"

if [ "$QUEUE_COUNT" -lt 4 ]; then
    # ネタ不足の場合はリサーチャーで補充してからライターを起動
    RESEARCH_COUNT=$(python3 -c "
import json
try:
    with open('$BASE_DIR/data/research_pool.json') as f:
        r = json.load(f)
    print(len([x for x in r if not x.get('used', False)]))
except:
    print(0)
")
    echo "未使用ネタ数: $RESEARCH_COUNT" >> "$LOG_FILE"
    if [ "$RESEARCH_COUNT" -lt 4 ]; then
        echo "ネタ不足のためリサーチャー起動..." >> "$LOG_FILE"
        python3 "$BASE_DIR/agents/researcher.py" >> "$LOG_FILE" 2>&1
    fi
    echo "ライター起動..." >> "$LOG_FILE"
    python3 "$BASE_DIR/agents/writer.py" --batch 5 >> "$LOG_FILE" 2>&1
    echo "ライター完了" >> "$LOG_FILE"
else
    echo "キューに十分な投稿があります（$QUEUE_COUNT件）。スキップ。" >> "$LOG_FILE"
fi

echo "=== daily_writer.sh 終了: $(date) ===" >> "$LOG_FILE"
