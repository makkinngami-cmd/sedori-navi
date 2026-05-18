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
import random
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright, Page

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
        # Amazon 検索
        search_url = (
            f'https://www.amazon.co.jp/s?k={query.replace(" ", "+")}&language=ja_JP'
        )
        await page.goto(search_url, wait_until='domcontentloaded', timeout=30_000)
        await sleep_human()

        # 最初の商品リンクを取得
        link_el = await page.query_selector(
            '[data-component-type="s-search-result"] h2 a.a-link-normal'
        )
        if not link_el:
            link_el = await page.query_selector(
                '[data-component-type="s-search-result"] a.a-link-normal[href*="/dp/"]'
            )

        if not link_el:
            print(f'  -- {name}: 検索結果なし')
            return result

        href = await link_el.get_attribute('href') or ''
        title_el = await link_el.query_selector('span')
        matched_title = (
            (await title_el.inner_text()).strip()[:80] if title_el else ''
        )

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


async def main() -> None:
    targets = [
        p
        for cat, items in PRODUCTS.items()
        if cat not in SKIP_CATEGORIES
        for p in items
    ]

    skipped = sum(
        len(items) for cat, items in PRODUCTS.items() if cat in SKIP_CATEGORIES
    )

    print(f'対象: {len(targets)} 商品  /  スキップ: {skipped} 商品（ポケカ・ワンピ）')
    print(f'推定所要時間: 約 {len(targets) * 9 // 60} 分')
    print(f'出力先: {MSRP_FILE}')
    print()

    results: list[dict] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)  # 動作確認のため表示モード
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
