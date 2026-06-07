"""
Generate product expansion candidates from 買取一丁目.

This script does not modify products.py or prices.csv. It fetches the
current 買取一丁目 listing, compares items by JAN/name with existing
sedori-navi products, and writes reports for deciding what to add next.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import time

import requests

from products import ALL_PRODUCTS


JST = timezone(timedelta(hours=9))
TODAY = datetime.now(JST).strftime('%Y-%m-%d')

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / 'data' / 'prices.csv'
REPORT_DIR = BASE_DIR / 'reports'
CSV_REPORT = REPORT_DIR / 'ichome_product_candidates.csv'
MD_REPORT = REPORT_DIR / 'ichome_product_candidates.md'

ICHOME_BASE = 'https://www.1-chome.com'
ICHOME_API = ICHOME_BASE + '/api/goods/listPage'
KEITAI_API = ICHOME_BASE + '/api/keitai/listPage'
KEITAI_CATE = 'RGNg976kptBN7UjF'

COMMON_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
    'Referer': ICHOME_BASE + '/',
}

# Keep this aligned with scraper/scrape.py.
ICHOME_CATEGORIES = [
    ('10000005', 'ゲーム', False),
    ('20304465', 'Steam Deck', True),
    ('10000001', 'カメラ', False),
    ('20279112', 'カメラ', False),
    ('20985614', 'カメラ', False),
    ('IIzyMdayU5wp7T4G', 'ポケカ', False),
    ('SEbO7gSBevo6KsPE', 'ワンピ', False),
    ('20482781', 'その他', False),
]

CSV_HEADERS = [
    'priority',
    'status',
    'category',
    'ichome_title',
    'ichome_original_title',
    'jan',
    'price',
    'url',
    'matched_product_name',
    'matched_by',
    'reason',
]

JAN_RE = re.compile(r'\b(\d{13})\b')


@dataclass
class Candidate:
    category: str
    title: str
    original_title: str
    jan: str
    price: int
    url: str
    matched_product_name: str = ''
    matched_by: str = ''
    status: str = ''
    priority: str = ''
    reason: str = ''


def normalize_text(value: str) -> str:
    value = value.replace('　', ' ')
    value = value.replace('（', ' ').replace('）', ' ')
    value = value.replace('【', ' ').replace('】', ' ')
    return re.sub(r'\s+', ' ', value).strip().lower()


def normalize_jan(value: str | int | None) -> str:
    if value is None:
        return ''
    match = JAN_RE.search(str(value))
    return match.group(1) if match else ''


def strip_embedded_jan(title: str, jan: str) -> str:
    cleaned = title
    if jan:
        cleaned = cleaned.replace(jan, '')
    cleaned = re.sub(r'\b(?:JAN|EAN)\s*[:：]?\s*\d{13}\w?\b', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def ichome_price(item: dict) -> int | None:
    for detail in item.get('goodsKbDetails', []):
        price = detail.get('kbDetailPrice')
        if price and int(price) > 0:
            return int(price)
    price = item.get('price')
    if price and int(price) > 0:
        return int(price)
    return None


def keitai_unopened_detail(item: dict) -> dict | None:
    return next(
        (
            detail
            for detail in item.get('goodsKbDetails', [])
            if detail.get('kbDetailName') == '未開封' and detail.get('kbDetailPrice')
        ),
        None,
    )


def build_existing_indexes() -> tuple[dict[str, str], dict[str, str]]:
    by_name = {product['name']: product for product in ALL_PRODUCTS}
    by_jan: dict[str, str] = {}
    normalized_names: dict[str, str] = {}

    for product in ALL_PRODUCTS:
        normalized_names[normalize_text(product['name'])] = product['name']
        for jan in product.get('jans', []):
            norm = normalize_jan(jan)
            if norm:
                by_jan.setdefault(norm, product['name'])
        norm = normalize_jan(product.get('jan'))
        if norm:
            by_jan.setdefault(norm, product['name'])

    if DATA_FILE.exists():
        with DATA_FILE.open(newline='', encoding='utf-8') as file:
            for row in csv.DictReader(file):
                product_name = row.get('product_name', '')
                if product_name not in by_name:
                    continue
                normalized_names.setdefault(normalize_text(product_name), product_name)
                jan = normalize_jan(row.get('jan'))
                if jan:
                    by_jan.setdefault(jan, product_name)

    return by_jan, normalized_names


def fetch_normal_candidates() -> list[Candidate]:
    session = requests.Session()
    candidates: list[Candidate] = []
    seen: set[tuple[str, str, str]] = set()

    for cate_code, category, is_impo in ICHOME_CATEGORIES:
        page = 1
        while True:
            params = {
                'accCode': '',
                'page': page,
                'size': 100,
                'keyword': '',
                'isImpo': 'true' if is_impo else 'false',
                'isCampaign': 'false',
                'cateCode': cate_code,
            }
            response = session.get(ICHOME_API, params=params, headers=COMMON_HEADERS, timeout=30)
            response.raise_for_status()
            page_data = response.json().get('data', {})
            content = page_data.get('content', [])
            if not content:
                break

            for item in content:
                title = str(item.get('title') or '').strip()
                price = ichome_price(item)
                if not title or not price:
                    continue
                jan = normalize_jan(item.get('jan'))
                goods_id = item.get('goodsId', '')
                url = f'{ICHOME_BASE}/wineDetail/{goods_id}/{goods_id}' if goods_id else ''
                key = (category, jan, title)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(Candidate(category, strip_embedded_jan(title, jan), title, jan, price, url))

            if page >= int(page_data.get('totalPages') or 1):
                break
            page += 1
            time.sleep(0.25)
        time.sleep(0.5)

    return candidates


def fetch_keitai_candidates() -> list[Candidate]:
    session = requests.Session()
    candidates: list[Candidate] = []
    seen: set[tuple[str, str]] = set()
    page = 1
    headers = {
        **COMMON_HEADERS,
        'Referer': f'{ICHOME_BASE}/mobile?category={KEITAI_CATE}',
    }

    while True:
        params = {
            'accCode': '',
            'page': page,
            'size': 100,
            'keyword': '',
            'isImpo': 'false',
            'isCampaign': 'false',
            'cateCode': KEITAI_CATE,
            'kbNames': '',
            'isImpoCate': 'false',
        }
        response = session.get(KEITAI_API, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        page_data = response.json().get('data', {})
        content = page_data.get('content', [])
        if not content:
            break

        for item in content:
            title = str(item.get('title') or '').strip()
            detail = keitai_unopened_detail(item)
            if not title or not detail:
                continue
            base_price = int(detail['kbDetailPrice'])
            detail_id = detail.get('allGoodsKbDetailId')
            goods_id = item.get('goodsId', '')
            url = f'{ICHOME_BASE}/mobileDetail/{goods_id}/{goods_id}' if goods_id else ''

            for color_option in item.get('keitaiColorOptions', []):
                color = str(color_option.get('color') or '').strip()
                jan = normalize_jan(color_option.get('jan'))
                var_price = 0
                for rel in color_option.get('keitaiKbDetailColorRels', []):
                    if rel.get('keitaiKbDetailId') == detail_id and rel.get('varPrice') is not None:
                        var_price = int(rel['varPrice'])
                        break
                price = base_price + var_price
                product_title = f'{title} {color}'.strip()
                key = (jan, product_title)
                if price <= 0 or key in seen:
                    continue
                seen.add(key)
                candidates.append(
                    Candidate(
                        'スマートフォン',
                        strip_embedded_jan(product_title, jan),
                        product_title,
                        jan,
                        price,
                        url,
                    )
                )

        if page >= int(page_data.get('totalPages') or 1):
            break
        page += 1
        time.sleep(0.25)

    return candidates


def annotate_candidates(candidates: list[Candidate]) -> list[Candidate]:
    existing_by_jan, existing_by_name = build_existing_indexes()

    for candidate in candidates:
        if candidate.jan and candidate.jan in existing_by_jan:
            candidate.status = 'registered'
            candidate.matched_product_name = existing_by_jan[candidate.jan]
            candidate.matched_by = 'jan'
            candidate.priority = '既存'
            candidate.reason = '既存商品とJAN一致'
            continue

        normalized_title = normalize_text(candidate.title)
        if normalized_title in existing_by_name:
            candidate.status = 'registered'
            candidate.matched_product_name = existing_by_name[normalized_title]
            candidate.matched_by = 'name'
            candidate.priority = '既存'
            candidate.reason = '既存商品名と一致'
            continue

        candidate.status = 'new_candidate'
        if not candidate.jan:
            candidate.priority = 'C'
            candidate.reason = 'JANなし。正式追加は慎重に確認'
        elif is_first_wave_candidate(candidate):
            candidate.priority = 'A'
            candidate.reason = 'JANあり、初回追加候補カテゴリ'
        else:
            candidate.priority = 'B'
            candidate.reason = 'JANあり未登録'

    return candidates


def is_first_wave_candidate(candidate: Candidate) -> bool:
    if not candidate.jan:
        return False
    if candidate.category in {'ゲーム', 'スマートフォン'}:
        return candidate.price >= 3000
    if candidate.category in {'ポケカ', 'ワンピ'}:
        return candidate.price >= 5000
    if candidate.category != 'カメラ':
        return False

    title = normalize_text(candidate.title)
    focus_terms = [
        'powershot',
        'ixy',
        'ricoh gr',
        'gr iii',
        'gr iv',
        'x100',
        'instax',
        'チェキ',
        '写ルンです',
        'tamron 18-300',
        'tamron 28-75',
        'tamron 28-200',
        'tamron 28-300',
        'z50',
        'lumix dc-tz',
    ]
    return any(term in title for term in focus_terms)


def sort_key(candidate: Candidate) -> tuple[int, int, str]:
    priority_rank = {'A': 0, 'B': 1, 'C': 2, '既存': 3}
    category_rank = {
        'ゲーム': 0,
        'スマートフォン': 1,
        'ポケカ': 2,
        'ワンピ': 3,
        'カメラ': 4,
        'Steam Deck': 5,
        'その他': 6,
    }
    return (
        priority_rank.get(candidate.priority, 9),
        category_rank.get(candidate.category, 9),
        -candidate.price,
        candidate.title,
    )


def write_csv(candidates: list[Candidate]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_REPORT.open('w', newline='', encoding='utf-8-sig') as file:
        writer = csv.DictWriter(file, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for candidate in sorted(candidates, key=sort_key):
            writer.writerow({
                'priority': candidate.priority,
                'status': candidate.status,
                'category': candidate.category,
                'ichome_title': candidate.title,
                'ichome_original_title': candidate.original_title,
                'jan': candidate.jan,
                'price': candidate.price,
                'url': candidate.url,
                'matched_product_name': candidate.matched_product_name,
                'matched_by': candidate.matched_by,
                'reason': candidate.reason,
            })


def md_escape(value: str) -> str:
    return value.replace('|', '\\|').replace('\n', ' ')


def write_md(candidates: list[Candidate]) -> None:
    new_candidates = [candidate for candidate in candidates if candidate.status == 'new_candidate']
    priority_counts = {
        priority: sum(1 for candidate in new_candidates if candidate.priority == priority)
        for priority in ['A', 'B', 'C']
    }
    registered_count = sum(1 for candidate in candidates if candidate.status == 'registered')
    by_category = {}
    for candidate in new_candidates:
        by_category[candidate.category] = by_category.get(candidate.category, 0) + 1

    lines = [
        '# 買取一丁目 商品追加候補レポート',
        '',
        f'更新日: {TODAY}',
        '',
        '## サマリー',
        '',
        f'- 買取一丁目取得商品数: {len(candidates)}',
        f'- 既存登録済み: {registered_count}',
        f'- 未登録候補: {len(new_candidates)}',
        f'- 優先度A（初回追加候補）: {priority_counts["A"]}',
        f'- 優先度B: {priority_counts["B"]}',
        f'- 優先度C: {priority_counts["C"]}',
        '',
        '## 未登録候補カテゴリ別',
        '',
    ]

    for category, count in sorted(by_category.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f'- {category}: {count}')

    lines.extend([
        '',
        '## 優先候補',
        '',
        'CSV全件: `reports/ichome_product_candidates.csv`',
        '',
        '優先度Aは、ゲーム・スマートフォン・カード系と、既にせどりナビで扱っている系統に近いカメラ商品を初回追加候補として抽出したもの。',
        '',
        '| 優先度 | カテゴリ | 商品名 | JAN | 価格 | 理由 |',
        '|---|---|---|---|---:|---|',
    ])

    for candidate in sorted(new_candidates, key=sort_key)[:120]:
        lines.append(
            '| '
            + ' | '.join([
                md_escape(candidate.priority),
                md_escape(candidate.category),
                md_escape(candidate.title),
                md_escape(candidate.jan),
                f'{candidate.price}',
                md_escape(candidate.reason),
            ])
            + ' |'
        )

    MD_REPORT.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> None:
    candidates = fetch_normal_candidates() + fetch_keitai_candidates()
    annotate_candidates(candidates)
    write_csv(candidates)
    write_md(candidates)
    print(f'wrote {CSV_REPORT}')
    print(f'wrote {MD_REPORT}')
    print(f'total={len(candidates)} new={sum(1 for c in candidates if c.status == "new_candidate")}')


if __name__ == '__main__':
    main()
