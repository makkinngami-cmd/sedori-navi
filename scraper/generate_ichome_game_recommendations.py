"""
Generate a focused recommendation report for game-related 買取一丁目 candidates.

Input:
  reports/ichome_product_candidates.csv

Output:
  reports/ichome_game_recommendations.csv
  reports/ichome_game_recommendations.md

This report is a first-pass shortlist. It does not edit product masters.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re


JST = timezone(timedelta(hours=9))
TODAY = datetime.now(JST).strftime('%Y-%m-%d')

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_CSV = BASE_DIR / 'reports' / 'ichome_product_candidates.csv'
OUT_CSV = BASE_DIR / 'reports' / 'ichome_game_recommendations.csv'
OUT_MD = BASE_DIR / 'reports' / 'ichome_game_recommendations.md'

CSV_HEADERS = [
    'recommendation',
    'segment',
    'ichome_title',
    'jan',
    'price',
    'url',
    'reason',
    'next_check',
]


def normalize(value: str) -> str:
    value = value.replace('　', ' ')
    return re.sub(r'\s+', ' ', value).strip().lower()


def classify(row: dict) -> tuple[str, str, str, str]:
    title = row['ichome_title']
    norm = normalize(title)
    price = int(row['price'] or 0)
    jan = row.get('jan', '')

    if not jan:
        return (
            '保留',
            'JANなし',
            'JANがないため、他業者照合や商品追加の前に実物確認が必要。',
            'JANまたは型番の確認',
        )

    if any(term in norm for term in ['rog xbox ally', 'steam deck']):
        return (
            'S',
            '携帯PC/Steam Deck',
            '高単価で既存せどりナビのSteam Deck/Xbox系と近い。型番JANも安定している。',
            'ヤフオク落札実績と他業者取扱有無',
        )

    if 'nintendo switch 2' in norm and 'セット' in title and price >= 20000:
        return (
            'S',
            'Switch2 本体/セット',
            'Switch2系は既存監視の中心に近く、セット品は値動き確認価値が高い。',
            '通常版との差額、他業者JAN一致',
        )

    if title.startswith('【NS2】') and 'edition' in norm:
        return (
            'A',
            'Switch2 Editionソフト',
            'Switch2系で既存監視と近いが、単価は低めなので本体セットより優先度を下げる。',
            '発売日、ヤフオク落札数、通常Switch版との差額',
        )

    if 'playstation5 slim' in norm and any(
        term in norm for term in ['ダブルパック', 'フォートナイト', 'モンスターハンターワイルズ']
    ):
        return (
            'S',
            'PS5 限定/同梱本体',
            'PS5本体派生で単価が高く、既存PS5監視との比較に向く。',
            '通常PS5との差額、ヤフオク落札実績',
        )

    if '30周年' in title and any(term in norm for term in ['playstation5', 'portal', 'edge', 'コントローラー']):
        return (
            'S',
            'PlayStation 限定品',
            '限定品で価格差・値動きが出やすい。既存PS5周辺機器と近い。',
            'ヤフオクでストア除外後の個人落札価格',
        )

    if any(term in norm for term in ['playstation portal', 'ps5 edge', 'pulse explore']):
        return (
            'A',
            'PlayStation 周辺機器',
            '既存のPS5系監視と近く、JAN照合しやすい。',
            '買取一丁目以外の取扱有無',
        )

    if any(term in norm for term in ['xbox series s', 'xbox elite']):
        return (
            'A',
            'Xbox 本体/上位周辺機器',
            'Xbox系は既存カテゴリあり。高単価品は監視候補になる。',
            'ヤフオク落札数と回転率',
        )

    if 'nintendo switch (有機elモデル)' in norm:
        return (
            'A',
            'Switch 限定本体',
            '既存Switch監視と近く、限定カラー/同梱版として比較価値がある。',
            '通常有機ELとの買取差額',
        )

    if any(term in norm for term in ['nintendo switch 2 proコントローラー', 'ps5 ワイヤレスコントローラー']):
        return (
            'B',
            '新作/限定コントローラー',
            'JANは安定するが、色・限定違いが多く増えすぎるため優先範囲を絞りたい。',
            '直近取引予定があるものだけ追加',
        )

    if title.startswith('【NS2】') or title.startswith('【PS5】'):
        return (
            'B',
            '新作ソフト',
            '価格は低めだが新作は値動き確認価値あり。数が増えやすいので厳選向き。',
            '発売日とヤフオク落札数',
        )

    if price >= 30000:
        return (
            'B',
            '高単価ゲーム商品',
            '高単価だが、既存監視との近さは要確認。',
            '他業者取扱有無',
        )

    return (
        '保留',
        '周辺機器/低単価ソフト',
        '候補数が多いため、取引予定や明確な値動きがある場合に追加する。',
        '取引予定の有無',
    )


def load_rows() -> list[dict]:
    with SOURCE_CSV.open(newline='', encoding='utf-8-sig') as file:
        return [
            row
            for row in csv.DictReader(file)
            if row['status'] == 'new_candidate' and row['category'] in {'ゲーム', 'Steam Deck'}
        ]


def recommendation_sort(row: dict) -> tuple[int, int, str]:
    rank = {'S': 0, 'A': 1, 'B': 2, '保留': 3}
    return (rank.get(row['recommendation'], 9), -int(row['price'] or 0), row['ichome_title'])


def build_recommendations(rows: list[dict]) -> list[dict]:
    recommendations = []
    for row in rows:
        recommendation, segment, reason, next_check = classify(row)
        recommendations.append({
            'recommendation': recommendation,
            'segment': segment,
            'ichome_title': row['ichome_title'],
            'jan': row['jan'],
            'price': row['price'],
            'url': row['url'],
            'reason': reason,
            'next_check': next_check,
        })
    return sorted(recommendations, key=recommendation_sort)


def write_csv(rows: list[dict]) -> None:
    with OUT_CSV.open('w', newline='', encoding='utf-8-sig') as file:
        writer = csv.DictWriter(file, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def md_escape(value: str) -> str:
    return value.replace('|', '\\|').replace('\n', ' ')


def write_md(rows: list[dict]) -> None:
    counts = {key: sum(1 for row in rows if row['recommendation'] == key) for key in ['S', 'A', 'B', '保留']}
    segments = {}
    for row in rows:
        if row['recommendation'] in {'S', 'A'}:
            segments[row['segment']] = segments.get(row['segment'], 0) + 1

    lines = [
        '# 買取一丁目 ゲーム分野 追加おすすめ候補',
        '',
        f'更新日: {TODAY}',
        '',
        '## 位置づけ',
        '',
        '- 買取一丁目の商品一覧から、せどりナビ未登録のゲーム系だけを抽出した一次提案。',
        '- 実際に追加する前に、ヤフオク落札実績、他業者取扱有無、取引予定の有無を確認する。',
        '- 商品マスターや価格CSVへの追加は、このレポートだけでは実施しない。',
        '',
        '## サマリー',
        '',
        f'- ゲーム系未登録候補: {len(rows)}',
        f'- S: {counts["S"]}',
        f'- A: {counts["A"]}',
        f'- B: {counts["B"]}',
        f'- 保留: {counts["保留"]}',
        '',
        '## S/A候補の分野別件数',
        '',
    ]

    for segment, count in sorted(segments.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f'- {segment}: {count}')

    lines.extend([
        '',
        '## まず見る候補',
        '',
        'CSV全件: `reports/ichome_game_recommendations.csv`',
        '',
        '| 推薦 | 分野 | 商品名 | JAN | 買取価格 | 理由 | 次に確認すること |',
        '|---|---|---|---|---:|---|---|',
    ])

    for row in [row for row in rows if row['recommendation'] in {'S', 'A'}][:80]:
        lines.append(
            '| '
            + ' | '.join([
                md_escape(row['recommendation']),
                md_escape(row['segment']),
                md_escape(row['ichome_title']),
                md_escape(row['jan']),
                row['price'],
                md_escape(row['reason']),
                md_escape(row['next_check']),
            ])
            + ' |'
        )

    OUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> None:
    rows = build_recommendations(load_rows())
    write_csv(rows)
    write_md(rows)
    print(f'wrote {OUT_CSV}')
    print(f'wrote {OUT_MD}')
    print(f'total={len(rows)} S={sum(1 for r in rows if r["recommendation"] == "S")} A={sum(1 for r in rows if r["recommendation"] == "A")}')


if __name__ == '__main__':
    main()
