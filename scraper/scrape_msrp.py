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


AMAZON_SELLER_ID = 'AN1VRQENFRJN5'  # Amazon.co.jp 自身の出品者ID


# ── メーカー/公式サイト判定 ───────────────────────────────────────────

def get_manufacturer_site(name: str) -> str | None:
    """
    商品名からフォールバック先サイト種別を返す。
    'nintendo' | 'sony' | 'yodobashi' | None
    """
    n = name.lower()
    if any(k in n for k in ['switch', 'joy-con', 'alarmo', 'pokemon go plus']):
        return 'nintendo'
    if any(k in n for k in [
        'ps5', 'playstation', 'dualsense', 'vr2', 'portal', 'リモートプレーヤー',
    ]):
        return 'sony'
    # カメラ・レンズ・チェキ・たまごっち・Xbox・Meta・Steam Deck → ヨドバシ
    return 'yodobashi'


# ── Step C: メーカー / ヨドバシ スクレイパー ─────────────────────────

async def _scrape_site_price(page: Page, url: str, selectors: list[str]) -> int | None:
    """指定URLを開き、セレクターリストから最初に見つかった整数価格を返す"""
    await page.goto(url, wait_until='domcontentloaded', timeout=30_000)
    await sleep_human()
    return await page.evaluate(r"""(selectors) => {
        const toInt = s => parseInt(s.replace(/[^0-9]/g, ''), 10);
        for (const sel of selectors) {
            for (const el of document.querySelectorAll(sel)) {
                const t = el.textContent || '';
                const m = t.match(/([\d,]+)/);
                if (m) {
                    const v = toInt(m[1]);
                    if (v > 1000) return v;
                }
            }
        }
        // 「税込」直前の ¥XX,XXX を広くスキャン
        const text = document.body.innerText;
        for (const label of ['（税込）', '(税込)', '税込']) {
            let pos = 0;
            while (true) {
                const idx = text.indexOf(label, pos);
                if (idx < 0) break;
                const chunk = text.slice(Math.max(0, idx - 40), idx + 2);
                const m = chunk.match(/[¥￥]([\d,]+)/);
                if (m) {
                    const v = toInt(m[1]);
                    if (v > 1000) return v;
                }
                pos = idx + 1;
            }
        }
        return null;
    }""", selectors)


async def scrape_nintendo_store(page: Page, query: str) -> tuple[int, str, str] | None:
    """Nintendo Store JP (store.nintendo.com/jp) から定価を取得"""
    try:
        search_url = (
            f'https://store.nintendo.com/jp/search'
            f'?q={query.replace(" ", "+")}'
        )
        await page.goto(search_url, wait_until='domcontentloaded', timeout=30_000)
        await sleep_human()

        link = await page.query_selector(
            'a[href*="/jp/product/"], '
            'a[href*="store.nintendo.com/jp/product/"], '
            '[data-testid="product-card"] a'
        )
        if not link:
            return None

        href = await link.get_attribute('href') or ''
        prod_url = href if href.startswith('http') else f'https://store.nintendo.com{href}'
        title_el = await link.query_selector('p, span, h2, h3')
        title = ((await title_el.inner_text()) if title_el else await link.inner_text() or '').strip()[:80]

        price = await _scrape_site_price(page, prod_url, [
            '[class*="price"]',
            '[class*="Price"]',
            '.nt-price',
            '.product-price',
        ])

        if price:
            return (price, prod_url, title)

    except Exception as e:
        print(f'  Nintendo Store エラー: {e}')
    return None


async def scrape_playstation_direct(page: Page, query: str) -> tuple[int, str, str] | None:
    """PlayStation Direct JP (direct.playstation.com/ja-jp) から定価を取得"""
    try:
        search_url = (
            f'https://direct.playstation.com/ja-jp/search'
            f'?searchStr={query.replace(" ", "+")}'
        )
        await page.goto(search_url, wait_until='domcontentloaded', timeout=30_000)
        await sleep_human()

        link = await page.query_selector(
            'a[href*="/ja-jp/buy-"], '
            '.product-card a, '
            '[class*="product"] a[href*="playstation"]'
        )
        if not link:
            return None

        href = await link.get_attribute('href') or ''
        prod_url = href if href.startswith('http') else f'https://direct.playstation.com{href}'
        title_el = await link.query_selector('h3, h2, [class*="title"], [class*="name"]')
        title = ((await title_el.inner_text()) if title_el else await link.inner_text() or '').strip()[:80]

        price = await _scrape_site_price(page, prod_url, [
            '[class*="price"]',
            '[class*="Price"]',
            '.product-price',
            '[itemprop="price"]',
        ])

        if price:
            return (price, prod_url, title)

    except Exception as e:
        print(f'  PlayStation Direct エラー: {e}')
    return None


async def scrape_yodobashi(page: Page, query: str) -> tuple[int, str, str] | None:
    """ヨドバシ.com で新品価格を取得（カメラ・Xbox・Meta・Steam Deck 等）"""
    try:
        search_url = (
            f'https://www.yodobashi.com/'
            f'?word={query.replace(" ", "+")}&num=10&searchtype=keyword'
        )
        await page.goto(search_url, wait_until='domcontentloaded', timeout=30_000)
        await sleep_human()

        # 最初の商品リンクを取得
        link = await page.query_selector(
            '.js_searchItemBox a.js_productDetailLink, '
            '.productName a, '
            '[class*="product"] a[href*="/product/"]'
        )
        if not link:
            return None

        href = await link.get_attribute('href') or ''
        prod_url = href if href.startswith('http') else f'https://www.yodobashi.com{href}'
        title = (await link.inner_text()).strip()[:80]

        price = await _scrape_site_price(page, prod_url, [
            '.priceSaleNumFig',
            '.priceSale .priceFig',
            '.priceFig',
            '[class*="saleFig"]',
            '.selling_price',
            '[itemprop="price"]',
        ])

        if price:
            return (price, prod_url, title)

    except Exception as e:
        print(f'  ヨドバシ エラー: {e}')
    return None


