#!/usr/bin/env python3
"""買取一丁目候補表から、スマホ分野の必要機種だけを小さく絞る。"""

import csv
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT = BASE_DIR / "reports" / "ichome_product_candidates.csv"
OUT_CSV = BASE_DIR / "reports" / "ichome_smartphone_recommendations.csv"
OUT_MD = BASE_DIR / "reports" / "ichome_smartphone_recommendations.md"
OUT_SHORTLIST_CSV = BASE_DIR / "reports" / "ichome_smartphone_shortlist.csv"

SMARTPHONE_CATEGORY = "スマートフォン"


def yen_to_int(value: str) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def parse_iphone(title: str) -> dict:
    match = re.match(
        r"^(iPhone(?: Air|\s+\d+\s+Pro\s+Max|\s+\d+\s+Pro|\s+\d+\s+Plus|\s+\d+\s+mini|\s+\d+))\s+"
        r"(\d+GB|1TB|2TB)\s+(.+)$",
        title,
    )
    if not match:
        return {"family": "その他", "capacity": "", "color": "", "generation": 0, "tier": "other"}

    family, capacity, color = match.groups()
    generation_match = re.search(r"iPhone(?: Air|\s+)(\d+)", family)
    generation = int(generation_match.group(1)) if generation_match else 0

    if "Pro Max" in family:
        tier = "Pro Max"
    elif " Pro" in family:
        tier = "Pro"
    elif "Air" in family:
        tier = "Air"
    elif "Plus" in family:
        tier = "Plus"
    elif "mini" in family:
        tier = "mini"
    else:
        tier = "base"

    return {
        "family": family,
        "capacity": capacity,
        "color": color,
        "generation": generation,
        "tier": tier,
    }


def capacity_score(capacity: str) -> int:
    return {
        "2TB": 18,
        "1TB": 25,
        "512GB": 22,
        "256GB": 18,
        "128GB": 8,
    }.get(capacity, 0)


def score_row(row: dict) -> tuple[int, str, list[str], dict]:
    title = row["ichome_title"]
    price = yen_to_int(row["price"])
    info = parse_iphone(title)
    score = 0
    reasons: list[str] = []

    if row.get("jan"):
        score += 20
        reasons.append("JANあり")

    if info["tier"] == "Pro Max":
        score += 35
        reasons.append("Pro Max")
    elif info["tier"] == "Pro":
        score += 30
        reasons.append("Pro")
    elif info["tier"] == "Air":
        score += 18
        reasons.append("Air")
    elif info["tier"] == "Plus":
        score += 8
        reasons.append("Plus")
    elif info["tier"] == "base":
        score += 5
        reasons.append("通常モデル")

    score += capacity_score(info["capacity"])
    if info["capacity"]:
        reasons.append(info["capacity"])

    if info["generation"] >= 16:
        score += 20
        reasons.append("新しめ")
    elif info["generation"] == 15:
        score += 10
        reasons.append("15世代")
    elif info["generation"] <= 13 and info["generation"] > 0:
        score -= 20
        reasons.append("世代古め")

    if price >= 180_000:
        score += 20
        reasons.append("高単価")
    elif price >= 140_000:
        score += 12
        reasons.append("単価あり")
    elif price < 80_000:
        score -= 15
        reasons.append("単価低め")

    # 2TBは高額だが動きが重くなりやすいので初回では少し慎重にする。
    if info["capacity"] == "2TB":
        score -= 10
        reasons.append("2TBは初回慎重")

    if info["tier"] in {"base", "Plus", "mini"} and info["generation"] <= 14:
        score -= 15
        reasons.append("初回追加の優先度低め")

    if info["tier"] == "other":
        score -= 20
        reasons.append("型番分類外")

    fam = info["family"]
    return score, fam, reasons, info


def rank(score: int, info: dict) -> str:
    if (
        score >= 100
        and info["generation"] == 16
        and info["tier"] in {"Pro Max", "Pro"}
        and info["capacity"] in {"256GB", "512GB", "1TB"}
    ):
        return "S"
    if score >= 85:
        return "A"
    if score >= 65:
        return "B"
    return "保留"


def decision(rank_value: str, info: dict) -> tuple[str, str]:
    if rank_value == "S":
        return "初回追加候補", "iPhone 16 Pro/Pro Maxの256GB以上。色別JANで追加しやすい。"
    if rank_value == "A":
        return "次点候補", "高単価だが、iPhone 16 S候補の後に追加判断。"
    if rank_value == "B":
        return "要確認", "モデル/容量を絞れば追加余地あり。初回は見送り寄り。"
    return "保留", "世代・単価・モデルの優先度から初回追加は見送り。"


