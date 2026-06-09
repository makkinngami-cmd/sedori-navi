#!/usr/bin/env python3
"""買取一丁目候補表から、ポケカ/ワンピの追加候補を小さく絞る。"""

import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT = BASE_DIR / "reports" / "ichome_product_candidates.csv"
OUT_CSV = BASE_DIR / "reports" / "ichome_card_recommendations.csv"
OUT_MD = BASE_DIR / "reports" / "ichome_card_recommendations.md"
OUT_SHORTLIST_CSV = BASE_DIR / "reports" / "ichome_card_shortlist.csv"

CARD_CATEGORIES = {"ポケカ", "ワンピ"}

BOX_WORDS = ["BOX", "box"]
SPECIAL_WORDS = ["スペシャルBOX", "デラックス BOX"]
LOW_PRIORITY_WORDS = ["スタートデッキ", "デッキ"]


def yen_to_int(value: str) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def has_any(text: str, words: list[str]) -> bool:
    return any(word.lower() in text.lower() for word in words)


def score_row(row: dict) -> tuple[int, list[str]]:
    title = row["ichome_title"]
    price = yen_to_int(row["price"])
    score = 0
    reasons: list[str] = []

    if row.get("jan"):
        score += 30
        reasons.append("JANあり")
    if has_any(title, BOX_WORDS):
        score += 25
        reasons.append("BOX系")
    if price >= 15_000:
        score += 25
        reasons.append("単価あり")
    elif price >= 8_000:
        score += 15
        reasons.append("中単価")
    else:
        score -= 20
        reasons.append("単価低め")
    if has_any(title, SPECIAL_WORDS):
        score += 10
        reasons.append("限定・人気BOX系")
    if has_any(title, LOW_PRIORITY_WORDS):
        score -= 20
        reasons.append("デッキ系は初回優先度低め")

    return score, reasons


def rank(score: int) -> str:
    if score >= 80:
        return "S"
    if score >= 60:
        return "A"
    if score >= 40:
        return "B"
    return "保留"


def recommendation(row: dict) -> tuple[str, str]:
    title = row["ichome_title"]
    category = row["category"]
    price = yen_to_int(row["price"])

    if "スタートデッキ" in title:
        return "保留", "低単価のデッキ系。初回追加ではなく後回し。"
    if category == "ポケカ" and "スペシャルBOX" in title:
        return "追加候補", "ポケセン限定系。市場価格基準で入れるなら候補。"
    if category == "ポケカ" and "デラックス BOX" in title:
        return "追加候補", "BOX系でJANあり。市場価格基準で扱いやすい。"
    if category == "ポケカ" and price >= 10_000:
        return "追加候補", "BOX系で単価あり。市場価格基準で候補。"
    if category == "ワンピ" and price >= 15_000:
        return "追加候補", "未登録BOXで単価あり。市場価格基準で候補。"
    return "要確認", "単価や商品形態を確認してから判断。"


def main() -> None:
    with INPUT.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    card_rows = [
        row for row in rows
        if row["category"] in CARD_CATEGORIES and row["status"] == "new_candidate"
    ]

    recommendations = []
    for row in card_rows:
        score, reasons = score_row(row)
        decision, note = recommendation(row)
        recommendations.append({
            "decision": decision,
            "rank": rank(score),
            "score": str(score),
            "category": row["category"],
            "priority": row["priority"],
            "ichome_title": row["ichome_title"],
            "jan": row["jan"],
            "price": row["price"],
            "url": row["url"],
            "price_type": "market",
            "reason": "、".join(reasons),
            "note": note,
        })

    order = {"追加候補": 3, "要確認": 2, "保留": 1}
    rank_order = {"S": 4, "A": 3, "B": 2, "保留": 1}
    recommendations.sort(
        key=lambda r: (
            order[r["decision"]],
            rank_order[r["rank"]],
            yen_to_int(r["price"]),
        ),
        reverse=True,
    )

    shortlist = [row for row in recommendations if row["decision"] == "追加候補"]

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "decision", "rank", "score", "category", "priority", "ichome_title",
        "jan", "price", "url", "price_type", "reason", "note",
    ]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(recommendations)

    with OUT_SHORTLIST_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(shortlist)

    counts = {key: sum(1 for r in recommendations if r["decision"] == key) for key in ["追加候補", "要確認", "保留"]}
    category_counts = {
        category: sum(1 for r in recommendations if r["category"] == category)
        for category in sorted(CARD_CATEGORIES)
    }

    lines = [
        "# 買取一丁目 ポケカ/ワンピ追加候補 推薦表",
        "",
        "買取一丁目の商品候補から、カード系の未登録候補を小さく確認するための表。",
        "カード系は定価/MSRPではなく、市場価格基準 `price_type=market` で扱う前提。",
        "",
        "## 集計",
        "",
        f"- カード系未登録候補: {len(recommendations)}件",
        f"- ポケカ: {category_counts.get('ポケカ', 0)}件",
        f"- ワンピ: {category_counts.get('ワンピ', 0)}件",
        f"- 追加候補: {counts['追加候補']}件",
        f"- 要確認: {counts['要確認']}件",
        f"- 保留: {counts['保留']}件",
        "",
        "## 判定方針",
        "",
        "- JANあり、BOX系、単価15,000円以上を優先。",
        "- スペシャルBOX/デラックスBOXは市場価格基準の追加候補にする。",
        "- 低単価デッキ系は初回追加から外す。",
        "- MSRPは無理に登録しない。入れる場合は買取一丁目候補価格を初期の市場基準として使う。",
        "",
        "## 初回追加候補",
        "",
        "| decision | rank | category | price | jan | title | note |",
        "|---|---|---|---:|---|---|---|",
    ]
    for row in shortlist:
        safe_title = row["ichome_title"].replace("|", "｜")
        safe_note = row["note"].replace("|", "｜")
        lines.append(
            f"| {row['decision']} | {row['rank']} | {row['category']} | {row['price']} | "
            f"{row['jan']} | {safe_title} | {safe_note} |"
        )

    lines.extend([
        "",
        "## 全候補",
        "",
        "| decision | rank | score | category | price | jan | title | reason |",
        "|---|---|---:|---|---:|---|---|---|",
    ])
    for row in recommendations:
        safe_title = row["ichome_title"].replace("|", "｜")
        safe_reason = row["reason"].replace("|", "｜")
        lines.append(
            f"| {row['decision']} | {row['rank']} | {row['score']} | {row['category']} | "
            f"{row['price']} | {row['jan']} | {safe_title} | {safe_reason} |"
        )

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT_CSV}")
    print(f"wrote {OUT_SHORTLIST_CSV}")
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
