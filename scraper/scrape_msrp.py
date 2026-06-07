#!/usr/bin/env python3
"""
定価スクレイパー（一回限り実行）
価格.com のメーカー希望小売価格欄から各商品の定価を取得する。
見つからない場合は Amazon の参考価格にフォールバックする。

前準備（初回のみ）:
    pip install playwright
    playwright install chromium

実行:
    cd scraper
    python scrape_msrp.py

結果:
    data/msrp.csv に保存される
    matched_title 列で照合が正しいか確認し、誤りがあれば手動修正してください
"""

import asyncio
import csv
import io
import random
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright, Page

# Windows環境での文字コードエラーを防ぐ
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent))
from products import PRODUCTS

BASE_DIR = Path(__file__).parent.parent
MSRP_FILE = BASE_DIR / 'data' / 'msrp.csv'

# 定価スクレイプをスキップするカテゴリ（単品定価がない）
SKIP_CATEGORIES = {'ポケカ', 'ワンピ'}

# 自動変換がうまくいかない商品用のカスタム検索クエリ
CUSTOM_QUERIES: dict[str, str] = {
    'Nintendo Switch 2 マリオカート ワールドセット 日本語・国内専用':         'Nintendo Switch 2 マリオカートワールド セット',
    'Nintendo Switch 2 日本語・国内専用':                      'Nintendo Switch 2 本体 国内版',
    'Nintendo Switch 2 多言語版':                    'Nintendo Switch 2 本体 多言語版',
    'Nintendo Switch 2 Proコントローラー':                     'Nintendo Switch 2 Proコントローラー',
    'Nintendo Switch (有機ELモデル) ホワイト':                       'Nintendo Switch 有機ELモデル ホワイト',
    'Nintendo Switch (有機ELモデル) ネオンブルー・ネオンレッド':                    'Nintendo Switch 有機ELモデル ネオン',
    'Nintendo Switch 新型 バッテリー強化版 ネオンブルー/(R) ネオンレッド':                    'Nintendo Switch 本体 ネオンブルー ネオンレッド',
    'Nintendo Switch 新型 バッテリー強化版 グレー':                    'Nintendo Switch 本体 グレー',
    'Nintendo Switch Lite グレー':                   'Nintendo Switch Lite グレー',
    'Nintendo Switch Lite ブルー':                   'Nintendo Switch Lite ブルー',
    'Nintendo Switch Lite コーラル':                 'Nintendo Switch Lite コーラル',
    'Nintendo Switch Lite ターコイズ':               'Nintendo Switch Lite ターコイズ',
    'Nintendo Switch Lite イエロー':                 'Nintendo Switch Lite イエロー',
    'Nintendo Switch Proコントローラー':                      'Nintendo Switch Proコントローラー',
    'Nintendo Switch Proコントローラー ゼルダの伝説':               'Nintendo Switch Proコントローラー ゼルダの伝説 知恵のかりもの',
    'Nintendo Switch Proコントローラー スプラトゥーン3エディション':              'Nintendo Switch Proコントローラー スプラトゥーン3',
    'Nintendo Switch ニンテンドーサウンドクロック Alarmo':                              'Nintendo サウンドクロック Alarmo',
    'Pokemon GO Plus +':                    'Pokemon GO Plus+',
    'PS5デジタル':                         'PlayStation 5 デジタル・エディション',
    'PS5':                                 'PlayStation 5 本体',
    'PlayStation5 Pro CFI-7000B01':                    'PlayStation 5 Pro',
    'PlayStation Portal リモートプレーヤー CFIJ-18000':                  'PlayStation Portal リモートプレーヤー',
    'PlayStation Portal リモートプレーヤー ブラック CFIJ-18001':         'PlayStation Portal ブラック CFIJ-18001',
    'PlayStation VR2 CFIJ-17000':                     'PlayStation VR2',
    'PlayStation VR2 “Horizon Call of the Mountain” 同梱版 CFIJ-17001':       'PlayStation VR2 Horizon Call of the Mountain',
    'Xbox Series X 1TB デジタル エディション ホワイト EP2-00708':                 'Xbox Series X 1TB ホワイト',
    'Xbox Series S 1TB ホワイト EP2-00650':                 'Xbox Series S 1TB ホワイト',
    'Xbox Series X RRT-00015':                              'Xbox Series X',
    'Xbox Series S 512 GB EP2-10065':                              'Xbox Series S',
    'Meta Quest 3 512GB':                    'Meta Quest 3 512GB',
    'Meta Quest 3 128GB':                    'Meta Quest 3 128GB',
    'Steam Deck OLED 1TB':                 'Steam Deck OLED 1TB',
    'Steam Deck OLED 512':                 'Steam Deck OLED 512GB',
    'Steam Deck LCD 512':                  'Steam Deck LCD 512GB',
    'Switch2 ブラックボルト':              'Nintendo Switch 2 ブラックボルト',
    'Switch2 ホワイトフレア':              'Nintendo Switch 2 ホワイトフレア',
}


