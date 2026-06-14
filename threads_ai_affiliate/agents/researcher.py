"""
エージェント①：リサーチャー
YouTube/Web検索からAI副業系のネタを収集してresearch_pool.jsonに保存する
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
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")
DATA_DIR = os.path.join(BASE_DIR, "data")

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_theme_needs(themes, research_pool):
    """テーマツリーを見て、ネタが少ないテーマを特定する"""
    theme_counts = {}
    for item in research_pool:
        theme = item.get("theme", "")
        theme_counts[theme] = theme_counts.get(theme, 0) + 1

    needs = []
    for main_theme, data in themes["theme_tree"].items():
        for sub in data["sub_themes"]:
            count = theme_counts.get(sub, 0)
            needs.append({"theme": sub, "main_theme": main_theme, "count": count})

    needs.sort(key=lambda x: x["count"])
    return needs[:3]  # ネタが少ない上位3テーマ

def research(dry_run=False):
    themes = load_json(os.path.join(KNOWLEDGE_DIR, "themes.json"))
    profile = load_json(os.path.join(KNOWLEDGE_DIR, "account_profile.json"))
    research_pool = load_json(os.path.join(DATA_DIR, "research_pool.json"))

    needs = get_theme_needs(themes, research_pool)
    print(f"[リサーチャー] ネタ不足テーマ: {[n['theme'] for n in needs]}")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt = f"""あなたはSNSコンテンツのリサーチ専門AIです。
以下のテーマについて、Threadsで伸びそうな投稿ネタを各テーマ2件ずつ考えてください。

## このアカウントについて（最重要・必ず守ること）
- アカウント名：ASU｜40代男のメンテ記録
- ステージ：40代・大阪のサロン経営者。自腹で男の体メンテを全部試している人
- 立場：メンズ脱毛・マッサージサロンを複数経営。現場から語れる本音がある
- 日常のメンテ：ジム週3〜4回・朝瞑想・腸活アプリ・サプリ複数種・AGA対策・サウナ・マッサージ・がん検査など
- 発信スタイル：体験談ベース・本音・「なかなか痩せない」などの自虐・語り口調

## リサーチの禁止事項（絶対に守ること）
❌ 女性向けの内容・女性を主語にしたネタ
❌ 医療的な「効果・効能・治療」断言（景表法・薬機法に抵触する表現）
❌ テストステロン・性欲・EDなどの直接的な性的表現
❌ 専門家・医師・コンサルタントとしての上から目線のネタ
❌ 「確実に痩せる」「絶対に生えてくる」などの誇大表現
❌ 一般論・教科書的な健康情報（体験談ベースで書けないネタ）

## リサーチのルール（必ず守ること）
✅ 「40代男性なら共感できる」体の変化・悩みのネタを優先する
✅ サロン経営者・現場視点からしか語れない本音ネタを積極的に取り上げる
✅ 「自分も試してみた」「サロンで気づいた」などの一次情報ベースのネタにする
✅ フックは「40代男性あるある・誰にも言えない悩み・ぶっちゃけ話」系
✅ 失敗談・後悔・正直な感想も積極的にネタにする
✅ AGA・腸活・サウナ・サプリ・予防医療・清潔感など具体的なジャンル名を入れる
✅ アフィリエイト（楽天・ASP）に繋げやすいネタを意識する

## ターゲット読者
{json.dumps(profile["target_audience"], ensure_ascii=False)}

## ネタを集めるテーマ
{json.dumps([n["theme"] for n in needs], ensure_ascii=False)}

## 出力形式（必ずJSON配列で返してください）
[
  {{
    "theme": "テーマ名",
    "main_theme": "大カテゴリ名",
    "title": "投稿ネタのタイトル（体験談・本音視点で）",
    "key_points": ["ポイント1", "ポイント2", "ポイント3"],
    "hook_idea": "1行目のアイデア（40代男性が思わず止まる共感・驚き・本音の告白）",
    "source_type": "体験談 or サロン現場視点 or 失敗談 or 正直な感想 or 比較"
  }}
]

2026年の最新トレンドを意識しつつ、「40代サロン経営者の自腹メンテ記録」という一貫したトーンで、具体的・正直なネタにしてください。
JSONのみ返してください。説明文は不要です。"""

    print("[リサーチャー] Claude APIでネタ生成中...")
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    new_items = json.loads(raw)
    for item in new_items:
        item["created_at"] = datetime.now().isoformat()
        item["used"] = False

    if dry_run:
        print(f"[リサーチャー] DRY RUN: {len(new_items)}件のネタを生成（保存スキップ）")
        for item in new_items:
            print(f"  - [{item['theme']}] {item['title']}")
        return new_items

    research_pool.extend(new_items)
    save_json(os.path.join(DATA_DIR, "research_pool.json"), research_pool)
    print(f"[リサーチャー] {len(new_items)}件のネタを保存。合計: {len(research_pool)}件")
    return new_items

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    research(dry_run=args.dry_run)
