#!/usr/bin/env python3
"""買取一丁目候補表から、カメラ分野の初回追加候補を小さく絞る。"""

import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT = BASE_DIR / "reports" / "ichome_product_candidates.csv"
OUT_CSV = BASE_DIR / "reports" / "ichome_camera_recommendations.csv"
OUT_MD = BASE_DIR / "reports" / "ichome_camera_recommendations.md"
OUT_SHORTLIST_CSV = BASE_DIR / "reports" / "ichome_camera_shortlist.csv"

CAMERA_CATEGORY = "カメラ"

PREMIUM_COMPACT = [
    "X100", "GR III", "GR IV", "PowerShot G7", "PowerShot G5",
    "PowerShot G9", "PowerShot V1", "SX740", "IXY 650",
    "RX100", "RX1", "TZ99",
]
POPULAR_BODY = [
    "Z50II", "Z5II", "Z6III", "X-T5", "X-T50", "X-T30", "X-E5", "X-M5",
    "EOS R6", "EOS R7", "EOS R8", "α7", "ILCE-7", "OM-1", "OM-3",
]
POPULAR_LENS = [
    "TAMRON", "Sigma", "NIKKOR Z", "RF24-", "RF70-", "RF100-",
    "XF16-", "XF18-", "FE 16-", "FE 24-", "FE 28-", "FE 70-",
]
LOW_PRIORITY = ["instax", "チェキ"]
LIMITED_WORDS = ["限定", "Anniversary", "リミテッド", "特別モデル"]
ULTRA_TELE_WORDS = [
    "600mm", "800mm", "500mm", "400mm", "300mm f/2.8",
    "100-300mm F2.8",
]

SHORTLIST_TERMS = [
    ("最優先", "X100V", "X100VIが既存登録済みで、同系列の高需要コンデジ"),
    ("最優先", "GR IV HDF", "GR IV Black/Monochromeが既存登録済みで、同系列の高需要コンデジ"),
    ("最優先", "GR IIIx HDF", "GR IIIx既存登録済みで、派生モデルとして見やすい"),
    ("最優先", "GR III HDF", "GR III既存登録済みで、派生モデルとして見やすい"),
    ("最優先", "GR III Street Edition", "GR III既存登録済みで、限定寄りだが需要が読みやすい"),
    ("最優先", "RX100M7", "高級コンデジで単価があり、型番が安定している"),
    ("最優先", "RX100M6", "高級コンデジで単価があり、型番が安定している"),
    ("最優先", "RX100M5A", "高級コンデジで単価があり、型番が安定している"),
    ("優先", "PowerShot G5 X Mark II", "PowerShot/G7X系の既存商品に近い高級コンデジ"),
    ("優先", "PowerShot V10 [ホワイト]", "V10ブラックキット既存。色違い単体として確認しやすい"),
    ("優先", "PowerShot V10 [シルバー]", "V10ブラックキット既存。色違い単体として確認しやすい"),
    ("優先", "CANON PowerShot V10 [ブラック]", "V10ブラックキット既存。単体版として確認しやすい"),
    ("次点", "FUJIFILM X-E5 ボディ", "富士フイルム小型ボディ。候補は色違いがあるため整理してから追加"),
    ("次点", "FUJIFILM X-M5 ボディ", "富士フイルム小型ボディ。候補は色違いがあるため整理してから追加"),
    ("次点", "Nikon Z5II ボディ", "Nikon Z系の既存商品に近いが、キット違いが多く整理が必要"),
    ("次点", "Nikon Z6III ボディ", "Nikon Z系の既存商品に近いが高単価で確認が必要"),
]


def yen_to_int(value: str) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def has_any(text: str, words: list[str]) -> bool:
    lower = text.lower()
    return any(word.lower() in lower for word in words)


def family(title: str) -> str:
    if has_any(title, PREMIUM_COMPACT):
        return "高級コンデジ"
    if has_any(title, POPULAR_BODY):
        return "人気ボディ"
    if has_any(title, POPULAR_LENS):
        return "主要レンズ"
    if has_any(title, LOW_PRIORITY):
        return "チェキ系"
    return "その他カメラ"


def score_row(row: dict) -> tuple[int, str, list[str]]:
    title = row["ichome_title"]
    price = yen_to_int(row["price"])
    fam = family(title)
    score = 0
    reasons: list[str] = []

    if row.get("jan"):
        score += 20
        reasons.append("JANあり")
    if price >= 80_000:
        score += 20
        reasons.append("高単価")
    if price >= 150_000:
        score += 10
        reasons.append("特に高単価")

    if fam == "高級コンデジ":
        score += 40
        reasons.append("高級コンデジ系")
    elif fam == "人気ボディ":
        score += 25
        reasons.append("人気ボディ系")
    elif fam == "主要レンズ":
        score += 15
        reasons.append("既存カメラ群に近いレンズ系")
    elif fam == "チェキ系":
        score -= 20
        reasons.append("チェキ系は既存商品が多い")

    if has_any(title, LIMITED_WORDS):
        score -= 10
        reasons.append("限定・特別モデルで安定性注意")
    if price >= 500_000:
        score -= 25
        reasons.append("超高額で初回追加向きではない")
    if has_any(title, ULTRA_TELE_WORDS):
        score -= 15
        reasons.append("超望遠・専門性が高い")
    if price < 40_000:
        score -= 20
        reasons.append("単価が低め")

    return score, fam, reasons


