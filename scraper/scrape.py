"""
買取価格スクレイパー
- モバイル一番 (SSR / requests + BeautifulSoup)
- 買取一丁目   (動的 / Playwright)
"""

import csv
import logging
import os
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
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
}

# 価格文字列からint抽出： "55,000円" → 55000
_PRICE_RE = re.compile(r'([\d,]+)\s*円')

def parse_price(text: str) -> int | None:
    m = _PRICE_RE.search(text.replace(' ', '').replace(' ', ''))
    if m:
        try:
            return int(m.group(1).replace(',', ''))
        except ValueError:
            return None
    return None

# ── fuzzy 商品マッチング ───────────────────────────────────────────────
def match_product(text: str) -> dict | None:
    """テキストがどの商品に対応するかを返す（最初にヒットしたもの）"""
    text_lower = text.lower()
    for product in ALL_PRODUCTS:
        for kw in product['keywords']:
            if kw.lower() in text_lower:
                return product
    return None


# ════════════════════════════════════════════════════════════════════════
# モバイル一番スクレイパー
# ════════════════════════════════════════════════════════════════════════
MOBILE_ICHIBAN_BASE = 'https://www.mobile-ichiban.com'

# 試みる URL 一覧（カテゴリページ → 商品ページ等）
# ※ 実際の URL は Playwright で事前に調査した結果に基づいています。
#   404 が続く場合は VERIFY_URLS で確認してから追加してください。
MOBILE_ICHIBAN_URLS = [
    '/',                   # ホームページ（注目商品が SSR 掲載）
    '/kaitori/game',
    '/kaitori/camera',
    '/kaitori/card',
    '/kaitori/pokemon',
    '/kaitori/onepiece',
    '/Game',
    '/Camera',
    '/Pokemon',
    '/Onepiece',
]

def _fetch(url: str, session: requests.Session) -> str | None:
    try:
        resp = session.get(url, headers=COMMON_HEADERS, timeout=20)
        if resp.status_code == 200:
            logger.info(f'OK  {url} ({len(resp.text):,} bytes)')
            return resp.text
        logger.warning(f'HTTP {resp.status_code}  {url}')
    except Exception as e:
        logger.error(f'Error fetching {url}: {e}')
    return None


def _extract_from_table(table: BeautifulSoup) -> list[tuple[str, int]]:
    """<table> から (商品名テキスト, 価格) ペアを抽出"""
    pairs = []
    rows = table.find_all('tr')
    for row in rows:
        cells = row.find_all(['td', 'th'])
        if len(cells) < 2:
            continue
        texts = [c.get_text(strip=True) for c in cells]
        # 価格っぽいセルを探す
        for i, t in enumerate(texts):
            price = parse_price(t)
            if price and price > 1000:
                # 前のセルが商品名候補
                for j in range(i):
                    if texts[j]:
                        pairs.append((texts[j], price))
                        break
    return pairs


def _extract_from_page(html: str) -> list[tuple[str, int]]:
    """HTML ページ全体から (商品名テキスト, 価格) を抽出"""
    soup = BeautifulSoup(html, 'lxml')
    pairs = []

    # ① テーブル形式
    for table in soup.find_all('table'):
        pairs.extend(_extract_from_table(table))

    # ② よくある class 名パターン（price, kaitori, buy-price 等）
    price_classes = re.compile(
        r'price|kaitori|buy[_\-]?price|amount|値段|買取',
        re.IGNORECASE
    )
    for el in soup.find_all(class_=price_classes):
        price = parse_price(el.get_text())
        if price and price > 1000:
            # 隣接する親・兄弟要素から商品名を探す
            name_el = (
                el.find_previous(class_=re.compile(r'name|item|product|商品', re.I))
                or el.find_parent()
            )
            if name_el:
                pairs.append((name_el.get_text(strip=True)[:80], price))

    # ③ 「商品名 ... X,XXX円」が同一ブロック内にある汎用パターン
    for block in soup.find_all(['li', 'div', 'article', 'section', 'tr']):
        text = block.get_text(separator=' ', strip=True)
        price = parse_price(text)
        if price and price > 1000 and len(text) < 200:
            pairs.append((text, price))

    return pairs


