"""
エージェント④：ポスター
キューの投稿をThreads APIで実際に投稿する。
アフィリエイト投稿の場合はコメント欄にPRリンクを自動配置。
"""
import os
import sys
import json
import time
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.env_loader import load_env

load_env()

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")
DATA_DIR = os.path.join(BASE_DIR, "data")

THREADS_API_BASE = "https://graph.threads.net/v1.0"

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def create_thread_post(user_id, access_token, text):
    """Threads投稿コンテナを作成"""
    url = f"{THREADS_API_BASE}/{user_id}/threads"
    params = {
        "media_type": "TEXT",
        "text": text,
        "access_token": access_token
    }
    res = requests.post(url, data=params)
    return res.json()

def publish_thread_post(user_id, access_token, creation_id):
    """コンテナを公開"""
    url = f"{THREADS_API_BASE}/{user_id}/threads_publish"
    params = {
        "creation_id": creation_id,
        "access_token": access_token
    }
    res = requests.post(url, data=params)
    return res.json()

def reply_to_post(user_id, access_token, post_id, text):
    """投稿にコメント（返信）を追加"""
    url = f"{THREADS_API_BASE}/{user_id}/threads"
    params = {
        "media_type": "TEXT",
        "text": text,
        "reply_to_id": post_id,
        "access_token": access_token
    }
    res = requests.post(url, data=params)
    container = res.json()
    if "id" not in container:
        return container

    time.sleep(5)
    return publish_thread_post(user_id, access_token, container["id"])

def get_affiliate_comment(post, offers):
    """アフィリエイト投稿に適した案件のコメント文を返す"""
    for offer in offers:
        if offer.get("affiliate_url") and "ここに" not in offer.get("affiliate_url", ""):
            target_patterns = offer.get("target_post_patterns", [])
            if not target_patterns or post.get("pattern_id") in target_patterns:
                pr_text = offer.get("pr_text", "")
                url = offer.get("affiliate_url", "")
                if pr_text and url:
                    return f"【PR】{pr_text}\n👉 {url}"
    return None

def post_one(post, dry_run=False):
    """1件投稿を実行"""
    user_id = os.environ["THREADS_USER_ID"]
    token = os.environ["THREADS_ACCESS_TOKEN"]
    offers = load_json(os.path.join(KNOWLEDGE_DIR, "affiliate_offers.json"))["offers"]
    settings = load_json(os.path.join(BASE_DIR, "config", "settings.json"))

    if settings.get("safety", {}).get("kill_switch"):
        print("[ポスター] ⚠️ KILL_SWITCH ON。投稿停止中。")
        return None

    content = post["content"]
    post_type = post.get("post_type", "通常")
    affiliate_fit = post.get("affiliate_fit", False)

    if dry_run:
        print(f"[ポスター] DRY RUN: 投稿をシミュレート")
        print(f"  本文: {content[:80]}...")
        print(f"  タイプ: {post_type}")
        if affiliate_fit:
            comment = get_affiliate_comment(post, offers)
            if comment:
                print(f"  PRコメント: {comment[:60]}...")
        return {"dry_run": True, "content": content}

    print(f"[ポスター] 投稿中: {content[:40]}...")

    # コンテナ作成
    container = create_thread_post(user_id, token, content)
    if "error" in container:
        print(f"[ポスター] ❌ コンテナ作成エラー: {container['error']['message']}")
        return None

    creation_id = container["id"]
    time.sleep(5)  # API推奨の待機

    # 公開
    result = publish_thread_post(user_id, token, creation_id)
    if "error" in result:
        print(f"[ポスター] ❌ 公開エラー: {result['error']['message']}")
        return None

    post_id = result["id"]
    print(f"[ポスター] ✅ 投稿完了: {post_id}")

    # コメント誘導型は自動で続きをコメントへ
    if post_type == "コメント誘導":
        time.sleep(3)
        reply_to_post(user_id, token, post_id, "↓ コメントで教えてください！読んでいます😊")

    # アフィリエイトコメントを配置
    if affiliate_fit:
        comment_text = get_affiliate_comment(post, offers)
        if comment_text:
            time.sleep(3)
            reply_to_post(user_id, token, post_id, comment_text)
            print(f"[ポスター] PRコメント配置完了")

    return {"post_id": post_id, "content": content, "posted_at": datetime.now().isoformat()}

def post_from_queue(dry_run=False):
    """キューから1件投稿して履歴に移動"""
    queue = load_json(os.path.join(DATA_DIR, "post_queue.json"))
    history = load_json(os.path.join(DATA_DIR, "post_history.json"))
    settings = load_json(os.path.join(BASE_DIR, "config", "settings.json"))

    # 1日の上限チェック
    today = datetime.now().strftime("%Y-%m-%d")
    today_posts = [p for p in history if p.get("posted_at", "").startswith(today)]
    max_per_day = settings["posting"]["max_per_day"]
    if len(today_posts) >= max_per_day:
        print(f"[ポスター] 本日の上限({max_per_day}件)に達しました。")
        return None

    pending = [p for p in queue if p.get("status") == "queued"]
    if not pending:
        print("[ポスター] キューに投稿がありません。")
        return None

    post = pending[0]
    result = post_one(post, dry_run=dry_run)

    if result and not dry_run:
        post["status"] = "posted"
        post["post_id"] = result.get("post_id")
        post["posted_at"] = result.get("posted_at")
        post["metrics"] = None

        # キューから削除して履歴に追加
        queue = [p for p in queue if p["id"] != post["id"]]
        history.append(post)
        save_json(os.path.join(DATA_DIR, "post_queue.json"), queue)
        save_json(os.path.join(DATA_DIR, "post_history.json"), history)

    return result

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    post_from_queue(dry_run=args.dry_run)
