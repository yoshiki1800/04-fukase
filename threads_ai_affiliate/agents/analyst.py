"""
エージェント②：アナリスト
投稿履歴を分析して、ライターへの指示書（feedback.json）を生成する
"""
import os
import sys
import json
import anthropic
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.env_loader import load_env

load_env()

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def analyze(dry_run=False):
    history = load_json(os.path.join(DATA_DIR, "post_history.json"))

    if len(history) < 3:
        print("[アナリスト] 投稿履歴が少なすぎます（3件以上必要）。デフォルトフィードバックを使用。")
        default_feedback = {
            "analyzed_at": datetime.now().isoformat(),
            "total_posts": 0,
            "insights": [
                "初期フェーズのため、まずは多様なパターンで投稿してデータを収集する",
                "1行目は数字・具体性・問いかけのどれかを必ず入れる",
                "AI副業・自動化の実体験ネタを優先する"
            ],
            "recommended_patterns": ["P02", "P03", "P09", "P15", "P05"],
            "avoid_patterns": [],
            "top_themes": ["AI活用術", "副業の始め方", "自動化・仕組み化"],
            "avoid_themes": [],
            "tone_guidance": "親しみやすく、失敗も含めた実体験ベースで書く"
        }
        feedback_path = os.path.join(DATA_DIR, "feedback.json")
        if not dry_run:
            save_json(feedback_path, default_feedback)
        return default_feedback

    # パフォーマンスデータがある投稿のみ対象
    posts_with_data = [p for p in history if p.get("metrics")]
    print(f"[アナリスト] 分析対象: {len(posts_with_data)}件")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    history_summary = []
    for p in posts_with_data[-50:]:  # 直近50件
        history_summary.append({
            "pattern": p.get("pattern_id"),
            "theme": p.get("theme"),
            "hook": p.get("content", "")[:50],
            "views": p.get("metrics", {}).get("views", 0),
            "likes": p.get("metrics", {}).get("likes", 0),
            "replies": p.get("metrics", {}).get("replies", 0),
        })

    prompt = f"""あなたはSNSデータ分析のプロです。
以下の投稿パフォーマンスデータを分析して、次の投稿バッチへの指示書を作成してください。

## 投稿データ（直近最大50件）
{json.dumps(history_summary, ensure_ascii=False, indent=2)}

## 出力形式（必ずJSONで返してください）
{{
  "analyzed_at": "分析日時（ISO形式）",
  "total_posts": 分析した投稿数,
  "insights": ["気づき1", "気づき2", "気づき3"],
  "recommended_patterns": ["P01", "P03"などパターンID],
  "avoid_patterns": ["避けるべきパターンID"],
  "top_themes": ["伸びているテーマ"],
  "avoid_themes": ["反応が薄いテーマ"],
  "tone_guidance": "次回バッチのトーン指示"
}}

JSONのみ返してください。"""

    print("[アナリスト] Claude APIで分析中...")
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    feedback = json.loads(raw)
    feedback["analyzed_at"] = datetime.now().isoformat()

    if dry_run:
        print(f"[アナリスト] DRY RUN: 分析完了（保存スキップ）")
        print(json.dumps(feedback, ensure_ascii=False, indent=2))
        return feedback

    save_json(os.path.join(DATA_DIR, "feedback.json"), feedback)
    print(f"[アナリスト] フィードバック保存完了")
    print(f"  推奨パターン: {feedback.get('recommended_patterns')}")
    print(f"  注力テーマ: {feedback.get('top_themes')}")
    return feedback

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    analyze(dry_run=args.dry_run)