def get_price_floor(name: str) -> int:
    """商品名から検索時の最低価格フィルターを返す（誤マッチ除外用）"""
    n = name.lower()
    if any(k in n for k in ['switch2 国内版', 'switch2 多言語', 'switch2 ブラック', 'switch2 ホワイト']):
        return 40000
    if 'マリカーセット' in n:
        return 50000
    if '有機' in n or 'oled' in n:
        return 30000
    if '新型' in n and 'switch' in n:
        return 25000
    if 'switch lite' in n:
        return 15000
    if name == 'PS5 ディスクドライブ':   # アドオン（CFI-ZDD1J）
        return 8000
    if name in ('PS5', 'PS5デジタル', 'PlayStation5 Pro') or 'playstation5' in n:
        return 40000
    if 'xbox series x' in n and ('1tb' in n or name == 'Xbox X'):
        return 50000
    if 'xbox series s' in n or name in ('Xbox S', 'Xbox S 1TB ホワイト'):
        return 25000
    if 'meta quest 3s' in n:
        return 40000
    if 'meta quest 3' in n:
        return 50000
    if 'steam deck' in n:
        return 50000
    if 'vr2' in n:
        return 40000
    if 'portal' in n or 'リモートプレーヤー' in n:
        return 25000
    if 'dualsense' in n:
        return 6000
    if 'joy-con 2' in n and ('充電' in name or 'grip' in n):
        return 2000
    if 'joy-con 2' in n:
        return 4000
    if 'joy-con' in n:
        return 3000
    if 'proコン' in n or 'pro controller' in n:
        return 6000
    if 'alarmo' in n:
        return 5000
    if 'pokemon go plus' in n:
        return 5000
    if 'x100vi' in n:
        return 150000
    if 'g7x' in n or 'g7 x' in n:
        return 50000
    if 'sx740' in n:
        return 30000
    if 'ixy 650' in n:
        return 10000
    if 'ixy' in n:
        return 20000
    if 'mini evo' in n:
        return 15000
    if 'wide 400' in n:
        return 10000
    if 'sq1' in n:
        return 8000
    if 'mini 13' in n:
        return 5000
    if 'チェキフィルム' in n or ('instax' in n and 'フィルム' in n):
        return 500
    if 'tamagotchi paradise' in n:
        return 4000
    return 3000


def build_query(name: str) -> str:
    """商品名から検索クエリを生成"""
    if name in CUSTOM_QUERIES:
        return CUSTOM_QUERIES[name]

    q = name
    q = re.sub(r'^Switch2\b', 'Nintendo Switch 2', q)
    q = re.sub(r'^Switch Lite\b', 'Nintendo Switch Lite', q)
    q = re.sub(r'^Switch\b', 'Nintendo Switch', q)
    q = re.sub(r'^Joy-Con 2\b', 'Nintendo Joy-Con 2', q)
    q = re.sub(r'^Joy-Con\b', 'Nintendo Joy-Con', q)

    if re.search(r'G7[_ ]?X|SX740|IXY|PowerShot', q) and 'Canon' not in q:
        q = 'Canon ' + q
    if re.search(r'X100VI|instax|チェキ|WIDE 400|SQ1|mini (13|Evo)|チェキフィルム', q):
        if 'FUJIFILM' not in q and 'Fujifilm' not in q:
            q = 'FUJIFILM ' + q

    if re.search(r'Tamagotchi|たまごっち', q) and 'BANDAI' not in q:
        q = 'BANDAI ' + q

    q = q.replace('（新）', '').replace('（旧）', '').replace('（', ' ').replace('）', ' ')
    q = re.sub(r'\s+', ' ', q).strip()

    return q


async def sleep_human() -> None:
    """人間的なランダム待機（3〜6秒）"""
    await asyncio.sleep(random.uniform(3.0, 6.0))


# ════════════════════════════════════════════════════════════════════════
# Step A: 価格.com（メーカー希望小売価格）
# ════════════════════════════════════════════════════════════════════════

