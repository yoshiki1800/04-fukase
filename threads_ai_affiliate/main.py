"""
メイン実行スクリプト
毎朝シェルスクリプトから呼び出す。6つのエージェントを順番に実行する。

使い方:
  python3 main.py              # 通常実行（フルサイクル）
  python3 main.py --dry-run    # テスト実行（実際には投稿しない）
  python3 main.py --post-only  # キューから1件投稿のみ
  python3 main.py --research   # リサーチのみ
  python3 main.py --write      # 投稿生成のみ
"""
import os
import sys
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from config.env_loader import load_env

load_env()

from agents.supervisor import monitor, log
from agents.fetcher import fetch_all_pending
from agents.analyst import analyze
from agents.researcher import research
from agents.writer import write_posts
from agents.poster import post_from_queue

def run_daily_cycle(dry_run=False):
    """毎日のフルサイクルを実行"""
    log(f"{'='*50}")
    log(f"日次サイクル開始 {'[DRY RUN]' if dry_run else ''}")
    log(f"{'='*50}")

    # ① スーパーバイザー：異常チェック
    log("\n--- ① スーパーバイザー 監視 ---")
    status = monitor()
    if status.get("status") == "stopped":
        log("KILL_SWITCH ON のため中断します", "CRITICAL")
        return

    # ② フェッチャー：昨日以前の投稿のメトリクス取得
    log("\n--- ② フェッチャー データ取得 ---")
    fetch_all_pending(dry_run=dry_run)

    # ③ アナリスト：パフォーマンス分析→フィードバック生成
    log("\n--- ③ アナリスト 分析 ---")
    analyze(dry_run=dry_run)

    # ④ リサーチャー：ネタ補充（pool内の未使用ネタが10件未満なら実行）
    log("\n--- ④ リサーチャー ネタ収集 ---")
    import json
    with open(os.path.join(os.path.dirname(__file__), "data", "research_pool.json"), encoding="utf-8") as f:
        pool = json.load(f)
    unused = [r for r in pool if not r.get("used")]
    if len(unused) < 10:
        log(f"未使用ネタ{len(unused)}件のため補充実行")
        research(dry_run=dry_run)
    else:
        log(f"未使用ネタ{len(unused)}件あり。補充スキップ。")

    # ⑤ ライター：投稿生成（キューが5件未満なら実行）
    log("\n--- ⑤ ライター 投稿生成 ---")
    with open(os.path.join(os.path.dirname(__file__), "data", "post_queue.json"), encoding="utf-8") as f:
        queue = json.load(f)
    queued = [p for p in queue if p.get("status") == "queued"]
    if len(queued) < 5:
        log(f"キュー{len(queued)}件のため生成実行")
        write_posts(batch_size=5, dry_run=dry_run)
    else:
        log(f"キュー{len(queued)}件あり。生成スキップ。")

    log("\n--- ⑥ ポスター 投稿実行はcronが担当 ---")
    log("main.pyの日次サイクル完了。投稿はcronで分散実行されます。")

def run_post_only(dry_run=False):
    """cronから呼ばれる単発投稿"""
    status = monitor()
    if status.get("status") == "stopped":
        return
    post_from_queue(dry_run=dry_run)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="テスト実行（投稿しない）")
    parser.add_argument("--post-only", action="store_true", help="キューから1件投稿のみ")
    parser.add_argument("--research", action="store_true", help="リサーチのみ")
    parser.add_argument("--write", action="store_true", help="投稿生成のみ")
    parser.add_argument("--batch", type=int, default=5, help="生成する投稿数")
    args = parser.parse_args()

    if args.post_only:
        run_post_only(dry_run=args.dry_run)
    elif args.research:
        research(dry_run=args.dry_run)
    elif args.write:
        write_posts(batch_size=args.batch, dry_run=args.dry_run)
    else:
        run_daily_cycle(dry_run=args.dry_run)
