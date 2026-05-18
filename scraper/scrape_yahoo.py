#!/usr/bin/env python3
"""
ヤフオク落札価格スクレイパー（週1回実行）
落札済み新品商品の過去7日分から 最安・平均・最高 を取得し prices.csv に追記する

実行:
    cd scraper
    python scrape_yahoo.py
"""

import asyncio
import csv
import io
import logging
import random
import re
import sys
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import mean

from playwright.async_api import async_playwright, Page

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent))
from products import ALL_PRODUCTS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)

JST      = timezone(timedelta(hours=9))
TODAY    = datetime.now(JST).strftime('%Y-%m-%d')
CUTOFF   = (datetime.now(JST) - timedelta(days=7)).strftime('%Y-%m-%d')

BASE_DIR  = Path(__file__).parent.parent
DATA_FILE = BASE_DIR / 'data' / 'prices.csv'
CSV_HEADERS = ['date', 'product_name', 'store', 'price', 'jan', 'url']

SKIP_CATEGORIES = {'ポケカ', 'ワンピ'}

# 商品ごとにヤフオク検索クエリを上書き
CUSTOM_QUERIES: dict[str, str] = {
    'Switch2 国内版マリカーセット': 'Nintendo Switch 2 マリオカートワールド セット',
    'Switch2 国内版':              'Nintendo Switch 2 本体 国内版',
    'Switch2 多言語版':            'Nintendo Switch 2 本体 多言語版',
    'Switch2 Proコン':             'Nintendo Switch 2 Proコントローラー',
    'Switch2 ブラックボルト':      'Nintendo Switch 2 ブラックボルト',
    'Switch2 ホワイトフレア':      'Nintendo Switch 2 ホワイトフレア',
    'Switch 有機白':               'Nintendo Switch 有機ELモデル ホワイト',
    'Switch 有機ネオン':           'Nintendo Switch 有機ELモデル ネオン',
    'Switch 新型ネオン':           'Nintendo Switch 本体 ネオンブルー ネオンレッド',
    'Switch 新型グレー':           'Nintendo Switch 本体 グレー',
    'Switch Liteグレー':           'Nintendo Switch Lite グレー',
    'Switch Liteブルー':           'Nintendo Switch Lite ブルー',
    'Switch Liteコーラル':         'Nintendo Switch Lite コーラル',
    'Switch Liteターコイズ':       'Nintendo Switch Lite ターコイズ',
    'Switch Liteイエロー':         'Nintendo Switch Lite イエロー',
    'Switch Proコン':              'Nintendo Switch Proコントローラー',
    'Switch Proコン ゼルダ':       'Nintendo Switch Proコントローラー ゼルダの伝説 知恵のかりもの',
    'Switch Proコン スプラ3':      'Nintendo Switch Proコントローラー スプラトゥーン3',
    'Alarmo':                      'Nintendo サウンドクロック Alarmo',
    'Pokemon GO Plus+':            'Pokemon GO Plus+',
    'PS5デジタル':                 'PlayStation 5 デジタル・エディション',
    'PS5':                         'PlayStation 5 本体',
    'PlayStation5 Pro':            'PlayStation 5 Pro',
    'リモートプレーヤー':          'PlayStation Portal リモートプレーヤー',
    'PlayStation VR2':             'PlayStation VR2',
    'PlayStation VR2 Horizon同梱版': 'PlayStation VR2 Horizon Call of the Mountain',
    'Xbox X 1TB ホワイト':         'Xbox Series X 1TB ホワイト',
    'Xbox S 1TB ホワイト':         'Xbox Series S 1TB ホワイト',
    'Xbox X':                      'Xbox Series X',
    'Xbox S':                      'Xbox Series S',
    'Meta Quest 3 512':            'Meta Quest 3 512GB',
    'Meta Quest 3 128':            'Meta Quest 3 128GB',
    'Steam Deck OLED 1TB':         'Steam Deck OLED 1TB',
    'Steam Deck OLED 512':         'Steam Deck OLED 512GB',
    'Steam Deck LCD 512':          'Steam Deck LCD 512GB',
}


# ── ユーティリティ ────────────────────────────────────────────────────

async def sleep_human() -> None:
    await asyncio.sleep(random.uniform(2.5, 5.0))


