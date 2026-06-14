"""
エージェント③：ライター
リサーチネタ＋アナリストのフィードバックをもとに投稿文を生成し、品質スコア7.0以上のみキューへ追加する
"""
import os
import sys
import json
import random
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

def similarity_check(new_content, history, threshold=0.85):
    """簡易的な類似度チェック（共通単語の割合）"""
    new_words = set(new_content.replace("\n", " ").split())
    for old_post in history[-100:]:
        old_words = set(old_post.get("content", "").replace("\n", " ").split())
        if not old_words:
            continue
        intersection = len(new_words & old_words)
        union = len(new_words | old_words)
        if union > 0 and intersection / union > threshold:
            return True
    return False

def get_recent_patterns(history, n=3):
    """直近n件で使ったパターンIDを返す"""
    return [p.get("pattern_id") for p in history[-n:] if p.get("pattern_id")]

def write_posts(batch_size=5, dry_run=False):
    profile = load_json(os.path.join(KNOWLEDGE_DIR, "account_profile.json"))
    patterns = load_json(os.path.join(KNOWLEDGE_DIR, "post_patterns.json"))
    research_pool = load_json(os.path.join(DATA_DIR, "research_pool.json"))
    history = load_json(os.path.join(DATA_DIR, "post_history.json"))
    queue = load_json(os.path.join(DATA_DIR, "post_queue.json"))

    # フィードバック読み込み（なければデフォルト）
    feedback_path = os.path.join(DATA_DIR, "feedback.json")
    feedback = load_json(feedback_path) if os.path.exists(feedback_path) else {}

    # 未使用のネタを取得
    unused_items = [r for r in research_pool if not r.get("used")]
    if len(unused_items) < batch_size:
        print(f"[ライター] 未使用ネタが不足({len(unused_items)}件)。リサーチャーを先に実行してください。")
        batch_size = len(unused_items)
    if batch_size == 0:
        print("[ライター] ネタがありません。終了します。")
        return []

    selected_items = random.sample(unused_items, batch_size)
    recent_patterns = get_recent_patterns(history)
    recommended = feedback.get("recommended_patterns", [])
    avoid = feedback.get("avoid_patterns", [])

    # 使用可能なパターンを選定
    available_patterns = [
        p for p in patterns["patterns"]
        if p["id"] not in recent_patterns and p["id"] not in avoid
    ]
    if not available_patterns:
        available_patterns = patterns["patterns"]

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    generated = []
    for item in selected_items:
        # パターン選択（推奨優先、なければランダム）
        preferred = [p for p in available_patterns if p["id"] in recommended]
        pattern = random.choice(preferred) if preferred else random.choice(available_patterns)

        for attempt in range(3):  # 最大3回リトライ
            from datetime import date
            today_str = date.today().strftime("%Y年%m月%d日")
            prompt = f"""あなたはThreads（SNS）の投稿ライターです。
以下の条件で投稿文を1つ書いてください。

## 今日の日付
{today_str}（年号・年代を使う場合は必ずこの日付を基準にすること）

## アカウント情報
- コンセプト: {profile["concept"]}
- ターゲット: {profile["target_audience"]["age"]}・{profile["target_audience"]["occupation"]}

## 投稿パターン
- パターン名: {pattern["name"]}
- 説明: {pattern["description"]}
- 構造: {" → ".join(pattern["structure"])}

## 使用するネタ
- テーマ: {item["theme"]}
- タイトル: {item["title"]}
- キーポイント: {item["key_points"]}
- フックアイデア: {item["hook_idea"]}

## 文体ルール（必ず守ること）
- ですます調ベース。友達に話しかけるような自然な口調
- 1行目が命。読者が思わず止まるフックを必ず入れる
- 「笑」「笑笑」を自然に使ってOK
- 列挙するときは「〜し、〜し、〜し笑」の会話調で。箇条書き（・や①②③）は絶対に使わない
- 自虐・謙虚さを自然に入れる（例：「まだ全然できてないですけど笑」）
- 難しい専門用語は使わない
- **150〜250文字以内**（短くスパッと伝えること。長くなりすぎない）
- ハッシュタグは使わない

## 投稿の構成（4ブロック構造・必ずこの順番で書く）
①【フック＋自己開示】2行。フック1行→自己開示1行。ブロック間に空行なし
②【あるある・理由・詳細】各フレーズを1行ずつ改行して並べる。ブロック前後に空行
③【転換・展開】各フレーズを1行ずつ改行。「でも〜」「最近〜」で話を動かす。前後に空行
④【締め】各フレーズを1行ずつ改行。柔らかく・短く。前後に空行

## 改行ルール（最重要・必ず守ること）
- 「〜し」「〜ので」「〜も」「〜けど」などの接続フレーズで改行する
- 1フレーズ＝1行。長い文は途中で区切って改行する
- ブロックが変わるときだけ空行（1行）を入れる
- ①フック＋自己開示のブロックだけは空行なし（2行続けて書く）

## 絶対に使ってはいけない表現（厳守）
- 「参考になれば幸いです」「参考になれば」→ 禁止
- 「〜を発信していきます」「〜していきます」→ 禁止
- 「届いてほしいです」「〜な人に向けて」→ 禁止
- 「本当に来てますよ」などの上から目線の断定 → 禁止
- 起承転結が明確すぎる綺麗な構成 → 禁止（人が話しているように書く）

## このアカウントのフェーズ（最重要・必ず守ること）
- 立場：40代・大阪のメンズサロン経営者。自腹で男の体メンテを全部試している人
- 日常：ジム週3〜4回・朝瞑想・腸活アプリ・サプリ複数・AGA対策・サウナ・マッサージ・がん検査
- 経営：メンズ脱毛・マッサージサロンを複数展開。施術現場の本音も語れる
- 悩み：なかなか痩せない・AGA気になる・忙しくて疲れが取れないなど等身大の悩みあり
- 収益：アフィリエイト（楽天・ASP）・院紹介で収益化を目指している

## 絶対にやってはいけないこと（フェーズ・ルール違反）
❌ 女性を主語にした内容・女性向けの表現
❌「〇〇に効きます」「〇〇が治ります」などの効能断言（薬機法・景表法NG）
❌ テストステロン・ED・性欲などの直接的な性的表現
❌ 専門家・医師のような上から目線の断言口調
❌ まだ体験していないことを体験談のように書く
❌「確実に」「絶対に」「必ず」などの誇大表現

## 体験談・数字について（最重要）
- 自分が実際に試したことのみ体験談として書く
- 「〜してみた」「自分の場合は〜だった笑」など実験中・体験中のトーンで書く
- 「まだ途中だけど」「効いてるかどうかわからんけど笑」などの正直な表現を使う
- 他の人の情報を紹介するときは「〇〇らしいです」「〇〇って聞きました」と伝聞形にする
- サロン経営者の視点から語るときは「施術してて思うんですが」「お客さんで多いのが」と枕詞を入れる

## マネタイズの布石ルール（必ず意識すること）
このアカウントはアフィリエイト（楽天・ASP・院紹介）への自然な誘導が目的の一つ。
投稿単体で完結させず、「詳しく知りたい」「使ってみたい」と思わせる余白を残すこと。

【布石の作り方3パターン】
①「2投稿ワンセット」型：体験談を語った直後の投稿でアフィリ商品を紹介
　→ 1投稿目：「最近サウナ後に使い始めたスキンケアがよかった」
　→ 2投稿目：「使ってるのはコレ↓（PR）」＋楽天リンク

②「興味喚起」型：体験談・感想を話して「商品名だけさらっと出す」
　→「使ってるのは〇〇っていう商品で、気になる人は調べてみてください笑」

③「問題提起」型：悩みや気づきを投稿し、解決策は次の投稿・コメント欄で
　→「AGAが気になって色々試したんですが、続きはコメント欄に書きます」

【重要】押しつけにならないこと
- CTA（誘導）は1投稿に1回まで・柔らかく
- 「買ってください」「見てください」は絶対に使わない
- 「気になる人だけどうぞ」スタンスで自然に誘導する

## 参考にすべき文体（この構造をベースにすること）

【正解の型①：共感型（バズ狙い）】
40代男性って、薄毛が気になってても誰にも言えないんですよね。
奥さんにも言いにくいし、友達にネタにされるのも嫌だし。
← ①フック＋自己開示：2行・空行なし

一人でこっそり調べて
一人でこっそり対策してる人、絶対多いと思う笑
← ②あるある：「〜し」で各フレーズを改行。ブロック前後に空行

自分もそのひとりなんですが
最近ちょっとずつ変わってきたのでそのうち話します。
← ③転換：「でも」「最近」で展開。前後に空行

みなさんどうしてます？
← ④締め：問いかけで締める。前後に空行

→ ポイント：1フレーズ1行・ブロック間のみ空行・箇条書きなし・自虐あり・使命感なし

【正解の型②：体験談型（アフィリ向き）】
サウナ後に使い始めてから、肌の調子が明らかに変わったスキンケアがあって。
← ①フック：体験の入口を一言で

成分とか正直よくわからないんですが
使い続けてたら同僚に「なんか肌きれいじゃないですか」って言われました笑
← ②体験詳細：「〜が」「〜けど」で改行。前後に空行

40代でもケアすれば変わるんだなと実感してます。
← ③転換・気づき。前後に空行

使ってるのコメント欄に貼っておきます🙏
← ④締め：柔らかいCTA

【悪い例（やってはいけない）】
「このスキンケアを使えば肌が若返ります。40代男性に効果的な成分が入っており、確実に改善します。」
→ NG：効能断言・誇大表現・AIっぽい構成

## アナリストからのフィードバック
{feedback.get("tone_guidance", "初期フェーズ。多様なパターンで試してください")}

## 出力形式（JSONで返してください）
{{
  "content": "投稿本文（200〜400文字）",
  "hook_line": "1行目の文章",
  "post_type": "通常 or コメント誘導 or ツリー",
  "affiliate_fit": true or false（アフィリエイトリンクを置くのに適しているか）,
  "score": {{
    "hook_strength": 点数(0-10),
    "usefulness": 点数(0-10),
    "specificity": 点数(0-10),
    "readability": 点数(0-10),
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

            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                print(f"[ライター] JSONパースエラー（attempt {attempt+1}）")
                continue

            score = result.get("score", {}).get("average", 0)
            content = result.get("content", "")

            if score < 7.0:
                print(f"[ライター] スコア不足({score:.1f})。リトライ {attempt+1}/3")
                continue

            if similarity_check(content, history):
                print(f"[ライター] 類似投稿あり。リトライ {attempt+1}/3")
                continue

            # 合格
            post = {
                "id": f"post_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(generated)}",
                "content": content,
                "hook_line": result.get("hook_line"),
                "post_type": result.get("post_type", "通常"),
                "pattern_id": pattern["id"],
                "pattern_name": pattern["name"],
                "theme": item["theme"],
                "main_theme": item.get("main_theme"),
                "affiliate_fit": result.get("affiliate_fit", False),
                "score": result.get("score"),
                "status": "queued",
                "created_at": datetime.now().isoformat(),
                "research_item_id": item.get("title"),
            }
            generated.append(post)
            print(f"[ライター] ✅ 合格({score:.1f}点): {content[:40]}...")
            break
        else:
            print(f"[ライター] ❌ 棄却: {item['title']}")

    # ネタをusedにマーク
    if not dry_run:
        used_titles = {item["title"] for item in selected_items}
        for r in research_pool:
            if r.get("title") in used_titles:
                r["used"] = True
        save_json(os.path.join(DATA_DIR, "research_pool.json"), research_pool)

        queue.extend(generated)
        save_json(os.path.join(DATA_DIR, "post_queue.json"), queue)

    print(f"[ライター] {len(generated)}/{batch_size}件をキューに追加")
    return generated

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch", type=int, default=5)
    args = parser.parse_args()
    write_posts(batch_size=args.batch, dry_run=args.dry_run)
