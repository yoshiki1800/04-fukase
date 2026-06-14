#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════╗
║            x_grow_master.py — X Growth Master System               ║
║       自己学習 × マルチエージェント × 相互監視 完全自動投稿        ║
║                                                                      ║
║  エージェント構成:                                                   ║
║    ① Analyst_Agent   — 前回投稿の成績を分析し学習ログを更新        ║
║    ② Creator_Agent   — 投稿案を生成                                 ║
║    ③ Auditor_Agent   — 内容・訴求力を10点満点で査定                ║
║    ④ Optimizer_Agent — Xアルゴリズム最適化を10点満点で査定         ║
║    ⑤ Editor_Agent    — 合否判定・差し戻しループ制御（最大3回）      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

# ════════════════════════════════════════════════════════════════════════
# PHASE 0: ライブラリ自動チェック＆インストール（最優先で実行）
# ════════════════════════════════════════════════════════════════════════

import sys
import os
import subprocess
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


def _pip_install(pkg: str) -> bool:
    """
    ライブラリをインストールする。
    macOS のシステムPython制限に対応するため、以下の順で試みる:
      1. 通常インストール
      2. --user フラグ付きインストール
      3. --break-system-packages フラグ付きインストール
    Returns: True=成功, False=失敗
    """
    base_cmd = [sys.executable, "-m", "pip", "install", pkg, "-q"]
    strategies = [
        base_cmd,
        base_cmd + ["--user"],
        base_cmd + ["--break-system-packages"],
    ]
    for cmd in strategies:
        try:
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            continue
    return False


def _install_missing_libs() -> None:
    """起動時に必要ライブラリを自動チェック・インストールする"""
    lib_map = {
        "tweepy":    "tweepy>=4.0.0",
        "anthropic": "anthropic>=0.25.0",
        "dotenv":    "python-dotenv>=1.0.0",
    }
    missing = []
    for mod, pkg in lib_map.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append((mod, pkg))

    if not missing:
        return

    print("\n📦 必要なライブラリが見つかりません。自動インストールを開始します…\n")
    failed = []
    for mod, pkg in missing:
        print(f"   ⏳ pip install {pkg} …", end="", flush=True)
        if _pip_install(pkg):
            print(" ✅")
        else:
            print(f" ❌")
            failed.append(pkg)

    if failed:
        print(f"\n❌ 以下のライブラリのインストールに失敗しました:")
        for pkg in failed:
            print(f"   pip install {pkg}")
        print("\n💡 仮想環境での実行をお試しください:")
        print("   python3 -m venv venv && source venv/bin/activate && python3 x_grow_master.py")
        sys.exit(1)

    print("\n✅ 全ライブラリのインストール完了！\n")


_install_missing_libs()

# ─── 自動インストール後のimport ───────────────────────────────────────
import tweepy                              # noqa: E402
import anthropic                           # noqa: E402
from dotenv import load_dotenv             # noqa: E402


# ════════════════════════════════════════════════════════════════════════
# PHASE 1: 定数・パス定義
# ════════════════════════════════════════════════════════════════════════

BASE_DIR        = Path(__file__).parent
ENV_FILE        = BASE_DIR / ".env"
HISTORY_FILE    = BASE_DIR / "x_learning_history.md"
LAST_TWEET_FILE = BASE_DIR / "last_tweet.json"

AI_MODEL      = "claude-opus-4-7"   # 使用するClaude モデル
MAX_RETRY     = 3                    # 最大リトライ回数
PASS_SCORE    = 16                   # 合格ライン（20点満点中）
TWEET_MAX_LEN = 140                  # ツイート最大文字数

DIVIDER      = "━" * 62
THIN_DIVIDER = "─" * 62


# ════════════════════════════════════════════════════════════════════════
# PHASE 2: 初期設定（.env 自動生成）
# ════════════════════════════════════════════════════════════════════════