def build_query(name: str) -> str:
    if name in CUSTOM_QUERIES:
        return CUSTOM_QUERIES[name]
    q = name
    q = re.sub(r'^Switch2\b',    'Nintendo Switch 2',   q)
    q = re.sub(r'^Switch Lite\b','Nintendo Switch Lite', q)
    q = re.sub(r'^Switch\b',     'Nintendo Switch',     q)
    q = re.sub(r'^Joy-Con 2\b',  'Nintendo Joy-Con 2',  q)
    q = re.sub(r'^Joy-Con\b',    'Nintendo Joy-Con',    q)
    if re.search(r'G7[_ ]?X|SX740|IXY|PowerShot|G1 X', q) and 'Canon' not in q:
        q = 'Canon ' + q
    if re.search(r'X100VI|instax|チェキ|WIDE 400|SQ1|mini (13|Evo)', q):
        if 'FUJIFILM' not in q and 'Fujifilm' not in q:
            q = 'FUJIFILM ' + q
    if re.search(r'Tamagotchi|たまごっち', q) and 'BANDAI' not in q:
        q = 'BANDAI ' + q
    q = q.replace('（新）', '').replace('（旧）', '').replace('（', ' ').replace('）', ' ')
    return re.sub(r'\s+', ' ', q).strip()


def parse_yahoo_date(date_str: str) -> str | None:
    """ヤフオクの各種日付フォーマットを YYYY-MM-DD に変換"""
    now = datetime.now(JST)
    s = date_str.strip()

    # "N分前" / "N時間前" → 今日
    if re.search(r'\d+(分|時間)前', s):
        return now.strftime('%Y-%m-%d')

    # "N日前"
    m = re.match(r'(\d+)日前', s)
    if m:
        return (now - timedelta(days=int(m.group(1)))).strftime('%Y-%m-%d')

    # "YYYY年M月D日"
    m = re.match(r'(\d{4})年(\d+)月(\d+)日', s)
    if m:
        return f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'

    # "M月D日"（年なし → 今年、ただし未来なら昨年）
    m = re.match(r'(\d+)月(\d+)日', s)
    if m:
        mo, da = int(m.group(1)), int(m.group(2))
        yr = now.year
        if (mo, da) > (now.month, now.day):
            yr -= 1
        return f'{yr}-{mo:02d}-{da:02d}'

    # "YYYY/MM/DD" or "YYYY-MM-DD"
    m = re.match(r'(\d{4})[-/](\d{2})[-/](\d{2})', s)
    if m:
        return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'

    # datetime 属性 (ISO8601 "2026-05-18T...")
    m = re.match(r'(\d{4}-\d{2}-\d{2})', s)
    if m:
        return m.group(1)

    return None


# ── ヤフオク スクレイパー ────────────────────────────────────────────

YAHOO_CLOSED = 'https://auctions.yahoo.co.jp/closedsearch/closedsearch'


async def fetch_closed_auctions(
    page: Page,
    query: str,
    min_price: int = 0,
) -> list[dict]:
    """
    ヤフオク落札済み検索（新品: istatus=1）から過去7日分の落札価格リストを取得。
    Returns: [{'title': str, 'price': int, 'date': 'YYYY-MM-DD', 'url': str}, ...]
    """
    params = urllib.parse.urlencode({
        'p':       query,
        'istatus': '1',         # 新品
        'n':       '100',       # 1ページ最大件数
        'b':       '1',
        'ei':      'UTF-8',
    })
    if min_price > 0:
        params += f'&min={min_price}'

    url = f'{YAHOO_CLOSED}?{params}'
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30_000)
    except Exception as e:
        logger.warning(f'  ページ遷移エラー ({query}): {e}')
        return []
    await sleep_human()

    raw = await page.evaluate(r"""() => {
        const results = [];
        // 複数のセレクターパターンを試す（ヤフオクのHTML構造変化に対応）
        const cards = [
            ...document.querySelectorAll('.Product'),
            ...document.querySelectorAll('[class*="SearchResult"] li'),
            ...document.querySelectorAll('[data-auction-id]'),
        ].filter((el, i, arr) => arr.indexOf(el) === i); // 重複排除

        for (const card of cards) {
            // タイトル
            let title = '';
            for (const sel of [
                '.Product__title',
                'h3[class*="title"]',
                '[class*="itemTitle"]',
                'a.Product__imageLink',
                'h3', 'h2',
            ]) {
                const el = card.querySelector(sel);
                if (el && el.textContent.trim()) {
                    title = el.textContent.trim().replace(/\s+/g, ' ');
                    break;
                }
            }

            // 価格
            let price = 0;
            for (const sel of [
                '.Product__price',
                '[class*="itemPrice"]',
                '[class*="price"]',
                '[class*="Price"]',
            ]) {
                const el = card.querySelector(sel);
                if (el) {
                    const m = el.textContent.match(/[\d,]+/);
                    if (m) { price = parseInt(m[0].replace(/,/g, ''), 10); break; }
                }
            }

            // 日付（datetime 属性 > テキスト）
            let dateStr = '';
            for (const sel of [
                'time[datetime]',
                '.Product__time',
                '[class*="endTime"]',
                '[class*="time"]',
                'time',
            ]) {
                const el = card.querySelector(sel);
                if (el) {
                    dateStr = el.getAttribute('datetime') || el.textContent.trim();
                    if (dateStr) break;
                }
            }

            // URL
            let href = '';
            const linkEl = card.querySelector('a[href*="yahoo.co.jp/auction/"]')
                        || card.querySelector('a[href*="/auction/"]')
                        || card.querySelector('a');
            if (linkEl) href = linkEl.href || '';

            if (title && price > 0) {
                results.push({ title, price, dateStr, url: href });
            }
        }
        return results;
    }""")

    # 日付パース & 7日以内フィルタ
    results = []
    for item in raw:
        date = parse_yahoo_date(item['dateStr'])
        if date and date >= CUTOFF:
            results.append({
                'title': item['title'],
                'price': item['price'],
                'date':  date,
                'url':   item['url'],
            })

    return results


