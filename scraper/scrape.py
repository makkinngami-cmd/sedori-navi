"""
買取価格スクレイパー
- 買取一丁目 (requests + JSON REST API)
"""

import csv
import logging
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

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
CSV_HEADERS = ['date', 'product_name', 'store', 'price', 'jan', 'url']

_JAN_RE = re.compile(r'\b(\d{13})\b')

COMMON_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
}


def _normalize(s: str) -> str:
    """全角スペース・全角括弧を半角化し小文字化する"""
    s = s.replace('　', ' ')           # 全角スペース
    s = s.replace('（', ' ').replace('）', ' ')  # 全角丸括弧
    s = s.replace('【', ' ').replace('】', ' ')  # 全角角括弧
    s = re.sub(r' +', ' ', s)         # 連続スペースを圧縮
    return s.lower().strip()

def match_product(text: str) -> dict | None:
    """テキストが products.py のどの商品に対応するか"""
    text_n = _normalize(text)
    for product in ALL_PRODUCTS:
        for kw in product['keywords']:
            if _normalize(kw) in text_n:
                return product
    return None


# ════════════════════════════════════════════════════════════════════════
# 買取一丁目スクレイパー（JSON REST API）
# ════════════════════════════════════════════════════════════════════════
ICHOME_BASE = 'https://www.1-chome.com'
ICHOME_API = ICHOME_BASE + '/api/goods/listPage'

# (cateCode, 説明, isImpo)
# トレカ系は isImpo=false でないと 0 件になる
ICHOME_CATEGORIES = [
    ('10000005',         'ゲーム',                True),
    ('20304465',         'Steam Deck',            True),
    ('10000001',         'カメラ本体・周辺',        True),
    ('20279112',         'インスタントカメラ',      True),
    ('20985614',         'チェキフイルム',          True),
    ('IIzyMdayU5wp7T4G', 'ポケモンカード',          False),
    ('SEbO7gSBevo6KsPE', 'ONE PIECE カード',        False),
]

ICHOME_HEADERS = {
    **COMMON_HEADERS,
    'Accept': 'application/json, text/plain, */*',
    'Referer': ICHOME_BASE + '/',
}


def _ichome_fetch(
    session: requests.Session,
    cate_code: str,
    is_impo: bool,
    page: int = 1,
    size: int = 100,
) -> dict | None:
    params = {
        'accCode': '',
        'page': page,
        'size': size,
        'keyword': '',
        'isImpo': 'true' if is_impo else 'false',
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

    for cate_code, cate_name, is_impo in ICHOME_CATEGORIES:
        page = 1
        total_fetched = 0

        while True:
            data = _ichome_fetch(session, cate_code, is_impo, page=page, size=100)
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
                    jan = str(item.get('jan') or '') or ''
                    goods_id = item.get('goodsId', '')
                    url = f'{ICHOME_BASE}/wineDetail/{goods_id}/{goods_id}' if goods_id else ''
                    found_products[product['name']] = {'price': price, 'jan': jan, 'url': url}
                    logger.info(f'  ✓ {product["name"]} → ¥{price:,}  ({title})')
                elif not product:
                    logger.info(f'  - 未マッチ: {title} (¥{price:,})')

            total_pages = page_data.get('totalPages', 1)
            if page >= total_pages:
                break
            page += 1
            time.sleep(0.5)

        logger.info(f'  {cate_name} ({cate_code}): {total_fetched} アイテム取得')
        time.sleep(1)

    for name, info in found_products.items():
        results.append({
            'date': TODAY, 'product_name': name,
            'store': store, 'price': info['price'],
            'jan': info['jan'], 'url': info['url'],
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
    # 欠けているフィールドの補完
    for r in new_records:
        r.setdefault('jan', '')
        r.setdefault('url', '')

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

    logger.info('--- 買取一丁目 ---')
    all_records = scrape_ichome()

    logger.info(f'合計 {len(all_records)} 件取得')
    save_to_csv(all_records)
    logger.info('=== 完了 ===')


if __name__ == '__main__':
    main()