def setup_env() -> None:
    """
    .env ファイルが存在する場合はそのまま読み込む。
    存在しない場合は Claude Code でのセットアップを案内して終了する。
    ※ セットアップは Claude Code（CLAUDE.md）が担当します。
    """
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
        return

    print(f"\n{DIVIDER}")
    print("⚠️   .env ファイルが見つかりません")
    print(DIVIDER)
    print("""
  このスクリプトを実行するには、最初に Claude Code でセットアップが必要です。

  ▼ セットアップ手順

    1. このフォルダを Claude Code で開く
       （Claude Code のターミナルでこのフォルダに移動して起動）

    2. Claude Code に話しかける
       「セットアップしてください」や「setup」と入力するだけで
       Claude が対話形式でAPIキーの設定をサポートします。

    3. セットアップ完了後、もう一度このスクリプトを実行してください
       python3 x_grow_master.py

  💡 Claude Code とは？
     Anthropic が提供する AI コーディングアシスタントです。
     https://claude.ai/code からダウンロードできます。
""")
    print(DIVIDER)
    sys.exit(0)


# ════════════════════════════════════════════════════════════════════════
# PHASE 3: 成長ログ（学習履歴）の初期化・読み書き
# ════════════════════════════════════════════════════════════════════════

INITIAL_HISTORY = """\
# 📚 X Growth Learning History
> このファイルはシステムが自動管理します。手動編集も可能です。

---

## 🔰 基本原則（初期Tips）

1. **フックの重要性**: 最初の1〜2行で読者を引き込まないと続きは読まれない。
   数字・疑問・驚き・共感のいずれかを冒頭に入れること。
2. **見やすさ**: 改行を積極的に使い1文を短くまとめる。ブロックが長いと離脱される。
3. **具体性**: 「すごい」「大切」など抽象語ではなく、数字・事例で語ること。
4. **CTA（行動喚起）**: 最後に「いいね」「RT」「コメント」を促す一言を入れると反応率が上がる。
5. **投稿タイミング**: 朝7〜9時・昼12時・夜21〜23時が反応を得やすい傾向がある。
6. **140文字の制限**: 文字数ギリギリを狙いつつ詰め込みすぎず余白を残す。
7. **絵文字の効果**: 冒頭・見出し部分に1〜2個の絵文字が視認性を高める。

---

## 📊 過去の投稿分析

（初回起動のため、分析データはまだありません。投稿後に自動更新されます。）

---

## 🎯 次回投稿への改善指示

（初回起動のため、まだありません。投稿後に自動生成されます。）
"""


def init_history() -> None:
    """x_learning_history.md が存在しない場合、初期テンプレートで生成"""
    if not HISTORY_FILE.exists():
        HISTORY_FILE.write_text(INITIAL_HISTORY, encoding="utf-8")
        print(f"📖 学習ログを初期化しました: {HISTORY_FILE.name}")


def load_history() -> str:
    return HISTORY_FILE.read_text(encoding="utf-8")


def save_history(content: str) -> None:
    HISTORY_FILE.write_text(content, encoding="utf-8")


# ════════════════════════════════════════════════════════════════════════
# PHASE 4: ツイートID管理（last_tweet.json）
# ════════════════════════════════════════════════════════════════════════

