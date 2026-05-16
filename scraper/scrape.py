"""
買取価格スクレイパー
- モバイル一番 (requests POST + BeautifulSoup)
- 買取一丁目   (requests + JSON REST API)
"""

import csv
import logging
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from products import ALL_PRODUCTS

# ── ログ設定 ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)

# ── 定数 ──────────────────────────────────────────────────────────────
JST = timezone(timedelta(hours=9))
TODAY = datetime.now(JST).strftime('%Y-%m-%d')

BASE_DIR = Path(__file__).parent.parent
DATA_FILE = BASE_DIR / 'data' / 'prices.csv'
CSV_HEADERS = ['date', 'product_name', 'store', 'price']

COMMON_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
}

_PRICE_RE = re.compile(r'([\d,]+)\s*円')


def parse_price(text: str) -> int | None:
    """価格文字列 "55,000円" → 55000"""
    m = _PRICE_RE.search(text.replace('　', ' '))
    if m:
        try:
            return int(m.group(1).replace(',', ''))
        except ValueError:
            return None
    return None


def match_product(text: str) -> dict | None:
    """テキストが products.py のどの商品に対応するか"""
    text_lower = text.lower()
    for product in ALL_PRODUCTS:
        for kw in product['keywords']:
            if kw.lower() in text_lower:
                return product
    return None


# ════════════════════════════════════════════════════════════════════════
# モバイル一番スクレイパー（POST ベース）
# ════════════════════════════════════════════════════════════════════════
MOBILE_ICHIBAN_BASE = 'https://www.mobile-ichiban.com'

# カテゴリコード → タグ名（tagNameLevel1）
MOBILE_ICHIBAN_CATEGORIES = [
    ('2', '家電買取'),    # ゲーム機・カメラ
    ('3', 'おもちゃ買取'), # トレカ・ぬいぐるみ等
]


def _mobile_post(session: requests.Session, cat_code: str, tag_name: str) -> str | None:
    """カテゴリ POST → HTML を返す"""
    post_data = {
        'g01Search': '',
        'g01tagLevel': '1',
        'g01tagCodeLevel1': cat_code,
        'g01tagCodeLevel2': '',
        'g01tagCodeLevel3': '',
        'g01tagNameLevel1': tag_name,
        'g01tagNameLevel2': '',
        'g01tagNameLevel3': '',
        'LeftTagJson': '',
        'TagJson': '',
        'g01ListOrImg': '2',
        'idCustom': '',
        'X-Requested-With': 'XMLHttpRequest',
    }
    headers = {
        **COMMON_HEADERS,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': MOBILE_ICHIBAN_BASE + '/',
    }
    try:
        resp = session.post(
            MOBILE_ICHIBAN_BASE + '/',
            data=post_data,
            headers=headers,
            timeout=30,
        )
        if resp.status_code == 200:
            logger.info(f'モバイル一番 cat={cat_code}: {len(resp.text):,} bytes')
            return resp.text
        logger.warning(f'モバイル一番 cat={cat_code}: HTTP {resp.status_code}')
    except Exception as e:
        logger.error(f'モバイル一番 POST エラー: {e}')
    return None


def _parse_card_bodies(html: str) -> list[tuple[str, int]]:
    """
    div.card-body から (商品名, 価格) を抽出する。
    典型的な内容: "Nintendo Switch 2 国内版|JAN:4902370553024|新品|51,000円"
    """
    soup = BeautifulSoup(html, 'lxml')
    pairs = []

    for card in soup.find_all('div', class_='card-body'):
        text = card.get_text(separator='|', strip=True)
        parts = [p.strip() for p in text.split('|') if p.strip()]

        price = None
        name = None

        for part in parts:
            p = parse_price(part)
            if p and p > 500:
                if price is None:
                    price = p
            elif (
                name is None
                and not part.startswith('JAN:')
                and not re.match(r'^\d{4,}$', part)
                and len(part) > 2
            ):
                name = part

        if name and price:
            pairs.append((name, price))

    logger.info(f'  card-body パース結果: {len(pairs)} ペア')
    return pairs


def scrape_mobile_ichiban() -> list[dict]:
    results = []
    store = 'モバイル一番'
    found_products: dict[str, int] = {}

    session = requests.Session()
    # Cookie 取得のためトップページを先に GET
    try:
        session.get(
            MOBILE_ICHIBAN_BASE + '/',
            headers={**COMMON_HEADERS, 'Accept': 'text/html,*/*'},
            timeout=20,
        )
    except Exception as e:
        logger.warning(f'モバイル一番 トップページ取得失敗: {e}')

    for cat_code, tag_name in MOBILE_ICHIBAN_CATEGORIES:
        html = _mobile_post(session, cat_code, tag_name)
        if not html:
            time.sleep(2)
            continue

        pairs = _parse_card_bodies(html)

        for text, price in pairs:
            product = match_product(text)
            if product and product['name'] not in found_products:
                found_products[product['name']] = price
                logger.info(f'  ✓ {product["name"]} → ¥{price:,}')

        time.sleep(2)

    for name, price in found_products.items():
        results.append({
            'date': TODAY, 'product_name': name,
            'store': store, 'price': price,
        })

    logger.info(f'モバイル一番: {len(results)} 件')
    return results