async def scrape_manufacturer_fallback(
    page: Page, name: str, query: str
) -> tuple[int, str, str] | None:
    """
    Step C: Amazon で価格が取れなかった場合にメーカー/ヨドバシで再検索。
    Returns: (price, url, matched_title) or None
    """
    site = get_manufacturer_site(name)
    if site is None:
        return None

    print(f'  ~ {name}: Step C → {site} で検索中...')

    if site == 'nintendo':
        r = await scrape_nintendo_store(page, query)
        if r:
            return r
        # Nintendo Store で見つからなければヨドバシへ
        print(f'  ~ {name}: Nintendo Store NG → ヨドバシへ')
        return await scrape_yodobashi(page, query)

    elif site == 'sony':
        r = await scrape_playstation_direct(page, query)
        if r:
            return r
        print(f'  ~ {name}: PlayStation Direct NG → ヨドバシへ')
        return await scrape_yodobashi(page, query)

    else:
        return await scrape_yodobashi(page, query)


async def get_price_on_product_page(page: Page, require_amazon_seller: bool = False) -> int | None:
    """
    商品ページから参考価格 → 販売価格の順で取得。

    require_amazon_seller=True のとき:
      - 参考価格（メーカー希望小売価格）は常に取得する（出品者不問）
      - fallback の販売価格は Amazon.co.jp が出品者の場合のみ使用する
        （第三者出品者の価格は市場価格でありMSRPではないため除外）
    """
    return await page.evaluate(r"""(requireAmazonSeller) => {
        const toInt = s => parseInt(s.replace(/[^0-9]/g, ''), 10);

        // 1) 参考価格（取り消し線付き）を探す ── 出品者に関わらず正しいMSRP
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

        // 2) テキストから「参考価格」「定価」の近くの数字を探す ── 同上
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
        //    require_amazon_seller=true のとき Amazon.co.jp が出品者でなければスキップ
        if (requireAmazonSeller) {
            const isAmazonSeller =
                bodyText.includes('Amazon.co.jp が販売') ||
                bodyText.includes('Amazon.co.jp が出荷') ||
                bodyText.includes('出荷元 Amazon.co.jp') ||
                !!document.querySelector('#merchant-info a[href*="AN1VRQENFRJN5"]') ||
                !!document.querySelector('#tabular-buybox a[href*="AN1VRQENFRJN5"]');
            if (!isAmazonSeller) return null;
        }

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
    }""", require_amazon_seller)


async def scrape_product(page: Page, name: str, query: str) -> dict:
    result = {
        'product_name': name,
        'msrp': '',
        'source_url': '',
        'matched_title': '',
    }

    try:
        price_floor = get_price_floor(name)
        k = query.replace(' ', '+')

        # ── 検索戦略 ────────────────────────────────────────────────────
        # Step A: Amazon.co.jp が出品者 (emi=) + 価格下限フィルター
        # Step B: emi フィルターなし（品切れ等で Step A で結果なしの場合）
        #         ただしこのとき fallback 販売価格は使わず 参考価格のみ採用
        search_variants = [
            (
                f'https://www.amazon.co.jp/s?k={k}'
                f'&low-price={price_floor}'
                f'&emi={AMAZON_SELLER_ID}'   # Amazon.co.jp が販売・出荷
                f'&language=ja_JP',
                True,   # require_amazon_seller
            ),
            (
                f'https://www.amazon.co.jp/s?k={k}'
                f'&low-price={price_floor}'
                f'&language=ja_JP',
                False,  # 第三者出品者も含む → fallback 価格は不採用
            ),
        ]

        link_el = None
        require_amazon_seller = True

        for search_url, req_seller in search_variants:
            await page.goto(search_url, wait_until='domcontentloaded', timeout=30_000)
            await sleep_human()

            for sel in [
                '[data-component-type="s-search-result"]:not([data-component-id*="Sponsored"]) h2 a.a-link-normal',
                '[data-component-type="s-search-result"] h2 a.a-link-normal',
                '[data-component-type="s-search-result"] a.a-link-normal[href*="/dp/"]',
            ]:
                link_el = await page.query_selector(sel)
                if link_el:
                    break

            if link_el:
                require_amazon_seller = req_seller
                if not req_seller:
                    print(f'  ~ {name}: Amazon出品なし → 参考価格のみ取得')
                break
        # ────────────────────────────────────────────────────────────────

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

        price = await get_price_on_product_page(page, require_amazon_seller=require_amazon_seller)

        if price:
            result['msrp'] = price
            print(f'  OK {name}  →  ¥{price:,}  [{matched_title[:50]}]')
        else:
            print(f'  -- {name}: Amazon 価格取得できず  [{matched_title[:50]}]')

    except Exception as e:
        print(f'  NG {name}: {e}')

    # ── Step C: Amazon で取れなければメーカー / ヨドバシへ ────────────
    if not result['msrp']:
        fallback = await scrape_manufacturer_fallback(page, name, query)
        if fallback:
            price_c, url_c, title_c = fallback
            result['msrp'] = price_c
            result['source_url'] = url_c
            result['matched_title'] = title_c
            site_c = get_manufacturer_site(name) or 'yodobashi'
            print(f'  OK {name}  →  ¥{price_c:,}  [{title_c[:50]}]  (via {site_c})')
        else:
            print(f'  -- {name}: 全ソースで価格取得できず')

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