async def scrape_kakaku(page: Page, query: str, price_floor: int) -> tuple[int, str, str] | None:
    """
    価格.com でメーカー希望小売価格を取得。
    Returns: (price, product_url, matched_title) or None
    """
    try:
        search_url = (
            f'https://kakaku.com/search_results/'
            f'?query={query.replace(" ", "+")}'
            f'&min_Price={price_floor}'
        )
        await page.goto(search_url, wait_until='domcontentloaded', timeout=30_000)
        await sleep_human()

        # 最初の商品リンクを取得
        link = await page.query_selector(
            'a[href*="/item/"][href*="kakaku.com"], '
            '.p-item_main__itemName a, '
            '[class*="p-item"] a[href*="/item/"]'
        )
        if not link:
            return None

        href = await link.get_attribute('href') or ''
        prod_url = href if href.startswith('http') else f'https://kakaku.com{href}'
        # /spec/ や /review/ でなく /item/ ページにする
        prod_url = re.sub(r'/(spec|review|bbs|pricehistory)/$', '/', prod_url)

        title_el = await link.query_selector('span, p')
        title = ((await title_el.inner_text()) if title_el
                 else (await link.inner_text())).strip()[:80]

        await page.goto(prod_url, wait_until='domcontentloaded', timeout=30_000)
        await sleep_human()

        price = await page.evaluate(r"""(priceFloor) => {
            const toInt = s => parseInt(s.replace(/[^0-9]/g, ''), 10);

            // ── 1) メーカー希望小売価格 専用欄を探す ───────────────────
            const labels = [
                'メーカー希望小売価格',
                'メーカー希望価格',
                '希望小売価格',
                '定価',
            ];
            // dt/dd 構造
            for (const dt of document.querySelectorAll('dt, th, [class*="label"], [class*="Label"]')) {
                if (labels.some(l => dt.textContent.includes(l))) {
                    // 隣の dd / td / 兄弟要素から価格を取る
                    const next = dt.nextElementSibling
                              || dt.parentElement?.nextElementSibling;
                    if (next) {
                        const m = next.textContent.match(/([\d,]+)/);
                        if (m) {
                            const v = toInt(m[1]);
                            if (v >= priceFloor) return v;
                        }
                    }
                }
            }
            // テキスト全体からラベル付近の数字を探す
            const text = document.body.innerText;
            for (const label of labels) {
                const idx = text.indexOf(label);
                if (idx < 0) continue;
                const chunk = text.slice(idx, idx + 80);
                const m = chunk.match(/[¥￥]([\d,]+)/);
                if (m) {
                    const v = toInt(m[1]);
                    if (v >= priceFloor) return v;
                }
            }
            return null;
        }""", price_floor)

        if price:
            return (price, prod_url, title)

    except Exception as e:
        print(f'  価格.com エラー: {e}')
    return None


# ════════════════════════════════════════════════════════════════════════
# Step B: Amazon（参考価格のみ）
# ════════════════════════════════════════════════════════════════════════

async def scrape_amazon_msrp(page: Page, query: str, price_floor: int) -> tuple[int, str, str] | None:
    """
    Amazon で参考価格（取り消し線付き / 参考価格テキスト）のみを取得。
    通常の販売価格は使わない（第三者出品・在庫切れ価格を除外するため）。
    Returns: (price, product_url, matched_title) or None
    """
    try:
        k = query.replace(' ', '+')
        search_url = (
            f'https://www.amazon.co.jp/s?k={k}'
            f'&low-price={price_floor}'
            f'&language=ja_JP'
        )
        await page.goto(search_url, wait_until='domcontentloaded', timeout=30_000)
        await sleep_human()

        link = None
        for sel in [
            '[data-component-type="s-search-result"]:not([data-component-id*="Sponsored"]) h2 a.a-link-normal',
            '[data-component-type="s-search-result"] h2 a.a-link-normal',
            '[data-component-type="s-search-result"] a.a-link-normal[href*="/dp/"]',
        ]:
            link = await page.query_selector(sel)
            if link:
                break

        if not link:
            return None

        href = await link.get_attribute('href') or ''
        matched_title = ''
        for title_sel in ['h2 span', 'span.a-text-normal', 'span']:
            title_el = await link.query_selector(title_sel)
            if title_el:
                matched_title = (await title_el.inner_text()).strip()[:80]
                if matched_title:
                    break

        product_url = (
            'https://www.amazon.co.jp' + href if href.startswith('/') else href
        )
        product_url = re.sub(r'/ref=.*', '', product_url)

        await page.goto(product_url, wait_until='domcontentloaded', timeout=30_000)
        await sleep_human()

        price = await page.evaluate(r"""(priceFloor) => {
            const toInt = s => parseInt(s.replace(/[^0-9]/g, ''), 10);

            // 参考価格（取り消し線付き）のみ採用
            for (const sel of [
                '.a-price.a-text-price .a-offscreen',
                '.basisPrice .a-offscreen',
                '[data-a-strike="true"] .a-offscreen',
                '.a-text-strike .a-offscreen',
            ]) {
                const el = document.querySelector(sel);
                if (el) {
                    const m = el.textContent.match(/([\d,]+)/);
                    if (m && toInt(m[1]) >= priceFloor) return toInt(m[1]);
                }
            }

            // テキストから「参考価格」「定価」ラベル付近の数字
            const bodyText = document.body.innerText;
            for (const label of ['参考価格', '定価', 'メーカー希望小売価格']) {
                const idx = bodyText.indexOf(label);
                if (idx >= 0) {
                    const chunk = bodyText.slice(idx, idx + 60);
                    const m = chunk.match(/[¥￥\s]([\d,]+)/);
                    if (m && toInt(m[1]) >= priceFloor) return toInt(m[1]);
                }
            }

            return null;
        }""", price_floor)

        if price:
            return (price, product_url, matched_title)

    except Exception as e:
        print(f'  Amazon エラー: {e}')
    return None


