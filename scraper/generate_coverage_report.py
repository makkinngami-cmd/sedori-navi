"""
商品 × 取得元のカバレッジ表を生成する。

○: 取得実績あり
空欄: 取得実績なし
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from products import ALL_PRODUCTS


BASE_DIR = Path(__file__).parent.parent
PRICES_FILE = BASE_DIR / 'data' / 'prices.csv'
REPORT_DIR = BASE_DIR / 'reports'
CSV_OUT = REPORT_DIR / 'coverage_matrix.csv'
MD_OUT = REPORT_DIR / 'coverage_matrix.md'

BUYBACK_STORES = [
    '買取一丁目',
    'モバイル一番',
    '買取ルデヤ',
    '森森買取',
    '買取ホムラ',
    '買取商店',
]

REFERENCE_STORES = [
    'ヤフオク 中央値',
    'ヤフオク 最安',
    'ヤフオク 最高',
]

STORES = BUYBACK_STORES + REFERENCE_STORES


def _load_rows() -> list[dict]:
    if not PRICES_FILE.exists():
        return []
    with open(PRICES_FILE, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _status(dates: set[str]) -> str:
    return '○' if dates else ''


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        '| ' + ' | '.join(headers) + ' |',
        '| ' + ' | '.join(['---'] * len(headers)) + ' |',
    ]
    for row in rows:
        lines.append('| ' + ' | '.join(row) + ' |')
    return '\n'.join(lines)


def main() -> None:
    rows = _load_rows()
    latest_date = max((r['date'] for r in rows), default='')

    dates_by_product_store: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        product_name = row.get('product_name', '')
        store = row.get('store', '')
        date = row.get('date', '')
        if product_name and store and date:
            dates_by_product_store[(product_name, store)].add(date)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    csv_headers = [
        'category',
        'product_name',
        'ever_buyback_store_count',
        *STORES,
        *[f'{store}_last_date' for store in STORES],
    ]
    csv_rows = []
    for product in ALL_PRODUCTS:
        product_name = product['name']
        ever_count = sum(
            1 for store in BUYBACK_STORES
            if dates_by_product_store[(product_name, store)]
        )
        csv_rows.append({
            'category': product['category'],
            'product_name': product_name,
            'ever_buyback_store_count': ever_count,
            **{
                store: _status(dates_by_product_store[(product_name, store)])
                for store in STORES
            },
            **{
                f'{store}_last_date': max(dates_by_product_store[(product_name, store)], default='')
                for store in STORES
            },
        })

    with open(CSV_OUT, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers)
        writer.writeheader()
        writer.writerows(csv_rows)

    total_products = len(csv_rows)
    no_ever = sum(1 for row in csv_rows if row['ever_buyback_store_count'] == 0)

    md = [
        '# 取得カバレッジ表',
        '',
        f'更新日: {latest_date}',
        '',
        '凡例: `○` 取得実績あり / 空欄 取得実績なし',
        '',
        '`prices.csv` は価格変化があった時だけ追記するため、最新日の行がない商品でも取得失敗とは限らない。最新取得日は `reports/coverage_matrix.csv` に保存する。',
        '',
        f'- 商品数: {total_products}',
        f'- 1業者以上で取得実績がある商品: {total_products - no_ever}',
        f'- 取得実績が一度もない商品: {no_ever}',
        '',
        '## カテゴリ別サマリー',
        '',
    ]

    summary_rows = []
    categories = []
    for product in ALL_PRODUCTS:
        if product['category'] not in categories:
            categories.append(product['category'])
    for category in categories:
        category_rows = [row for row in csv_rows if row['category'] == category]
        summary_rows.append([
            category,
            str(len(category_rows)),
            str(sum(1 for row in category_rows if row['ever_buyback_store_count'] > 0)),
            str(sum(1 for row in category_rows if row['ever_buyback_store_count'] == 0)),
        ])
    md.append(_markdown_table(
        ['カテゴリ', '商品数', '取得実績あり', '取得実績なし'],
        summary_rows,
    ))

    for category in categories:
        md.extend(['', f'## {category}', ''])
        category_rows = [row for row in csv_rows if row['category'] == category]
        table_rows = []
        for row in category_rows:
            table_rows.append([
                row['product_name'],
                str(row['ever_buyback_store_count']),
                *[row[store] for store in STORES],
            ])
        md.append(_markdown_table(
            ['商品', '取得業者数', *STORES],
            table_rows,
        ))

    MD_OUT.write_text('\n'.join(md) + '\n', encoding='utf-8')
    print(f'wrote {CSV_OUT}')
    print(f'wrote {MD_OUT}')


if __name__ == '__main__':
    main()
