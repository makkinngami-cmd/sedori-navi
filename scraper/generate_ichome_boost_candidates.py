"""
Research 買取一丁目's "買取強化中" (boost) products and report new candidates.

買取一丁目 publishes a curated "買取強化中" list via /api/index/getImpoProduct.
These are the products the shop is actively raising buyback prices on, so they
are the highest-signal candidates for adding to sedori-navi.

This script does NOT modify products.py or prices.csv. It fetches the current
boost list, compares each item against existing sedori-navi products by JAN/name,
and writes reports of the boosted products that are not yet tracked.

Run weekly (買取強化 changes slowly). To actually add an approved candidate, use
apply_boost_candidates.py after reviewing the shortlist.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time

import requests

# Reuse the shared helpers from the general candidate generator.
from generate_ichome_product_candidates import (
    COMMON_HEADERS,
    ICHOME_BASE,
    build_existing_indexes,
    normalize_jan,
    normalize_text,
    strip_embedded_jan,
)

JST = timezone(timedelta(hours=9))
TODAY = datetime.now(JST).strftime('%Y-%m-%d')

BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = BASE_DIR / 'reports'
CSV_REPORT = REPORT_DIR / 'ichome_boost_candidates.csv'
MD_REPORT = REPORT_DIR / 'ichome_boost_candidates.md'

BOOST_API = ICHOME_BASE + '/api/index/getImpoProduct'

CSV_HEADERS = [
    'status',
    'category',
    'ichome_title',
    'jan',
    'price',
    'url',
    'matched_product_name',
    'matched_by',
]


@dataclass
class BoostItem:
    title: str
    jan: str
    price: int
    url: str
    category: str = ''
    status: str = ''
    matched_product_name: str = ''
    matched_by: str = ''


def keitai_base_price(item: dict) -> int:
    """Cheapest 未開封/新品 buyback price among goodsKbDetails."""
    prices = [
        int(d['kbDetailPrice'])
        for d in item.get('goodsKbDetails', [])
        if d.get('kbDetailPrice') and int(d['kbDetailPrice']) > 0
    ]
    return min(prices) if prices else 0


def normal_price(item: dict) -> int:
    if item.get('price') and int(item['price']) > 0:
        return int(item['price'])
    return keitai_base_price(item)


def guess_category(title: str) -> str:
    t = normalize_text(title)
    if any(k in t for k in ['iphone', 'galaxy', 'pixel', 'xperia', 'aquos']):
        return 'スマートフォン'
    if any(k in t for k in ['switch', 'playstation', 'ps5', 'xbox', 'steam deck', 'meta quest']):
        return 'ゲーム'
    if any(k in t for k in ['powershot', 'ixy', 'ricoh gr', 'x100', 'instax', 'チェキ',
                            'lumix', 'nikon', 'tamron', 'sigma', 'olympus', 'rx100', 'fujifilm']):
        return 'カメラ'
    if 'box' in t or 'ポケモン' in t or 's＆v' in t.lower():
        return 'ポケカ'
    if 'op-' in t or 'one piece' in t:
        return 'ワンピ'
    return 'その他'


def fetch_boost_items() -> list[BoostItem]:
    session = requests.Session()
    items: list[BoostItem] = []
    seen: set[tuple[str, str]] = set()
    page = 1

    while True:
        params = {'page': page, 'size': 100}
        response = session.get(BOOST_API, params=params, headers=COMMON_HEADERS, timeout=30)
        response.raise_for_status()
        page_data = response.json().get('data') or {}
        content = page_data.get('content', [])
        if not content:
            break

        for item in content:
            title = str(item.get('title') or '').strip()
            if not title:
                continue
            goods_id = item.get('goodsId', '')

            if item.get('isKeitaiItem'):
                base = keitai_base_price(item)
                url = f'{ICHOME_BASE}/mobileDetail/{goods_id}/{goods_id}' if goods_id else ''
                color_options = item.get('keitaiColorOptions', [])
                if not color_options:
                    _push(items, seen, title, '', base, url)
                    continue
                for color_option in color_options:
                    color = str(color_option.get('color') or '').strip()
                    jan = normalize_jan(color_option.get('jan'))
                    product_title = f'{title} {color}'.strip()
                    _push(items, seen, product_title, jan, base, url)
            else:
                jan = normalize_jan(item.get('jan'))
                price = normal_price(item)
                url = f'{ICHOME_BASE}/wineDetail/{goods_id}/{goods_id}' if goods_id else ''
                _push(items, seen, title, jan, price, url)

        if page >= int(page_data.get('totalPages') or 1):
            break
        page += 1
        time.sleep(0.25)

    return items


def _push(items, seen, title, jan, price, url) -> None:
    key = (jan, title)
    if key in seen:
        return
    seen.add(key)
    clean = strip_embedded_jan(title, jan)
    items.append(BoostItem(clean, jan, price, url, category=guess_category(clean)))


def annotate(items: list[BoostItem]) -> None:
    existing_by_jan, existing_by_name = build_existing_indexes()
    for it in items:
        if it.jan and it.jan in existing_by_jan:
            it.status = 'registered'
            it.matched_product_name = existing_by_jan[it.jan]
            it.matched_by = 'jan'
            continue
        norm = normalize_text(it.title)
        if norm in existing_by_name:
            it.status = 'registered'
            it.matched_product_name = existing_by_name[norm]
            it.matched_by = 'name'
            continue
        it.status = 'new_candidate'


def sort_key(it: BoostItem):
    status_rank = {'new_candidate': 0, 'registered': 1}
    return (status_rank.get(it.status, 9), -it.price, it.title)


def write_csv(items: list[BoostItem]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_REPORT.open('w', newline='', encoding='utf-8-sig') as file:
        writer = csv.DictWriter(file, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for it in sorted(items, key=sort_key):
            writer.writerow({
                'status': it.status,
                'category': it.category,
                'ichome_title': it.title,
                'jan': it.jan,
                'price': it.price,
                'url': it.url,
                'matched_product_name': it.matched_product_name,
                'matched_by': it.matched_by,
            })


def md_escape(value: str) -> str:
    return value.replace('|', '\\|').replace('\n', ' ')


def write_md(items: list[BoostItem]) -> None:
    new_items = [it for it in items if it.status == 'new_candidate']
    by_cat: dict[str, int] = {}
    for it in new_items:
        by_cat[it.category] = by_cat.get(it.category, 0) + 1

    lines = [
        '# 買取一丁目 買取強化中 新規候補レポート',
        '',
        f'更新日: {TODAY}',
        '',
        '買取一丁目が「買取強化中」に出している商品のうち、せどりナビ未登録のものを抽出。',
        '買取強化中は値上げ・利ざやが出やすい注目商品。',
        '',
        '## サマリー',
        '',
        f'- 強化中の取得件数: {len(items)}',
        f'- 既存登録済み: {sum(1 for it in items if it.status == "registered")}',
        f'- 未登録の新規候補: {len(new_items)}',
        '',
        '## 新規候補カテゴリ別',
        '',
    ]
    for cat, count in sorted(by_cat.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f'- {cat}: {count}')

    lines.extend([
        '',
        '## 新規候補（強化中・未登録）',
        '',
        'CSV全件: `reports/ichome_boost_candidates.csv`',
        '',
        '| カテゴリ | 商品名 | JAN | 買取価格 |',
        '|---|---|---|---:|',
    ])
    for it in sorted(new_items, key=sort_key):
        lines.append(
            '| ' + ' | '.join([
                md_escape(it.category),
                md_escape(it.title),
                md_escape(it.jan),
                f'{it.price}',
            ]) + ' |'
        )

    MD_REPORT.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> None:
    items = fetch_boost_items()
    annotate(items)
    write_csv(items)
    write_md(items)
    new_count = sum(1 for it in items if it.status == 'new_candidate')
    print(f'wrote {CSV_REPORT}')
    print(f'wrote {MD_REPORT}')
    print(f'total={len(items)} new={new_count}')


if __name__ == '__main__':
    main()