def load_last_tweet() -> Optional[dict]:
    """最後に投稿したツイートの情報を読み込む"""
    if not LAST_TWEET_FILE.exists():
        return None
    try:
        return json.loads(LAST_TWEET_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_last_tweet(tweet_id: str, text: str) -> None:
    """投稿したツイート情報をローカルに保存（次回分析用）"""
    data = {
        "tweet_id":  tweet_id,
        "text":      text,
        "posted_at": datetime.now().isoformat(),
    }
    LAST_TWEET_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ════════════════════════════════════════════════════════════════════════
# PHASE 5: X API クライアント初期化
# ════════════════════════════════════════════════════════════════════════

def init_x_client() -> tweepy.Client:
    """Tweepy v2 クライアントを初期化して返す"""
    api_key              = os.getenv("X_API_KEY", "")
    api_secret           = os.getenv("X_API_SECRET", "")
    access_token         = os.getenv("X_ACCESS_TOKEN", "")
    access_token_secret  = os.getenv("X_ACCESS_TOKEN_SECRET", "")
    bearer_token         = os.getenv("X_BEARER_TOKEN") or None

    if not all([api_key, api_secret, access_token, access_token_secret]):
        raise ValueError(
            "X API の認証情報が .env に不足しています。\n"
            "   X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_TOKEN_SECRET を確認してください。"
        )

    return tweepy.Client(
        bearer_token=bearer_token,
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
        wait_on_rate_limit=True,
    )


# ════════════════════════════════════════════════════════════════════════
# PHASE 6: エージェント① — 成長アナリスト（Analyst_Agent）
# ════════════════════════════════════════════════════════════════════════

def fetch_tweet_metrics(client: tweepy.Client, tweet_id: str) -> dict:
    """
    ツイートの公開・非公開メトリクスを取得する。
    アクセス権限が不足している場合は取得できた指標のみ返す。
    ※ インプレッションは Twitter API Basic 以上のプランが必要。
    """
    metrics = {
        "impressions": None,
        "likes":       None,
        "retweets":    None,
        "replies":     None,
        "error":       None,
    }
    try:
        response = client.get_tweet(
            id=tweet_id,
            tweet_fields=["public_metrics", "non_public_metrics"],
        )
        if response.data:
            tweet = response.data
            pub = getattr(tweet, "public_metrics", None)
            if pub:
                metrics["likes"]    = pub.get("like_count")
                metrics["retweets"] = pub.get("retweet_count")
                metrics["replies"]  = pub.get("reply_count")
            priv = getattr(tweet, "non_public_metrics", None)
            if priv:
                metrics["impressions"] = priv.get("impression_count")
    except tweepy.errors.Forbidden:
        metrics["error"] = (
            "非公開メトリクス（インプレッション）の取得には "
            "Twitter API Basic 以上のプランが必要です。"
        )
    except tweepy.errors.TweepyException as e:
        metrics["error"] = str(e)
    except Exception as e:
        metrics["error"] = f"予期しないエラー: {e}"

    return metrics


def analyst_agent(
    ai:         anthropic.Anthropic,
    last_tweet: dict,
    metrics:    dict,
    genre:      str,
) -> str:
    """
    エージェント①: 成長アナリスト
    前回投稿のメトリクスを分析し、学習ログ（x_learning_history.md）を自律的に更新する。
    """
    print(f"\n{'🔍 ' * 3} Analyst_Agent 分析中…")

    history       = load_history()
    impressions   = metrics["impressions"] if metrics["impressions"] is not None else "取得不可"
    likes         = metrics["likes"]       if metrics["likes"]       is not None else "取得不可"
    retweets      = metrics["retweets"]    if metrics["retweets"]    is not None else "取得不可"
    replies       = metrics["replies"]     if metrics["replies"]     is not None else "取得不可"
    error_note    = f"\n※ 注記: {metrics['error']}" if metrics["error"] else ""

    prompt = f"""
あなたはXの成長戦略アナリストです。
「前回投稿内容」と「実際のエンゲージメント指標」を元に分析し、
「学習ログ（x_learning_history.md）」を更新してください。

## ターゲットジャンル
{genre}

## 前回の投稿テキスト
---
{last_tweet["text"]}
---

## 実際のパフォーマンス指標
- インプレッション数 : {impressions}
- いいね数           : {likes}
- リポスト数         : {retweets}
- リプライ数         : {replies}{error_note}

## 現在の学習ログ
---
{history}
---

## 指示
1. 前回投稿の「良かった点」「改善点」を具体的に鋭く分析する
2. 次回投稿への改善指示を箇条書きで3〜5点まとめる
3. 現在の学習ログ全体を**更新した完全な Markdown テキスト**として出力する
   （基本原則セクションは保持しつつ、「過去の投稿分析」「次回投稿への改善指示」を更新する）

## 出力
更新済みの学習ログ（Markdown 全文）のみを出力してください。余計な説明文は不要です。
"""

    try:
        response = ai.messages.create(
            model=AI_MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        updated_history = response.content[0].text.strip()
        save_history(updated_history)
        print("   ✅ 分析完了・学習ログを更新しました")
        return updated_history
    except anthropic.APIError as e:
        print(f"   ⚠️  AI API エラー: {e}\n   学習ログはそのまま維持します。")
        return history


# ════════════════════════════════════════════════════════════════════════
# PHASE 7: エージェント② — 構成作家（Creator_Agent）
# ════════════════════════════════════════════════════════════════════════

def creator_agent(
    ai:       anthropic.Anthropic,
    genre:    str,
    history:  str,
    feedback: str = "",
    attempt:  int = 1,
) -> str:
    """
    エージェント②: 構成作家
    ジャンルと学習ログをインプットに投稿案を生成する。
    feedback が渡された場合は監査官のダメ出しを反映した改善版を生成する。
    """
    label = "初稿生成" if attempt == 1 else f"修正版 {attempt}稿"
    print(f"\n{'✍️  ' * 3} Creator_Agent 起動中（{label}）…")

    feedback_block = f"""
## ❌ 前回投稿がNGとなった理由（全て改善して再生成すること）
{feedback}
""" if feedback else ""

    prompt = f"""
あなたは優秀なXの投稿専門ライターです。
以下の条件を厳守して、今回のXへの投稿テキストを**1つだけ**作成してください。

## ターゲットジャンル・ペルソナ
{genre}

## 学習ログ（前回の反省・改善指示）
{history}
{feedback_block}

## 絶対守る条件
- **{TWEET_MAX_LEN}文字以内**（句読点・絵文字・改行コードも全て含む）
- 最初の1〜2行で読者を引き込む強い「フック」を入れる
- 具体的な数字・事例を必ず入れる
- 適切な改行で読みやすくする
- ターゲット層の悩みや興味に刺さる内容にする
- 最後に自然なCTA（いいね・RT・コメント促進）を入れる

## 出力
投稿テキストのみを出力してください。タイトルや説明文・引用符は不要です。
"""

    try:
        response = ai.messages.create(
            model=AI_MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        tweet_text = response.content[0].text.strip().strip('"\'')
        char_count = len(tweet_text)
        over = f" ⚠️ {TWEET_MAX_LEN}文字超過！" if char_count > TWEET_MAX_LEN else ""
        print(f"   ✅ 投稿案生成完了（{char_count}文字）{over}")
        return tweet_text
    except anthropic.APIError as e:
        raise RuntimeError(f"Creator_Agent API エラー: {e}") from e


# ════════════════════════════════════════════════════════════════════════
# PHASE 8: エージェント③ — クリティカル監査官（Auditor_Agent）
# ════════════════════════════════════════════════════════════════════════

def auditor_agent(
    ai:         anthropic.Anthropic,
    tweet_text: str,
    genre:      str,
) -> tuple:
    """
    エージェント③: クリティカル監査官
    ターゲット訴求力と内容の充実度を10点満点で査定する。
    Returns: (score: int, feedback: str)
    """
    print(f"\n{'🕵️  ' * 3} Auditor_Agent 起動中（内容・訴求力査定）…")

    prompt = f"""
あなたはXマーケティングの厳格な監査官です。
投稿テキストをターゲット層への訴求力と内容の充実度の観点から**厳しく**査定してください。

## ターゲットジャンル・ペルソナ
{genre}

## 評価対象の投稿テキスト
---
{tweet_text}
---

## 採点基準（10点満点）
- 10点 : ターゲット層が思わずいいね・RTしたくなる完璧なレベル
- 8〜9点 : 刺さるが、もう一押し磨ける
- 6〜7点 : 普通。印象に残らない
- 4〜5点 : 内容が薄い・抽象的すぎる
- 1〜3点 : ターゲット層に全く刺さらない

## 出力形式（必ずこの形式で出力）
SCORE: [0〜10の整数のみ]
FEEDBACK:
[具体的な改善フィードバック。箇条書き3点以内]
"""

    return _parse_agent_response(ai, prompt, "Auditor", "内容監査")


# ════════════════════════════════════════════════════════════════════════
# PHASE 9: エージェント④ — Xトレンド最適化分析官（Optimizer_Agent）
# ════════════════════════════════════════════════════════════════════════

def optimizer_agent(
    ai:         anthropic.Anthropic,
    tweet_text: str,
) -> tuple:
    """
    エージェント④: Xトレンド最適化分析官
    Xアルゴリズム最適化（フック・改行・文字数）を10点満点で査定する。
    Returns: (score: int, feedback: str)
    """
    print(f"\n{'📊 ' * 3} Optimizer_Agent 起動中（アルゴリズム最適化査定）…")

    char_count = len(tweet_text)
    prompt = f"""
あなたはX（旧Twitter）アルゴリズム最適化の専門家です。
投稿テキストをXアルゴリズムへの最適度で**厳格に**査定してください。

## 評価対象の投稿テキスト（{char_count}文字 / {TWEET_MAX_LEN}文字制限）
---
{tweet_text}
---

## 採点基準（10点満点）
以下の4観点で査定する：
1. **フックの強度**（3点）: 最初の1〜2行で読者をスクロール停止させられるか？
2. **改行・読みやすさ**（3点）: 適切な改行があり一目で読めるか？
3. **文字数最適化**（2点）: {TWEET_MAX_LEN}文字制限内に収まり情報密度は適切か？
4. **エンゲージメント誘発**（2点）: いいね・RT・コメントを促す仕掛けがあるか？

## 出力形式（必ずこの形式で出力）
SCORE: [0〜10の整数のみ]
FEEDBACK:
[各観点について具体的なフィードバック。箇条書き4点]
"""

    return _parse_agent_response(ai, prompt, "Optimizer", "アルゴリズム査定")


def _parse_agent_response(
    ai:       anthropic.Anthropic,
    prompt:   str,
    agent:    str,
    label:    str,
) -> tuple:
    """エージェントのレスポンスからスコアとフィードバックをパースする共通処理"""
    try:
        response = ai.messages.create(
            model=AI_MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
    except anthropic.APIError as e:
        print(f"   ⚠️  {agent}_Agent API エラー: {e}  → スコア 0 として処理します")
        return 0, f"{agent}_Agent でエラーが発生しました: {e}"

    # SCORE 行をパース
    score = 5  # デフォルト中間値
    for line in raw.split("\n"):
        if line.strip().startswith("SCORE:"):
            try:
                score = max(0, min(10, int(line.replace("SCORE:", "").strip())))
            except ValueError:
                pass
            break

    # FEEDBACK 以降をパース
    fb_start = raw.find("FEEDBACK:")
    feedback = raw[fb_start + len("FEEDBACK:"):].strip() if fb_start != -1 else raw

    print(f"   ✅ {label}完了 → {score}/10点")
    return score, feedback


# ════════════════════════════════════════════════════════════════════════
# PHASE 10: エージェント⑤ — 編集長ループ（Editor_Agent + 差し戻し制御）
# ════════════════════════════════════════════════════════════════════════

def editor_loop(
    ai:      anthropic.Anthropic,
    genre:   str,
    history: str,
) -> dict:
    """
    エージェント⑤: 編集長ループ
    Creator → Auditor + Optimizer → 合否判定 → 最大 MAX_RETRY 回リトライ
    合格ライン: PASS_SCORE 点以上（20点満点）
    Returns: 最終採用結果の辞書
    """
    best_result      = None
    best_score       = -1
    feedback_combined = ""

    for attempt in range(1, MAX_RETRY + 1):

        # ── 投稿案を生成 ──────────────────────────────────────────────
        tweet_text = creator_agent(
            ai, genre, history,
            feedback=feedback_combined,
            attempt=attempt,
        )

        # ── 内容査定 ──────────────────────────────────────────────────
        auditor_score, auditor_feedback = auditor_agent(ai, tweet_text, genre)

        # ── アルゴリズム査定 ──────────────────────────────────────────
        optimizer_score, optimizer_feedback = optimizer_agent(ai, tweet_text)

        total_score = auditor_score + optimizer_score
        passed      = total_score >= PASS_SCORE

        result = {
            "tweet_text":        tweet_text,
            "auditor_score":     auditor_score,
            "auditor_feedback":  auditor_feedback,
            "optimizer_score":   optimizer_score,
            "optimizer_feedback": optimizer_feedback,
            "total_score":       total_score,
            "attempt":           attempt,
            "passed":            passed,
        }

        if total_score > best_score:
            best_score  = total_score
            best_result = result

        # ── 合否判定 ──────────────────────────────────────────────────
        if passed:
            print(f"\n{'─'*62}")
            print(f"✅ 編集長判定: 合格！（{total_score}/20点 ≥ {PASS_SCORE}点）")
            print(f"{'─'*62}")
            break
        else:
            if attempt < MAX_RETRY:
                print(f"\n{'─'*62}")
                print(f"❌ スコア不十分のため差し戻し（{attempt}回目）")
                print(f"   合計スコア: {total_score}/20点  合格ライン: {PASS_SCORE}点")
                print(f"{'─'*62}")
                feedback_combined = (
                    f"【Auditor からのフィードバック（内容査定: {auditor_score}/10）】\n"
                    f"{auditor_feedback}\n\n"
                    f"【Optimizer からのフィードバック（アルゴリズム査定: {optimizer_score}/10）】\n"
                    f"{optimizer_feedback}"
                )
                time.sleep(0.5)
            else:
                print(f"\n{'─'*62}")
                print(f"⚠️  {MAX_RETRY}回リトライしましたが合格ラインに未達。")
                print(f"   最高スコアの投稿案（{best_score}/20点）を採用します。")
                print(f"{'─'*62}")

    return best_result


# ════════════════════════════════════════════════════════════════════════
# PHASE 11: 結果表示（美しいコンソール出力）
# ════════════════════════════════════════════════════════════════════════

def display_result(result: dict) -> None:
    """最終結果をリッチにコンソール表示する"""
    tweet      = result["tweet_text"]
    char_count = len(tweet)
    total      = result["total_score"]
    passed     = result["passed"]

    # ── ヘッダー ──────────────────────────────────────────────────────
    print(f"\n{DIVIDER}")
    print("🎯   最終投稿案レポート")
    print(DIVIDER)

    # ── 投稿テキスト ──────────────────────────────────────────────────
    char_color = "✅" if char_count <= TWEET_MAX_LEN else "❌ 超過！"
    print(f"\n📝 投稿テキスト（{char_count}/{TWEET_MAX_LEN}文字 {char_color}）")
    print(f"\n{'─'*50}")
    print(tweet)
    print(f"{'─'*50}\n")

    # ── Auditor スコア ────────────────────────────────────────────────
    a_bar = _score_bar(result["auditor_score"], 10)
    print(f"🕵️  Auditor_Agent（内容・訴求力）: {result['auditor_score']}/10  {a_bar}")
    for line in result["auditor_feedback"].split("\n"):
        stripped = line.strip()
        if stripped:
            print(f"   {stripped}")

    # ── Optimizer スコア ──────────────────────────────────────────────
    print()
    o_bar = _score_bar(result["optimizer_score"], 10)
    print(f"📊 Optimizer_Agent（Xアルゴリズム）: {result['optimizer_score']}/10  {o_bar}")
    for line in result["optimizer_feedback"].split("\n"):
        stripped = line.strip()
        if stripped:
            print(f"   {stripped}")

    # ── 総合スコア ────────────────────────────────────────────────────
    print(f"\n{DIVIDER}")
    total_bar  = _score_bar(total, 20)
    status_str = "✅ 合格" if passed else f"⚠️  リトライ最高点（未達）"
    print(f"📊 総合スコア: {total}/20点  {total_bar}  {status_str}")
    print(f"   合格ライン: {PASS_SCORE}/20点 ｜ 試行回数: {result['attempt']}回")
    print(DIVIDER)


def _score_bar(score: int, max_score: int, width: int = 10) -> str:
    """スコアをビジュアルなバーで表示"""
    filled = round(score / max_score * width)
    bar    = "█" * filled + "░" * (width - filled)
    return f"[{bar}]"


# ════════════════════════════════════════════════════════════════════════
# PHASE 12: X への投稿
# ════════════════════════════════════════════════════════════════════════

def post_to_x(client: tweepy.Client, tweet_text: str) -> Optional[str]:
    """X へ投稿し、成功した場合はツイートIDを返す"""
    try:
        response  = client.create_tweet(text=tweet_text)
        tweet_id  = str(response.data["id"])
        print(f"\n🚀 投稿成功！")
        print(f"   ツイートID : {tweet_id}")
        print(f"   URL        : https://x.com/i/web/status/{tweet_id}")
        return tweet_id
    except tweepy.errors.Forbidden as e:
        print(f"\n❌ 投稿エラー（権限不足）")
        print(f"   X Developer Portal でアプリに「Read and Write」権限を付与してください。")
        print(f"   詳細: {e}")
        return None
    except tweepy.errors.TweepyException as e:
        print(f"\n❌ 投稿エラー: {e}")
        return None
    except Exception as e:
        print(f"\n❌ 予期しないエラー: {e}")
        return None


# ════════════════════════════════════════════════════════════════════════
# PHASE 13: メイン実行フロー
# ════════════════════════════════════════════════════════════════════════

def main() -> None:

    # ── バナー ────────────────────────────────────────────────────────
    print(f"\n{DIVIDER}")
    print("🚀  X Growth Master System  —  起動中")
    print(f"    バージョン: 1.0.0  |  モデル: {AI_MODEL}")
    print(DIVIDER)

    # ── 初期設定 ──────────────────────────────────────────────────────
    setup_env()
    init_history()

    genre         = os.getenv("TARGET_GENRE", "Xの成長戦略・SNSマーケティング")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")

    if not anthropic_key:
        print("❌ ANTHROPIC_API_KEY が設定されていません。.env を確認してください。")
        sys.exit(1)

    print(f"\n📌 ターゲットジャンル : {genre}")
    print(f"📁 作業ディレクトリ  : {BASE_DIR}\n")

    # ── クライアント初期化 ────────────────────────────────────────────
    try:
        ai       = anthropic.Anthropic(api_key=anthropic_key)
        x_client = init_x_client()
        print("✅ Anthropic AI / X API 接続完了\n")
    except ValueError as e:
        print(f"❌ 設定エラー: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ クライアント初期化エラー: {e}")
        sys.exit(1)

    # ── 前回の投稿を分析（Analyst_Agent）────────────────────────────
    last_tweet = load_last_tweet()

    if last_tweet:
        print(THIN_DIVIDER)
        print(f"📂 前回の投稿を検出")
        print(f"   投稿日時   : {last_tweet.get('posted_at', '不明')}")
        print(f"   ツイートID : {last_tweet['tweet_id']}")
        preview = last_tweet['text'][:45].replace('\n', ' ')
        print(f"   テキスト   : {preview}…")
        print(THIN_DIVIDER)

        print("\n⏳ エンゲージメント指標を取得中…")
        metrics = fetch_tweet_metrics(x_client, last_tweet["tweet_id"])

        if metrics["error"]:
            print(f"   ⚠️  一部メトリクス取得に失敗: {metrics['error']}")
            print("   取得できたデータのみで分析を進めます。\n")

        print(f"   👁  インプレッション : {metrics['impressions'] or '取得不可'}")
        print(f"   ❤️  いいね           : {metrics['likes']       or '取得不可'}")
        print(f"   🔁 リポスト         : {metrics['retweets']    or '取得不可'}")
        print(f"   💬 リプライ         : {metrics['replies']     or '取得不可'}")

        history = analyst_agent(ai, last_tweet, metrics, genre)
    else:
        print("📌 前回の投稿記録が見つかりません（初回または記録なし）。")
        print("   学習ログの基本Tips をもとに投稿案を生成します。\n")
        history = load_history()

    # ── マルチエージェント生成ループ ─────────────────────────────────
    print(f"\n{DIVIDER}")
    print("🤖  マルチエージェント投稿生成システム  起動")
    print(f"    合格ライン: {PASS_SCORE}/20点  |  最大リトライ: {MAX_RETRY}回")
    print(DIVIDER)

    try:
        result = editor_loop(ai, genre, history)
    except RuntimeError as e:
        print(f"\n❌ 投稿生成中にエラーが発生しました: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 予期しないエラー: {e}")
        sys.exit(1)

    # ── 結果表示 ──────────────────────────────────────────────────────
    display_result(result)

    # ── 人間の承認ゲート ──────────────────────────────────────────────
    print(f"\n{'─'*62}")
    try:
        answer = input("📮 この投稿を X に送信しますか？ (Y/N、EnterでY) : ").strip().upper()
    except KeyboardInterrupt:
        print("\n\n🛑 キャンセルされました。投稿は行いません。")
        sys.exit(0)

    if answer in ("Y", ""):
        print("\n⏳ X へ投稿中…")
        tweet_id = post_to_x(x_client, result["tweet_text"])
        if tweet_id:
            save_last_tweet(tweet_id, result["tweet_text"])
            print(f"\n💾 ツイートIDを保存しました: {LAST_TWEET_FILE.name}")
            print("   次回起動時に今回の投稿を自動分析します。")
        else:
            print("\n⚠️  投稿に失敗しました。API設定を確認してください。")
    else:
        print("\n🛑 投稿をキャンセルしました。")

    # ── 終了 ──────────────────────────────────────────────────────────
    print(f"\n{DIVIDER}")
    print("✨  X Growth Master — 正常終了")
    print(DIVIDER + "\n")


# ════════════════════════════════════════════════════════════════════════
# エントリーポイント
# ════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()