# ════════════════════════════════════════════════════════════════════════
# 買取一丁目スクレイパー（JSON REST API）
# ════════════════════════════════════════════════════════════════════════
ICHOME_BASE = 'https://www.1-chome.com'
ICHOME_API = ICHOME_BASE + '/api/goods/listPage'

# (cateCode, 説明)
ICHOME_CATEGORIES = [
    ('10000005',         'ゲーム'),
    ('10000001',         'カメラ本体・周辺'),
    ('20279112',         'インスタントカメラ'),
    ('20985614',         'チェキフイルム'),
    ('IIzyMdayU5wp7T4G', 'ポケモンカード'),
    ('SEbO7gSBevo6KsPE', 'ONE PIECE カード'),
]

ICHOME_HEADERS = {
    **COMMON_HEADERS,
    'Accept': 'application/json, text/plain, */*',
    'Referer': ICHOME_BASE + '/',
}


def _ichome_fetch(session: requests.Session, cate_code: str, page: int = 1, size: int = 100) -> dict | None:
    params = {
        'accCode': '',
        'page': page,
        'size': size,
        'keyword': '',
        'isImpo': 'true',
        'isCampaign': 'false',
        'cateCode': cate_code,
    }
    try:
        resp = session.get(ICHOME_API, params=params, headers=ICHOME_HEADERS, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        logger.warning(f'買取一丁目 {cate_code} p{page}: HTTP {resp.status_code}')
    except Exception as e:
        logger.error(f'買取一丁目 API エラー {cate_code}: {e}')
    return None


def _ichome_price(item: dict) -> int | None:
    """API アイテムから買取価格を取得"""
    # 優先: goodsKbDetails[0].kbDetailPrice
    for detail in item.get('goodsKbDetails', []):
        p = detail.get('kbDetailPrice')
        if p and int(p) > 0:
            return int(p)
    # fallback: price フィールド
    p = item.get('price')
    if p and int(p) > 0:
        return int(p)
    return None


def scrape_ichome() -> list[dict]:
    results = []
    store = '買取一丁目'
    found_products: dict[str, int] = {}

    session = requests.Session()

    for cate_code, cate_name in ICHOME_CATEGORIES:
        page = 1
        total_fetched = 0

        while True:
            data = _ichome_fetch(session, cate_code, page=page, size=100)
            if not data:
                break

            page_data = data.get('data', {})
            content = page_data.get('content', [])
            if not content:
                break

            total_fetched += len(content)

            for item in content:
                title = item.get('title', '').strip()
                if not title:
                    continue
                price = _ichome_price(item)
                if not price:
                    continue
                product = match_product(title)
                if product and product['name'] not in found_products:
                    found_products[product['name']] = price
                    logger.info(f'  ✓ {product["name"]} → ¥{price:,}  ({title})')

            total_pages = page_data.get('totalPages', 1)
            if page >= total_pages:
                break
            page += 1
            time.sleep(0.5)

        logger.info(f'  {cate_name} ({cate_code}): {total_fetched} アイテム')
        time.sleep(1)

    for name, price in found_products.items():
        results.append({
            'date': TODAY, 'product_name': name,
            'store': store, 'price': price,
        })

    logger.info(f'買取一丁目: {len(results)} 件')
    return results


# ════════════════════════════════════════════════════════════════════════
# CSV 書き込み
# ════════════════════════════════════════════════════════════════════════

def save_to_csv(records: list[dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_header = not DATA_FILE.exists() or DATA_FILE.stat().st_size == 0

    existing_keys: set[tuple] = set()
    if DATA_FILE.exists():
        with open(DATA_FILE, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('date') == TODAY:
                    existing_keys.add((row['date'], row['product_name'], row['store']))

    new_records = [
        r for r in records
        if (r['date'], r['product_name'], r['store']) not in existing_keys
    ]

    if not new_records:
        logger.info('新規レコードなし（既にスクレイプ済み？）')
        return

    with open(DATA_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if write_header:
            writer.writeheader()
        writer.writerows(new_records)

    logger.info(f'CSV に {len(new_records)} 件追記: {DATA_FILE}')


# ════════════════════════════════════════════════════════════════════════
# エントリポイント
# ════════════════════════════════════════════════════════════════════════

def main() -> None:
    logger.info(f'=== 価格収集開始 {TODAY} ===')

    all_records: list[dict] = []

    logger.info('--- モバイル一番 ---')
    all_records.extend(scrape_mobile_ichiban())

    logger.info('--- 買取一丁目 ---')
    all_records.extend(scrape_ichome())

    logger.info(f'合計 {len(all_records)} 件取得')
    save_to_csv(all_records)
    logger.info('=== 完了 ===')


if __name__ == '__main__':
    main()
