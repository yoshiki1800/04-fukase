"""
エージェント⑥：スーパーバイザー
全体の監視・異常検知・KILL_SWITCH管理
"""
import os
import sys
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.env_loader import load_env

load_env()

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [{level}] {message}"
    print(log_line)

    log_file = os.path.join(LOGS_DIR, f"supervisor_{datetime.now().strftime('%Y%m%d')}.log")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_line + "\n")

def activate_kill_switch():
    """緊急停止：全投稿をストップ"""
    settings_path = os.path.join(BASE_DIR, "config", "settings.json")
    settings = load_json(settings_path)
    settings["safety"]["kill_switch"] = True
    save_json(settings_path, settings)
    log("⚠️ KILL_SWITCH ON - 全投稿を停止しました", "CRITICAL")

def deactivate_kill_switch():
    """投稿再開"""
    settings_path = os.path.join(BASE_DIR, "config", "settings.json")
    settings = load_json(settings_path)
    settings["safety"]["kill_switch"] = False
    save_json(settings_path, settings)
    log("✅ KILL_SWITCH OFF - 投稿を再開しました", "INFO")

def check_posting_rate(history):
    """投稿頻度の異常チェック"""
    now = datetime.now()
    last_hour_posts = [
        p for p in history
        if p.get("posted_at") and
        now - datetime.fromisoformat(p["posted_at"]) < timedelta(hours=1)
    ]
    if len(last_hour_posts) >= 3:
        log(f"⚠️ 1時間以内に{len(last_hour_posts)}件投稿。異常な頻度の可能性。", "WARNING")
        return False
    return True

def check_duplicate_content(history):
    """重複コンテンツのチェック"""
    today = datetime.now().strftime("%Y-%m-%d")
    today_posts = [p for p in history if p.get("posted_at", "").startswith(today)]

    contents = [p.get("content", "") for p in today_posts]
    unique_contents = set(contents)
    if len(contents) != len(unique_contents):
        log(f"⚠️ 本日の投稿に重複コンテンツを検出。", "WARNING")
        return False
    return True

def check_queue_health(queue):
    """キューの健全性チェック"""
    queued = [p for p in queue if p.get("status") == "queued"]
    if len(queued) == 0:
        log("⚠️ キューが空です。ライターを実行してください。", "WARNING")
    else:
        log(f"✅ キュー: {len(queued)}件待機中")

def monitor():
    """全体監視を実行"""
    log("=== スーパーバイザー 監視開始 ===")

    settings = load_json(os.path.join(BASE_DIR, "config", "settings.json"))
    history = load_json(os.path.join(DATA_DIR, "post_history.json"))
    queue = load_json(os.path.join(DATA_DIR, "post_queue.json"))

    if isinstance(history, dict):
        history = []
    if isinstance(queue, dict):
        queue = []

    # KILL_SWITCHチェック
    if settings.get("safety", {}).get("kill_switch"):
        log("⚠️ KILL_SWITCH ON - 投稿は停止中です", "WARNING")
        return {"status": "stopped", "reason": "kill_switch"}

    alerts = []

    # 投稿頻度チェック
    if not check_posting_rate(history):
        alerts.append("高頻度投稿を検出")

    # 重複コンテンツチェック
    if not check_duplicate_content(history):
        alerts.append("重複コンテンツを検出")

    # キュー健全性チェック
    check_queue_health(queue)

    # 本日の投稿数
    today = datetime.now().strftime("%Y-%m-%d")
    today_count = len([p for p in history if p.get("posted_at", "").startswith(today)])
    max_per_day = settings["posting"]["max_per_day"]
    log(f"本日の投稿数: {today_count}/{max_per_day}")

    # 連続エラーが多い場合はKILL_SWITCH
    if len(alerts) >= 3:
        log("⚠️ 複数の異常を検出。KILL_SWITCHを起動します。", "CRITICAL")
        activate_kill_switch()
        return {"status": "stopped", "alerts": alerts}

    if alerts:
        log(f"警告: {', '.join(alerts)}", "WARNING")
    else:
        log("✅ 異常なし。正常稼働中。")

    return {"status": "ok", "today_posts": today_count, "queue_size": len([p for p in queue if p.get("status") == "queued"])}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--kill", action="store_true", help="緊急停止")
    parser.add_argument("--resume", action="store_true", help="投稿再開")
    args = parser.parse_args()

    if args.kill:
        activate_kill_switch()
    elif args.resume:
        deactivate_kill_switch()
    else:
        monitor()
