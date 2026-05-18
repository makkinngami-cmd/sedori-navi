#!/usr/bin/env python3
"""
定価スクレイパー（一回限り実行）
Amazon.co.jp から各商品の参考価格（定価）を取得する

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
    'Switch2 国内版マリカーセット':         'Nintendo Switch 2 マリオカートワールド セット',
    'Switch2 国内版':                      'Nintendo Switch 2 本体 国内版',
    'Switch2 多言語版':                    'Nintendo Switch 2 本体 多言語版',
    'Switch2 Proコン':                     'Nintendo Switch 2 Proコントローラー',
    'Switch 有機白':                       'Nintendo Switch 有機ELモデル ホワイト',
    'Switch 有機ネオン':                    'Nintendo Switch 有機ELモデル ネオン',
    'Switch 新型ネオン':                    'Nintendo Switch 本体 ネオンブルー ネオンレッド',
    'Switch 新型グレー':                    'Nintendo Switch 本体 グレー',
    'Switch Liteグレー':                   'Nintendo Switch Lite グレー',
    'Switch Liteブルー':                   'Nintendo Switch Lite ブルー',
    'Switch Liteコーラル':                 'Nintendo Switch Lite コーラル',
    'Switch Liteターコイズ':               'Nintendo Switch Lite ターコイズ',
    'Switch Liteイエロー':                 'Nintendo Switch Lite イエロー',
    'Switch Proコン':                      'Nintendo Switch Proコントローラー',
    'Switch Proコン ゼルダ':               'Nintendo Switch Proコントローラー ゼルダの伝説 知恵のかりもの',
    'Switch Proコン スプラ3':              'Nintendo Switch Proコントローラー スプラトゥーン3',
    'Alarmo':                              'Nintendo サウンドクロック Alarmo',
    'Pokemon GO Plus+':                    'Pokemon GO Plus+',
    'PS5デジタル':                         'PlayStation 5 デジタル・エディション',
    'PS5':                                 'PlayStation 5 本体',
    'PlayStation5 Pro':                    'PlayStation 5 Pro',
    'リモートプレーヤー':                  'PlayStation Portal リモートプレーヤー',
    'PlayStation VR2':                     'PlayStation VR2',
    'PlayStation VR2 Horizon同梱版':       'PlayStation VR2 Horizon Call of the Mountain',
    'Xbox X 1TB ホワイト':                 'Xbox Series X 1TB ホワイト',
    'Xbox S 1TB ホワイト':                 'Xbox Series S 1TB ホワイト',
    'Xbox X':                              'Xbox Series X',
    'Xbox S':                              'Xbox Series S',
    'Meta Quest 3 512':                    'Meta Quest 3 512GB',
    'Meta Quest 3 128':                    'Meta Quest 3 128GB',
    'Steam Deck OLED 1TB':                 'Steam Deck OLED 1TB',
    'Steam Deck OLED 512':                 'Steam Deck OLED 512GB',
    'Steam Deck LCD 512':                  'Steam Deck LCD 512GB',
    'Switch2 ブラックボルト':              'Nintendo Switch 2 ブラックボルト',
    'Switch2 ホワイトフレア':              'Nintendo Switch 2 ホワイトフレア',
}


def get_price_floor(name: str) -> int:
    """商品名から検索時の最低価格フィルターを返す（アクセサリ除外用）"""
    n = name.lower()
    # ゲーム機本体
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
    # PS5本体のみ高フロア、ゲームソフト(PS5 Split Fiction等)は除外
    if name in ('PS5', 'PS5デジタル', 'PlayStation5 Pro', 'PS5 ディスクドライブ') or 'playstation5' in n:
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
    # コントローラー・周辺機器
    if 'dualsense' in n:
        return 6000
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
    # カメラ
    if 'x100vi' in n:
        return 150000
    if 'g7x' in n or 'g7 x' in n:
        return 50000
    if 'sx740' in n:
        return 30000
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
    if 'チェキフィルム' in n:
        return 500
    # たまごっち
    if 'tamagotchi paradise' in n:
        return 4000
    # ゲームソフト
    return 3000


def build_query(name: str) -> str:
    """商品名から Amazon 検索クエリを生成"""
    if name in CUSTOM_QUERIES:
        return CUSTOM_QUERIES[name]

    q = name

    # ゲーム機器のブランド付加
    q = re.sub(r'^Switch2\b', 'Nintendo Switch 2', q)
    q = re.sub(r'^Switch Lite\b', 'Nintendo Switch Lite', q)
    q = re.sub(r'^Switch\b', 'Nintendo Switch', q)
    q = re.sub(r'^Joy-Con 2\b', 'Nintendo Joy-Con 2', q)
    q = re.sub(r'^Joy-Con\b', 'Nintendo Joy-Con', q)

    # カメラ系ブランド付加
    if re.search(r'G7[_ ]?X|SX740|IXY|PowerShot', q) and 'Canon' not in q:
        q = 'Canon ' + q
    if re.search(r'X100VI|instax|チェキ|WIDE 400|SQ1|mini (13|Evo)|チェキフィルム', q):
        if 'FUJIFILM' not in q and 'Fujifilm' not in q:
            q = 'FUJIFILM ' + q

    # たまごっち
    if re.search(r'Tamagotchi|たまごっち', q) and 'BANDAI' not in q:
        q = 'BANDAI ' + q

    # 表記ゆれ除去
    q = q.replace('（新）', '').replace('（旧）', '').replace('（', ' ').replace('）', ' ')
    q = re.sub(r'\s+', ' ', q).strip()

    return q


async def sleep_human() -> None:
    """人間的なランダム待機（3〜6秒）"""
    await asyncio.sleep(random.uniform(3.0, 6.0))


async def get_price_on_product_page(page: Page) -> int | None:
    """商品ページから参考価格 → 販売価格の順で取得"""
    return await page.evaluate(r"""() => {
        const toInt = s => parseInt(s.replace(/[^0-9]/g, ''), 10);

        // 1) 参考価格（取り消し線）を探す
        for (const sel of [
            '.a-price.a-text-price .a-offscreen',
            '.basisPrice .a-offscreen',
            '[data-a-strike="true"] .a-offscreen',
            '.a-text-strike .a-offscreen',
        ]) {
            const el = document.querySelector(sel);
            if (el) {
                const m = el.textContent.match(/([\d,]+)/);
                if (m && toInt(m[1]) > 100) return toInt(m[1]);
            }
        }

        // 2) テキストから「参考価格」「定価」の近くの数字を探す
        const bodyText = document.body.innerText;
        for (const label of ['参考価格', '定価', 'メーカー希望小売価格']) {
            const idx = bodyText.indexOf(label);
            if (idx >= 0) {
                const chunk = bodyText.slice(idx, idx + 60);
                const m = chunk.match(/[¥￥\s]([\d,]+)/);
                if (m && toInt(m[1]) > 100) return toInt(m[1]);
            }
        }

        // 3) fallback: 通常販売価格
        for (const sel of [
            '#corePriceDisplay_desktop_feature_div .a-offscreen',
            '#corePrice_feature_div .a-offscreen',
            '#priceblock_ourprice',
            '#priceblock_dealprice',
            '#price_inside_buybox',
            '.a-price-whole',
        ]) {
            const el = document.querySelector(sel);
            if (el) {
                const m = el.textContent.match(/([\d,]+)/);
                if (m && toInt(m[1]) > 100) return toInt(m[1]);
            }
        }

        return null;
    }""")


async def scrape_product(page: Page, name: str, query: str) -> dict:
    result = {
        'product_name': name,
        'msrp': '',
        'source_url': '',
        'matched_title': '',
    }

    try:
        # Amazon 検索（low-price フィルターでアクセサリを除外）
        price_floor = get_price_floor(name)
        search_url = (
            f'https://www.amazon.co.jp/s?k={query.replace(" ", "+")}'
            f'&low-price={price_floor}&language=ja_JP'
        )
        await page.goto(search_url, wait_until='domcontentloaded', timeout=30_000)
        await sleep_human()

        # 最初の商品リンクを取得（スポンサー広告をスキップ）
        link_el = None
        for sel in [
            '[data-component-type="s-search-result"]:not([data-component-id*="Sponsored"]) h2 a.a-link-normal',
            '[data-component-type="s-search-result"] h2 a.a-link-normal',
            '[data-component-type="s-search-result"] a.a-link-normal[href*="/dp/"]',
        ]:
            link_el = await page.query_selector(sel)
            if link_el:
                break

        if not link_el:
            print(f'  -- {name}: 検索結果なし')
            return result

        href = await link_el.get_attribute('href') or ''
        # タイトル取得（複数パターンを試す）
        matched_title = ''
        for title_sel in ['h2 span', 'span.a-text-normal', 'span']:
            title_el = await link_el.query_selector(title_sel)
            if title_el:
                matched_title = (await title_el.inner_text()).strip()[:80]
                if matched_title:
                    break

        product_url = (
            'https://www.amazon.co.jp' + href if href.startswith('/') else href
        )
        product_url = re.sub(r'/ref=.*', '', product_url)

        result['source_url'] = product_url
        result['matched_title'] = matched_title

        # 商品ページへ
        await page.goto(product_url, wait_until='domcontentloaded', timeout=30_000)
        await sleep_human()

        price = await get_price_on_product_page(page)

        if price:
            result['msrp'] = price
            print(f'  OK {name}  →  ¥{price:,}  [{matched_title[:50]}]')
        else:
            print(f'  -- {name}: 価格取得できず  [{matched_title[:50]}]')

    except Exception as e:
        print(f'  NG {name}: {e}')

    return result


def save_csv(rows: list[dict]) -> None:
    MSRP_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MSRP_FILE, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(
            f, fieldnames=['product_name', 'msrp', 'source_url', 'matched_title']
        )
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
        existing_price = existing.get(name, 0)
        if existing_price >= floor:
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
                    results.append(row)  # 正常データは引き継ぎ

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
