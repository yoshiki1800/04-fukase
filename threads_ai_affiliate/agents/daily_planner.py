"""
半自動投稿プランナー
毎日の使い方：
  前日夜に「明日のネタ5つ」を入力 → 投稿文を自動生成 → 確認してキューに追加

使い方：
  python daily_planner.py
  → ネタを対話形式で5つ入力
  → 各ネタの投稿文が生成される
  → 確認後 y を入力でキューに保存

  または直接JSONで渡す：
  python daily_planner.py --topics '["サウナ後の肌ケア","AGA薬飲み始めた","腸活アプリ3ヶ月"]'
"""
import os
import sys
import json
import argparse
import anthropic
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.env_loader import load_env

load_env()

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")
DATA_DIR = os.path.join(BASE_DIR, "data")

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generate_post_from_topic(topic: str, profile: dict, patterns: dict, history: list) -> dict:
    """1つのネタから投稿文を1つ生成する"""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    today_str = date.today().strftime("%Y年%m月%d日")

    # 直近で使ったパターンを除外してバリエーションを確保
    recent_pattern_ids = [p.get("pattern_id") for p in history[-10:] if p.get("pattern_id")]
    all_patterns = patterns["patterns"]
    available = [p for p in all_patterns if p["id"] not in recent_pattern_ids]
    if not available:
        available = all_patterns

    # パターン情報をプロンプトに渡す
    patterns_summary = "\n".join([
        f"- {p['id']}：{p['name']}（{p['description'][:40]}）"
        for p in available[:5]
    ])

    prompt = f"""あなたはThreads（SNS）の投稿ライターです。
以下の条件で投稿文を1つ書いてください。

## 今日の日付
{today_str}

## アカウント情報
- アカウント名：{profile["account_name"]}
- コンセプト：{profile["concept"]}
- ペルソナ：{profile["persona"]["background"]}
- ターゲット：{profile["target_audience"]["age"]}・{profile["target_audience"]["gender"]}

## 今日のネタ（塚本さんから提供）
{topic}

## 使えるパターン（以下から選んで使う）
{patterns_summary}

## 投稿の目的と役割（最重要）
このアカウントの投稿は以下の3種類が混在している。今回のネタに最もふさわしい種類を選んで書く。

【種類A：共感・日常ネタ】← 最多。全体の6割
- 目的：フォロワーを増やす・信頼を積む
- 商品・リンク誘導は一切なし
- 「あるある」「ぶっちゃけ話」「笑い話」「日常エピソード」で共感を呼ぶ
- 読者が「わかる笑」「コメントしたい」と思う内容

【種類B：体験談（布石）】← 中程度。全体の3割
- 目的：後日の商品紹介への自然な流れを作る
- 商品名は「さらっと1回触れる」程度でOK。リンクは貼らない
- 「試してみた」「使い始めた」程度の報告で終わる。売り込まない

【種類C：商品紹介（PR）】← 少なめ。全体の1割
- 目的：収益化
- 体験談と商品リンクをセットで提示（PR明記必須）
- 「気になる人だけどうぞ」スタンス。押しつけない

今回は【種類A または 種類B】で書くこと。種類Cは使わない。

## 文体ルール（必ず守ること）
- ですます調ベース。友達に話しかけるような自然な口調
- 1行目が命。読者が思わず止まるフックを必ず入れる
- 「笑」「笑笑」を自然に使ってOK
- 列挙するときは「〜し、〜し、〜し笑」の会話調で。箇条書き（・や①②③）は絶対に使わない
- 自虐・謙虚さを自然に入れる（例：「なかなか痩せないんですけど笑」）
- 難しい専門用語は使わない
- 150〜250文字以内（短くスパッと）
- ハッシュタグは使わない

## 投稿の構成（4ブロック構造）
①【フック＋自己開示】2行。空行なし
②【あるある・詳細】各フレーズ1行改行。前後に空行
③【転換・展開】「でも〜」「最近〜」で動かす。前後に空行
④【締め】問いかけか柔らかい一言。前後に空行

## 必ず守る禁止事項
- 「〇〇に効きます」「確実に」などの効能断言NG（薬機法）
- 女性向けの表現NG
- テストステロン・ED・性欲などの直接表現NG
- まだ体験していないことを体験談として書くことNG
- 「発信していきます」などの使命感NG
- 商品リンク・URL・「詳しくはコメント欄」などのCTA（種類A・Bでは絶対NG）

## 参考文体（この雰囲気で書く）

【種類Aの良い例：日常エピソード型】
この間居酒屋で隣のおばさま軍団に話しかけられました。
20代かと思ったーって言われました。嬉しいですよね笑

YouTuberのNMNサプリを試しに飲み始めて3ヶ月目ですし、効果あったのか？とニヤニヤしました！

継続する価値ありだなって思ってます。

【種類Aの良い例：あるある共感型】
40代男性って、薄毛が気になってても誰にも言えないんですよね。
奥さんにも言いにくいし、友達にネタにされるのも嫌だし。

一人でこっそり調べて
一人でこっそり対策してる人、絶対多いと思う笑

みなさんどうしてます？

## 出力形式（JSONで返してください）
{{
  "content": "投稿本文",
  "hook_line": "1行目の文章",
  "post_category": "共感・日常ネタ or 体験談（布石） or 商品紹介（PR）",
  "pattern_id": "使ったパターンID",
  "pattern_name": "パターン名",
  "affiliate_fit": true or false,
  "affiliate_note": "種類Bの場合のみ：後日どの商品に誘導できるか一言。種類Aはnull",
  "score": {{
    "hook_strength": 点数(0-10),
    "usefulness": 点数(0-10),
    "persona_match": 点数(0-10),
    "average": 平均点
  }}
}}

JSONのみ返してください。"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


def run_daily_planner(topics: list = None):
    profile = load_json(os.path.join(KNOWLEDGE_DIR, "account_profile.json"))
    patterns = load_json(os.path.join(KNOWLEDGE_DIR, "post_patterns.json"))
    history = load_json(os.path.join(DATA_DIR, "post_history.json"))
    queue = load_json(os.path.join(DATA_DIR, "post_queue.json"))

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # ネタの入力
    if topics is None:
        print("\n" + "="*50)
        print("📋 明日の投稿ネタを入力してください（最大5つ）")
        print("例：「サウナ後に使い始めたスキンケアがよかった」")
        print("    「AGA薬、飲み始めて3ヶ月経った感想」")
        print("    「なかなか痩せない話」")
        print("入力が終わったら空エンターで完了")
        print("="*50 + "\n")

        topics = []
        for i in range(5):
            t = input(f"ネタ {i+1}: ").strip()
            if not t:
                break
            topics.append(t)

    if not topics:
        print("ネタが入力されませんでした。終了します。")
        return

    print(f"\n{len(topics)}つのネタで投稿文を生成します...\n")

    approved_posts = []

    for i, topic in enumerate(topics):
        print(f"[{i+1}/{len(topics)}] ネタ：「{topic}」")
        print("生成中...")

        try:
            result = generate_post_from_topic(topic, profile, patterns, history)
        except Exception as e:
            print(f"  エラー: {e}")
            continue

        content = result.get("content", "")
        score = result.get("score", {}).get("average", 0)
        affiliate_fit = result.get("affiliate_fit", False)
        affiliate_note = result.get("affiliate_note", "")

        print(f"\n{'='*40}")
        print(f"📝 生成された投稿文（スコア: {score:.1f}点）")
        if affiliate_fit:
            print(f"💰 アフィリ向き: {affiliate_note}")
        print(f"{'='*40}")
        print(content)
        print(f"{'='*40}\n")

        ans = input("この投稿文をキューに追加しますか？ [y/n/e(編集)]: ").strip().lower()

        if ans == "e":
            print("編集内容を入力してください（空エンターで元の文を使用）：")
            edited = input("> ").strip()
            if edited:
                content = edited
            ans = "y"

        if ans == "y":
            post = {
                "id": f"post_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}",
                "content": content,
                "hook_line": result.get("hook_line", ""),
                "pattern_id": result.get("pattern_id", ""),
                "pattern_name": result.get("pattern_name", ""),
                "theme": topic,
                "main_theme": "手動入力",
                "affiliate_fit": affiliate_fit,
                "affiliate_note": affiliate_note,
                "score": result.get("score"),
                "status": "queued",
                "created_at": datetime.now().isoformat(),
                "source": "manual_planner"
            }
            approved_posts.append(post)
            print(f"  ✅ キューに追加しました\n")
        else:
            print(f"  ⏭ スキップしました\n")

    if approved_posts:
        queue.extend(approved_posts)
        save_json(os.path.join(DATA_DIR, "post_queue.json"), queue)
        print(f"\n🎉 {len(approved_posts)}件の投稿をキューに追加しました！")
        print(f"現在のキュー合計: {len(queue)}件")
        print(f"\n次の投稿は poster.py を実行（または自動スケジューラーが処理します）")
    else:
        print("\nキューへの追加はありませんでした。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="半自動投稿プランナー")
    parser.add_argument(
        "--topics",
        type=str,
        default=None,
        help='ネタをJSON配列で渡す例: \'["サウナ体験","AGA対策3ヶ月目"]\''
    )
    args = parser.parse_args()

    topics = None
    if args.topics:
        topics = json.loads(args.topics)

    run_daily_planner(topics=topics)