def main() -> None:
    with INPUT.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    phone_rows = [
        row for row in rows
        if row["category"] == SMARTPHONE_CATEGORY and row["status"] == "new_candidate"
    ]

    recommendations = []
    for row in phone_rows:
        score, family, reasons, info = score_row(row)
        row_rank = rank(score, info)
        row_decision, note = decision(row_rank, info)
        recommendations.append({
            "decision": row_decision,
            "rank": row_rank,
            "score": str(score),
            "family": family,
            "tier": info["tier"],
            "capacity": info["capacity"],
            "color": info["color"],
            "priority": row["priority"],
            "ichome_title": row["ichome_title"],
            "jan": row["jan"],
            "price": row["price"],
            "url": row["url"],
            "reason": "、".join(reasons),
            "note": note,
        })

    rank_order = {"S": 4, "A": 3, "B": 2, "保留": 1}
    decision_order = {"初回追加候補": 4, "次点候補": 3, "要確認": 2, "保留": 1}
    recommendations.sort(
        key=lambda r: (
            decision_order[r["decision"]],
            rank_order[r["rank"]],
            int(r["score"]),
            yen_to_int(r["price"]),
        ),
        reverse=True,
    )

    shortlist = [row for row in recommendations if row["decision"] == "初回追加候補"]

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "decision", "rank", "score", "family", "tier", "capacity", "color",
        "priority", "ichome_title", "jan", "price", "url", "reason", "note",
    ]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(recommendations)

    with OUT_SHORTLIST_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(shortlist)

    counts = {key: sum(1 for r in recommendations if r["rank"] == key) for key in ["S", "A", "B", "保留"]}
    decision_counts = {
        key: sum(1 for r in recommendations if r["decision"] == key)
        for key in ["初回追加候補", "次点候補", "要確認", "保留"]
    }

    lines = [
        "# 買取一丁目 スマホ追加候補 推薦表",
        "",
        "買取一丁目の商品候補から、スマホを必要機種だけに絞った表。",
        "色違いはJANが別なので残しつつ、モデル/容量で初回追加範囲を小さくする。",
        "",
        "## 集計",
        "",
        f"- スマホ未登録候補: {len(recommendations)}件",
        f"- 初回追加候補: {decision_counts['初回追加候補']}件",
        f"- 次点候補: {decision_counts['次点候補']}件",
        f"- 要確認: {decision_counts['要確認']}件",
        f"- 保留: {decision_counts['保留']}件",
        f"- S: {counts['S']}件",
        f"- A: {counts['A']}件",
        f"- B: {counts['B']}件",
        f"- 保留rank: {counts['保留']}件",
        "",
        "## 判定方針",
        "",
        "- 既存登録済みのiPhone 17 Pro/Pro Maxは触らない。",
        "- 初回追加は iPhone 16 Pro/Pro Max の256GB/512GB/1TBに絞る。",
        "- 128GB、2TB、iPhone 15以前、iPhone Airは次点または要確認に落とす。",
        "- スマホはApple MSRPがあるものはMSRP基準、旧機種や終売品は必要なら市場価格基準で扱う。",
        "",
        "## 初回追加候補",
        "",
        "| decision | rank | family | capacity | price | jan | title | note |",
        "|---|---|---|---|---:|---|---|---|",
    ]
    for row in shortlist:
        safe_title = row["ichome_title"].replace("|", "｜")
        safe_note = row["note"].replace("|", "｜")
        lines.append(
            f"| {row['decision']} | {row['rank']} | {row['family']} | {row['capacity']} | "
            f"{row['price']} | {row['jan']} | {safe_title} | {safe_note} |"
        )

    lines.extend([
        "",
        "## 次点候補 上位",
        "",
        "| decision | rank | score | family | capacity | price | jan | title | reason |",
        "|---|---|---:|---|---|---:|---|---|---|",
    ])
    for row in [r for r in recommendations if r["decision"] == "次点候補"][:40]:
        safe_title = row["ichome_title"].replace("|", "｜")
        safe_reason = row["reason"].replace("|", "｜")
        lines.append(
            f"| {row['decision']} | {row['rank']} | {row['score']} | {row['family']} | "
            f"{row['capacity']} | {row['price']} | {row['jan']} | {safe_title} | {safe_reason} |"
        )

    lines.extend([
        "",
        "## 全候補サマリー",
        "",
        "| decision | rank | score | family | capacity | price | jan | title |",
        "|---|---|---:|---|---|---:|---|---|",
    ])
    for row in recommendations:
        safe_title = row["ichome_title"].replace("|", "｜")
        lines.append(
            f"| {row['decision']} | {row['rank']} | {row['score']} | {row['family']} | "
            f"{row['capacity']} | {row['price']} | {row['jan']} | {safe_title} |"
        )

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT_CSV}")
    print(f"wrote {OUT_SHORTLIST_CSV}")
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
