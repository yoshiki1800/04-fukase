"""
エージェント⑤：フェッチャー
投稿後24時間以降の投稿のメトリクス（閲覧数・いいね・リプライ）をThreads APIから取得する
"""
import os
import sys
import json
import requests
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.env_loader import load_env

load_env()

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

THREADS_API_BASE = "https://graph.threads.net/v1.0"

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def fetch_metrics(post_id, access_token):
    """投稿のメトリクスを取得"""
    url = f"{THREADS_API_BASE}/{post_id}/insights"
    params = {
        "metric": "views,likes,replies,reposts,quotes",
        "access_token": access_token
    }
    res = requests.get(url, params=params)
    data = res.json()

    if "error" in data:
        return None

    metrics = {}
    for item in data.get("data", []):
        metrics[item["name"]] = item.get("values", [{}])[0].get("value", 0)
    return metrics

def fetch_all_pending(dry_run=False):
    """メトリクス未取得の投稿（24時間以上経過）を一括取得"""
    token = os.environ["THREADS_ACCESS_TOKEN"]
    history = load_json(os.path.join(DATA_DIR, "post_history.json"))

    now = datetime.now()
    updated = 0

    for post in history:
        if post.get("metrics") is not None:
            continue
        if not post.get("post_id") or not post.get("posted_at"):
            continue

        posted_at = datetime.fromisoformat(post["posted_at"])
        if now - posted_at < timedelta(hours=24):
            continue  # まだ24時間経っていない

        if dry_run:
            print(f"[フェッチャー] DRY RUN: {post['post_id']} のメトリクスを取得予定")
            continue

        metrics = fetch_metrics(post["post_id"], token)
        if metrics:
            post["metrics"] = metrics
            post["metrics_fetched_at"] = now.isoformat()
            updated += 1
            print(f"[フェッチャー] ✅ {post['post_id']}: views={metrics.get('views', 0)}, likes={metrics.get('likes', 0)}")
        else:
            print(f"[フェッチャー] ⚠️ {post['post_id']}: メトリクス取得失敗")

    if not dry_run and updated > 0:
        save_json(os.path.join(DATA_DIR, "post_history.json"), history)
        print(f"[フェッチャー] {updated}件のメトリクスを更新しました")
    elif updated == 0:
        print("[フェッチャー] 更新対象なし")

    return updated

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    fetch_all_pending(dry_run=args.dry_run)