# ════════════════════════════════════════════════════════════════════════
# メインのスクレイプ関数
# ════════════════════════════════════════════════════════════════════════

async def scrape_product(page: Page, name: str, query: str) -> dict:
    result = {
        'product_name': name,
        'msrp': '',
        'source_url': '',
        'matched_title': '',
    }
    price_floor = get_price_floor(name)

    # ── Step A: 価格.com（メーカー希望小売価格） ─────────────────────
    r = await scrape_kakaku(page, query, price_floor)
    if r:
        price, url, title = r
        result.update(msrp=price, source_url=url, matched_title=title)
        print(f'  OK {name}  →  ¥{price:,}  [{title[:50]}]  (via kakaku)')
        return result

    print(f'  ~ {name}: 価格.com NG → Amazon 参考価格を試行')

    # ── Step B: Amazon（参考価格のみ） ───────────────────────────────
    r = await scrape_amazon_msrp(page, query, price_floor)
    if r:
        price, url, title = r
        result.update(msrp=price, source_url=url, matched_title=title)
        print(f'  OK {name}  →  ¥{price:,}  [{title[:50]}]  (via amazon)')
        return result

    print(f'  -- {name}: 全ソースで価格取得できず')
    return result


# ════════════════════════════════════════════════════════════════════════
# CSV 読み書き
# ════════════════════════════════════════════════════════════════════════

MSRP_FIELDS = ['product_name', 'msrp', 'effective_date', 'source_url', 'matched_title']


def save_csv(rows: list[dict]) -> None:
    MSRP_FILE.parent.mkdir(parents=True, exist_ok=True)
    # effective_date が未設定の行には 2000-01-01 を補完
    for r in rows:
        r.setdefault('effective_date', '2000-01-01')
    with open(MSRP_FILE, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=MSRP_FIELDS, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def load_existing_msrp() -> dict[str, int]:
    """既存の msrp.csv から {product_name: msrp} を読み込む"""
    if not MSRP_FILE.exists():
        return {}
    with open(MSRP_FILE, newline='', encoding='utf-8') as f:
        return {
            row['product_name']: int(row['msrp'])
            for row in csv.DictReader(f)
            if row.get('msrp')
        }


# ════════════════════════════════════════════════════════════════════════
# エントリポイント
# ════════════════════════════════════════════════════════════════════════

async def main() -> None:
    all_targets = [
        p
        for cat, items in PRODUCTS.items()
        if cat not in SKIP_CATEGORIES
        for p in items
    ]

    # 既存CSVで「価格フロアを下回る＝誤マッチ」の商品のみ再スクレイプ
    existing = load_existing_msrp()
    targets = []
    skipped_ok = []
    for p in all_targets:
        name = p['name']
        floor = get_price_floor(name)
        if existing.get(name, 0) >= floor:
            skipped_ok.append(name)
        else:
            targets.append(p)

    skip_cat = sum(
        len(items) for cat, items in PRODUCTS.items() if cat in SKIP_CATEGORIES
    )

    print(f'対象: {len(targets)} 商品  /  取得済みスキップ: {len(skipped_ok)} 商品  /  カテゴリスキップ: {skip_cat} 商品')
    print(f'推定所要時間: 約 {len(targets) * 9 // 60} 分')
    print(f'出力先: {MSRP_FILE}')
    print()

    # 取得済みの正常データは引き継ぐ
    results: list[dict] = []
    if MSRP_FILE.exists():
        with open(MSRP_FILE, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                name = row['product_name']
                floor = get_price_floor(name)
                if int(row.get('msrp') or 0) >= floor:
                    results.append(row)

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
            name = product['name']
            query = build_query(name)
            print(f'[{i:3}/{len(targets)}] {name}  (検索: {query})')

            r = await scrape_product(page, name, query)
            results.append(r)

            # 20件ごとに中間保存
            if i % 20 == 0:
                save_csv(results)
                print(f'      ── 中間保存 ({i}/{len(targets)}) ──\n')

        await browser.close()

    save_csv(results)
    found = sum(1 for r in results if r['msrp'])
    print(f'\n完了: {found}/{len(results)} 件取得')
    print(f'確認: {MSRP_FILE}')
    print('matched_title 列で照合が正しいか確認し、誤りがあれば msrp 列を手動修正してください。')


if __name__ == '__main__':
    asyncio.run(main())