def rank(score: int, fam: str) -> str:
    if score >= 75 and fam == "高級コンデジ":
        return "S"
    if score >= 65:
        return "A"
    if score >= 50:
        return "B"
    return "保留"


def main() -> None:
    with INPUT.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    camera_rows = [
        row for row in rows
        if row["category"] == CAMERA_CATEGORY and row["status"] == "new_candidate"
    ]

    recommendations = []
    for row in camera_rows:
        score, fam, reasons = score_row(row)
        rec = {
            "rank": rank(score, fam),
            "score": str(score),
            "family": fam,
            "priority": row["priority"],
            "ichome_title": row["ichome_title"],
            "jan": row["jan"],
            "price": row["price"],
            "url": row["url"],
            "reason": "、".join(reasons),
        }
        recommendations.append(rec)

    recommendations.sort(
        key=lambda r: (
            {"S": 3, "A": 2, "B": 1, "保留": 0}[r["rank"]],
            int(r["score"]),
            yen_to_int(r["price"]),
        ),
        reverse=True,
    )

    shortlist = []
    seen_titles = set()
    for bucket, term, note in SHORTLIST_TERMS:
        matches = [
            row for row in recommendations
            if term.lower() in row["ichome_title"].lower()
            and row["ichome_title"] not in seen_titles
        ]
        # 色違いは最大2件まで。ボディ/キット違いは短表では増やしすぎない。
        for row in matches[:2]:
            row = dict(row)
            row["shortlist_rank"] = bucket
            row["shortlist_note"] = note
            shortlist.append(row)
            seen_titles.add(row["ichome_title"])

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "rank", "score", "family", "priority", "ichome_title",
        "jan", "price", "url", "reason",
    ]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(recommendations)

    shortlist_headers = ["shortlist_rank", *headers, "shortlist_note"]
    with OUT_SHORTLIST_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=shortlist_headers)
        writer.writeheader()
        writer.writerows(shortlist)

    counts = {key: sum(1 for r in recommendations if r["rank"] == key) for key in ["S", "A", "B", "保留"]}
    family_counts: dict[str, int] = {}
    for row in recommendations:
        if row["rank"] in {"S", "A", "B"}:
            family_counts[row["family"]] = family_counts.get(row["family"], 0) + 1

    lines = [
        "# 買取一丁目 カメラ追加候補 推薦表",
        "",
        "買取一丁目の商品候補から、せどりナビへ初回追加しやすいカメラ系だけを絞った表。",
        "まずは追加ではなく、候補確認用。",
        "",
        "## 集計",
        "",
        f"- カメラ未登録候補: {len(camera_rows)}件",
        f"- S: {counts['S']}件",
        f"- A: {counts['A']}件",
        f"- B: {counts['B']}件",
        f"- 保留: {counts['保留']}件",
        "",
        "## 判定方針",
        "",
        "- S: 高級コンデジ中心。品薄・人気・型番安定で初回追加候補にしやすい。",
        "- A: 人気ボディまたは主要レンズ。高単価だが対象が広いので確認してから追加。",
        "- B: 追加余地はあるが、専門性・価格帯・既存商品との重複を見て判断。",
        "- 保留: 低単価、チェキ系、超高額・超望遠、または初回追加には重いもの。",
        "",
        "## 初回おすすめ短表",
        "",
        "まず人間が確認するならこの順。ここから実際に追加する商品だけを選ぶ。",
        "",
        "| 優先 | rank | price | jan | title | メモ |",
        "|---|---|---:|---|---|---|",
    ]
    for row in shortlist:
        safe_title = row["ichome_title"].replace("|", "｜")
        safe_note = row["shortlist_note"].replace("|", "｜")
        lines.append(
            f"| {row['shortlist_rank']} | {row['rank']} | {row['price']} | "
            f"{row['jan']} | {safe_title} | {safe_note} |"
        )
    lines.extend([
        "",
        "## ファミリー別件数（S/A/B）",
        "",
    ])
    for fam, count in sorted(family_counts.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"- {fam}: {count}件")

    def append_table(title: str, rows_for_rank: list[dict], limit: int) -> None:
        lines.extend(["", f"## {title}", "", "| rank | score | family | price | jan | title | reason |", "|---|---:|---|---:|---|---|---|"])
        for row in rows_for_rank[:limit]:
            safe_title = row["ichome_title"].replace("|", "｜")
            safe_reason = row["reason"].replace("|", "｜")
            lines.append(
                f"| {row['rank']} | {row['score']} | {row['family']} | {row['price']} | "
                f"{row['jan']} | {safe_title} | {safe_reason} |"
            )

    append_table("S候補", [r for r in recommendations if r["rank"] == "S"], 30)
    append_table("A候補 上位", [r for r in recommendations if r["rank"] == "A"], 40)
    append_table("B候補 上位", [r for r in recommendations if r["rank"] == "B"], 40)

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT_CSV}")
    print(f"wrote {OUT_SHORTLIST_CSV}")
    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