async def scrape_product_yahoo(
    page: Page,
    name: str,
    query: str,
    keywords: list[str],
    min_price: int = 0,
) -> list[dict]:
    """
    1商品分のヤフオク落札データを取得し、最安・平均・最高をまとめて返す。
    """
    items = await fetch_closed_auctions(page, query, min_price)

    if not items:
        logger.info(f'  -- {name}: 落札データなし')
        return []

    # キーワードマッチング（自分の商品に合致するものだけ使う）
    def matches(title: str) -> bool:
        t = title.lower().replace('　', ' ')
        for kw in keywords:
            if kw.lower() in t:
                return True
        return False

    matched = [it for it in items if matches(it['title'])]
    if not matched:
        logger.info(f'  -- {name}: マッチする落札なし ({len(items)} 件中)')
        return []

    prices = [it['price'] for it in matched]
    lo  = min(prices)
    hi  = max(prices)
    avg = round(mean(prices))
    url = matched[0]['url']  # 代表URL（最初にマッチしたもの）

    logger.info(
        f'  OK {name}: {len(matched)} 件 最安¥{lo:,} 平均¥{avg:,} 最高¥{hi:,}'
    )

    return [
        {'date': TODAY, 'product_name': name, 'store': 'ヤフオク 最安', 'price': lo,  'jan': '', 'url': url},
        {'date': TODAY, 'product_name': name, 'store': 'ヤフオク 平均', 'price': avg, 'jan': '', 'url': url},
        {'date': TODAY, 'product_name': name, 'store': 'ヤフオク 最高', 'price': hi,  'jan': '', 'url': url},
    ]


# ── CSV 書き込み ──────────────────────────────────────────────────────

def save_to_csv(records: list[dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_header = not DATA_FILE.exists() or DATA_FILE.stat().st_size == 0

    # 今日分の重複チェック
    existing_keys: set[tuple] = set()
    if DATA_FILE.exists():
        with open(DATA_FILE, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                if row.get('date') == TODAY:
                    existing_keys.add((row['date'], row['product_name'], row['store']))

    new_records = [
        r for r in records
        if (r['date'], r['product_name'], r['store']) not in existing_keys
    ]

    if not new_records:
        logger.info('新規レコードなし（既にスクレイプ済み）')
        return

    with open(DATA_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if write_header:
            writer.writeheader()
        writer.writerows(new_records)

    logger.info(f'CSV に {len(new_records)} 件追記')


# ── エントリポイント ──────────────────────────────────────────────────

def _already_scraped_today(threshold: int = 10) -> bool:
    """今日分のヤフオクレコードが threshold 件以上あればスキップ"""
    if not DATA_FILE.exists():
        return False
    with open(DATA_FILE, newline='', encoding='utf-8') as f:
        count = sum(
            1 for row in csv.DictReader(f)
            if row.get('date') == TODAY and 'ヤフオク' in row.get('store', '')
        )
    return count >= threshold


async def main() -> None:
    logger.info(f'=== ヤフオク落札価格収集開始 {TODAY} (過去7日: {CUTOFF}〜) ===')

    if _already_scraped_today():
        logger.info('今日分データ取得済み — スキップ')
        return

    targets = [
        p for cat, items in ALL_PRODUCTS.items()
        if cat not in SKIP_CATEGORIES
        for p in items
    ]
    logger.info(f'対象: {len(targets)} 商品')

    all_records: list[dict] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            ),
            locale='ja-JP',
            timezone_id='Asia/Tokyo',
            viewport={'width': 1280, 'height': 900},
        )
        page = await ctx.new_page()

        for i, product in enumerate(targets, 1):
            name     = product['name']
            keywords = product.get('keywords', [name])
            query    = build_query(name)
            logger.info(f'[{i:3}/{len(targets)}] {name}  (検索: {query})')

            records = await scrape_product_yahoo(page, name, query, keywords)
            all_records.extend(records)

            # 20件ごとに中間保存
            if i % 20 == 0:
                save_to_csv(all_records)
                all_records = []
                logger.info(f'      ── 中間保存 ({i}/{len(targets)}) ──')

            await asyncio.sleep(random.uniform(1.0, 2.0))

        await browser.close()

    save_to_csv(all_records)
    logger.info('=== 完了 ===')


if __name__ == '__main__':
    asyncio.run(main())