def scrape_mobile_ichiban() -> list[dict]:
    results = []
    store = 'モバイル一番'
    session = requests.Session()
    found_products: dict[str, int] = {}  # name → price

    for path in MOBILE_ICHIBAN_URLS:
        url = MOBILE_ICHIBAN_BASE + path
        html = _fetch(url, session)
        if not html:
            time.sleep(1)
            continue

        pairs = _extract_from_page(html)
        logger.info(f'  {path}: {len(pairs)} price pairs found')

        for text, price in pairs:
            product = match_product(text)
            if product and product['name'] not in found_products:
                found_products[product['name']] = price
                logger.info(f'  ✓ {product["name"]} → ¥{price:,}')

        time.sleep(1.5)

    for name, price in found_products.items():
        results.append({
            'date': TODAY, 'product_name': name,
            'store': store, 'price': price,
        })

    logger.info(f'モバイル一番: {len(results)} 件')
    return results


# ════════════════════════════════════════════════════════════════════════
# 買取一丁目スクレイパー（Playwright）
# ════════════════════════════════════════════════════════════════════════
ICHOME_BASE = 'https://www.1-chome.com'

ICHOME_URLS = [
    '/',
    '/kaitori/',
    '/kaitori/game/',
    '/kaitori/camera/',
    '/kaitori/card/',
    '/kaitori/pokemon/',
    '/kaitori/onepiece/',
    '/buy/',
    '/price/',
    '/price/game/',
    '/price/camera/',
    '/price/card/',
]


def _pw_extract(page, url: str) -> list[tuple[str, int]]:
    """Playwright page オブジェクトから (テキスト, 価格) を抽出"""
    try:
        page.goto(url, timeout=30000, wait_until='domcontentloaded')
        # 動的コンテンツの描画を少し待つ
        page.wait_for_timeout(3000)
        html = page.content()
        return _extract_from_page(html)
    except Exception as e:
        logger.error(f'Playwright error at {url}: {e}')
        return []


def scrape_ichome() -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error('playwright がインストールされていません: pip install playwright')
        return []

    results = []
    store = '買取一丁目'
    found_products: dict[str, int] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=COMMON_HEADERS['User-Agent'],
            locale='ja-JP',
        )
        page = ctx.new_page()

        # まず TOPページ を取得してリンクを列挙
        try:
            page.goto(ICHOME_BASE + '/', timeout=30000, wait_until='domcontentloaded')
            page.wait_for_timeout(3000)

            # ページ内の href をすべて収集
            hrefs = page.eval_on_selector_all(
                'a[href]',
                'els => els.map(e => e.getAttribute("href"))'
            )
            # 買取・価格関連っぽい内部リンクを追加
            for href in hrefs:
                if not href:
                    continue
                if any(kw in href for kw in ['kaitori', 'price', 'game', 'camera', 'card', 'buy']):
                    full = href if href.startswith('http') else ICHOME_BASE + href
                    if full not in ICHOME_URLS and ICHOME_BASE in full:
                        ICHOME_URLS.append(full)
        except Exception as e:
            logger.warning(f'買取一丁目 TOP取得失敗: {e}')

        for path_or_url in ICHOME_URLS:
            url = path_or_url if path_or_url.startswith('http') else ICHOME_BASE + path_or_url
            pairs = _pw_extract(page, url)
            logger.info(f'  {url}: {len(pairs)} pairs')

            for text, price in pairs:
                product = match_product(text)
                if product and product['name'] not in found_products:
                    found_products[product['name']] = price
                    logger.info(f'  ✓ {product["name"]} → ¥{price:,}')

            time.sleep(1)

        browser.close()

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

    # 今日分の重複を除外（同日・同商品・同店舗は上書きしない）
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
