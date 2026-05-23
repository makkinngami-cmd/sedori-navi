#!/usr/bin/env python3
"""
ヤフオク落札価格スクレイパー（毎日実行・同日重複スキップ）
落札済み新品商品の過去7日分から 最安・中央値・最高 を取得し prices.csv に追記する

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
from statistics import mean, median

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

BASE_DIR      = Path(__file__).parent.parent
DATA_FILE     = BASE_DIR / 'data' / 'prices.csv'
SCRAPE_MARKER = BASE_DIR / 'data' / 'last_scrape_yahoo.txt'
CSV_HEADERS   = ['date', 'product_name', 'store', 'price', 'jan', 'url']

SKIP_CATEGORIES = {'ポケカ', 'ワンピ'}

# 商品ごとにヤフオク検索クエリを上書き
CUSTOM_QUERIES: dict[str, str] = {
    'Switch2 国内版マリカーセット': 'Nintendo Switch 2 マリオカートワールド セット',
    'Switch2 国内版':              'Nintendo Switch 2 本体 国内版',
    'Switch2 多言語版':            'Nintendo Switch 2 本体 多言語版',
    'Switch2 Proコン':             'Nintendo Switch 2 Proコントローラー',
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
    'PlayStation5 Pro':            'CFI-7000B01',
    'PlayStation5':                'CFI-2000A01',
    'PlayStation5 デジタルエディション': 'CFI-2000B01',
    'PlayStation5 デジタルエディション 日本語専用': 'CFI-2200B01',
    'PlayStation5 デジタル ダブルパック 日本語専用': 'CFIJ-10032',
    'PlayStation5 Ghost of Yotei リミテッドエディション': 'CFIJ-10029',
    'PlayStation5 ディスクドライブ': 'CFI-ZDD1J',
    'リモートプレーヤー':          'PlayStation Portal リモートプレーヤー',
    'PlayStation VR2':             'PlayStation VR2',
    'PlayStation VR2 Horizon同梱版': 'PlayStation VR2 Horizon Call of the Mountain',
    'Xbox X 1TB ホワイト':         'Xbox Series X 1TB ホワイト',
    'Xbox S 1TB ホワイト':         'Xbox Series S 1TB ホワイト',
    'Xbox X':                      'Xbox Series X',
    'Xbox S':                      'Xbox Series S',
    'Meta Quest 3 512':            'Meta Quest 3 512GB',
    'Meta Quest 3 128':            'Meta Quest 3 128GB',
    'Steam Deck 有機EL 1TB':        'Steam Deck OLED 1TB',
    'Steam Deck 有機EL 512GB':      'Steam Deck OLED 512GB',
    # iPhone 17 Pro Max
    'iPhone 17 Pro Max 256GB シルバー':         'iPhone 17 Pro Max 256GB シルバー SIMフリー',
    'iPhone 17 Pro Max 256GB ディープブルー':   'iPhone 17 Pro Max 256GB ディープブルー SIMフリー',
    'iPhone 17 Pro Max 256GB コズミックオレンジ':'iPhone 17 Pro Max 256GB コズミックオレンジ SIMフリー',
    'iPhone 17 Pro Max 512GB シルバー':         'iPhone 17 Pro Max 512GB シルバー SIMフリー',
    'iPhone 17 Pro Max 512GB ディープブルー':   'iPhone 17 Pro Max 512GB ディープブルー SIMフリー',
    'iPhone 17 Pro Max 512GB コズミックオレンジ':'iPhone 17 Pro Max 512GB コズミックオレンジ SIMフリー',
    'iPhone 17 Pro Max 1TB シルバー':           'iPhone 17 Pro Max 1TB シルバー SIMフリー',
    'iPhone 17 Pro Max 1TB ディープブルー':     'iPhone 17 Pro Max 1TB ディープブルー SIMフリー',
    'iPhone 17 Pro Max 1TB コズミックオレンジ': 'iPhone 17 Pro Max 1TB コズミックオレンジ SIMフリー',
    'iPhone 17 Pro Max 2TB シルバー':           'iPhone 17 Pro Max 2TB シルバー SIMフリー',
    'iPhone 17 Pro Max 2TB ディープブルー':     'iPhone 17 Pro Max 2TB ディープブルー SIMフリー',
    'iPhone 17 Pro Max 2TB コズミックオレンジ': 'iPhone 17 Pro Max 2TB コズミックオレンジ SIMフリー',
    # iPhone 17 Pro
    'iPhone 17 Pro 256GB シルバー':             'iPhone 17 Pro 256GB シルバー SIMフリー',
    'iPhone 17 Pro 256GB ディープブルー':       'iPhone 17 Pro 256GB ディープブルー SIMフリー',
    'iPhone 17 Pro 256GB コズミックオレンジ':   'iPhone 17 Pro 256GB コズミックオレンジ SIMフリー',
    'iPhone 17 Pro 512GB シルバー':             'iPhone 17 Pro 512GB シルバー SIMフリー',
    'iPhone 17 Pro 512GB ディープブルー':       'iPhone 17 Pro 512GB ディープブルー SIMフリー',
    'iPhone 17 Pro 512GB コズミックオレンジ':   'iPhone 17 Pro 512GB コズミックオレンジ SIMフリー',
    'iPhone 17 Pro 1TB シルバー':               'iPhone 17 Pro 1TB シルバー SIMフリー',
    'iPhone 17 Pro 1TB ディープブルー':         'iPhone 17 Pro 1TB ディープブルー SIMフリー',
    'iPhone 17 Pro 1TB コズミックオレンジ':     'iPhone 17 Pro 1TB コズミックオレンジ SIMフリー',
}

# 商品ごとの価格上限（これを超えたら本体込みバンドルと判断）
PRICE_CAPS: dict[str, int] = {
    'PlayStation5 ディスクドライブ': 25000,  # MSRP ¥11,980
    'リモートプレーヤー':            50000,  # MSRP ¥29,980
    'PlayStation VR2':              100000,  # MSRP ¥74,980
}

# 商品ごとの価格下限（ヤフオク検索の min= パラメータに渡す）
# カメラ系は「互換バッテリー」「レンズキャップ」等のアクセサリーが
# 商品名を含んで出品されるため、現実的な最低価格を設定して除外する
PRICE_FLOORS: dict[str, int] = {
    'G7 X Mark II':                    8000,
    'G7 X Mark III シルバー':          8000,
    'G7 X Mark III ブラック':          8000,
    'G7X Mark III 30th Anniversary':  30000,
    'PowerShot G1 X Mark III':         8000,
    'PowerShot V10':                   8000,
    'PowerShot V1':                    8000,
    'IXY 650 シルバー':                5000,
    'IXY 650 ブラック':                5000,
    'IXY 650 m シルバー':              5000,
    'IXY 650 m ブラック':              5000,
    'SX740 シルバー':                  8000,
    'SX740 ブラック':                  8000,
    'SX70':                            5000,
    'X100VI シルバー（新）':          50000,
    'X100VI ブラック（新）':          50000,
    'X100VI シルバー（旧）':          50000,
    'X100VI ブラック（旧）':          50000,
    'X-T30 レンズキット':             15000,
    'LUMIX DC-TZ99 ブラック':         10000,
    'LUMIX DC-TZ99 ホワイト':         10000,
    'RICOH GR IV Monochrome':         50000,
    'RICOH GR IV':                    50000,
    'RICOH GR IIIx Urban Edition':    30000,
    'RICOH GR III Diary Edition':     30000,
    'RICOH GR IIIx':                  30000,
    'RICOH GR III':                   30000,
    'Nikon Z50II ダブルズームキット': 30000,
    'Nikon Z50II 18-140 VRキット':    25000,
    'Nikon Z50II 16-50 VRキット':     20000,
    'Nikon Z50II ボディ':             20000,
    'OM SYSTEM PEN E-P7':             15000,
    # iPhone 17 Pro Max
    'iPhone 17 Pro Max 256GB シルバー':          160000,
    'iPhone 17 Pro Max 256GB ディープブルー':    160000,
    'iPhone 17 Pro Max 256GB コズミックオレンジ':160000,
    'iPhone 17 Pro Max 512GB シルバー':          180000,
    'iPhone 17 Pro Max 512GB ディープブルー':    180000,
    'iPhone 17 Pro Max 512GB コズミックオレンジ':180000,
    'iPhone 17 Pro Max 1TB シルバー':            215000,
    'iPhone 17 Pro Max 1TB ディープブルー':      215000,
    'iPhone 17 Pro Max 1TB コズミックオレンジ':  215000,
    'iPhone 17 Pro Max 2TB シルバー':            250000,
    'iPhone 17 Pro Max 2TB ディープブルー':      250000,
    'iPhone 17 Pro Max 2TB コズミックオレンジ':  250000,
    # iPhone 17 Pro
    'iPhone 17 Pro 256GB シルバー':              140000,
    'iPhone 17 Pro 256GB ディープブルー':        140000,
    'iPhone 17 Pro 256GB コズミックオレンジ':    140000,
    'iPhone 17 Pro 512GB シルバー':              160000,
    'iPhone 17 Pro 512GB ディープブルー':        160000,
    'iPhone 17 Pro 512GB コズミックオレンジ':    160000,
    'iPhone 17 Pro 1TB シルバー':                195000,
    'iPhone 17 Pro 1TB ディープブルー':          195000,
    'iPhone 17 Pro 1TB コズミックオレンジ':      195000,
}

# アクセサリー出品の除外ワード
# （カメラ等で本体名を「対応機種」として記載した周辺機器が引っかかる対策）
ACCESSORY_WORDS = [
    'レンズキャップ', '前キャップ', 'レンズ前キャップ',
    '互換バッテリー', '互換充電器', '互換品',
    'ストラップ', 'ネックストラップ', 'ハンドストラップ',
    'フィルター', 'PLフィルター', 'UVフィルター', 'NDフィルター',
    'レンズフード', 'レンズ フード',
    '液晶保護フィルム', '液晶保護シート', 'スクリーン保護',
    'シリコンカバー', 'シリコンケース',
]


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
    # "終了" / 時刻部分を除去: "5/18 22:58終了" → "5/18"
    s = s.replace('終了', '').strip()
    s = re.sub(r'\s+\d{1,2}:\d{2}.*$', '', s).strip()

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

    # "M/D" or "M/DD"（年なし → 今年、ただし未来なら昨年）
    m = re.match(r'^(\d{1,2})/(\d{1,2})$', s)
    if m:
        mo, da = int(m.group(1)), int(m.group(2))
        yr = now.year
        if (mo, da) > (now.month, now.day):
            yr -= 1
        return f'{yr}-{mo:02d}-{da:02d}'

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
        // a[href*="/auction/"] を持つ li が商品カード
        const cards = Array.from(document.querySelectorAll('li'))
            .filter(li => li.querySelector('a[href*="/auction/"]'));

        for (const card of cards) {
            // タイトル: クラスなし p（最初に見つかったもの）→ h3 → h2 の順
            let title = '';
            for (const sel of ['p', 'h3', 'h2']) {
                const el = card.querySelector(sel);
                if (el && el.textContent.trim().length > 5) {
                    title = el.textContent.trim().replace(/\s+/g, ' ');
                    break;
                }
            }

            // 価格: "落札" ラベルの次の span → フォールバックで数字+"円" span
            let price = 0;
            const spans = Array.from(card.querySelectorAll('span'));
            for (let i = 0; i < spans.length; i++) {
                if (spans[i].textContent.trim() === '落札' && spans[i + 1]) {
                    const m = spans[i + 1].textContent.match(/[\d,]+/);
                    if (m) { price = parseInt(m[0].replace(/,/g, ''), 10); break; }
                }
            }
            if (!price) {
                for (const sp of spans) {
                    const m = sp.textContent.match(/^([\d,]+)円$/);
                    if (m) { price = parseInt(m[1].replace(/,/g, ''), 10); break; }
                }
            }

            // 日付: "終了" を含む span（例: "5/18 22:58終了"）
            let dateStr = '';
            for (const sp of spans) {
                const t = sp.textContent.trim();
                if (t.includes('終了') && /\d/.test(t)) {
                    dateStr = t;
                    break;
                }
            }
            // time[datetime] があればそちらを優先
            const timeEl = card.querySelector('time[datetime]');
            if (timeEl) dateStr = timeEl.getAttribute('datetime');

            // URL
            const linkEl = card.querySelector('a[href*="/auction/"]');
            const href = linkEl ? linkEl.href : '';

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
    max_price: int = 0,
) -> list[dict]:
    """
    1商品分のヤフオク落札データを取得し、最安・平均・最高をまとめて返す。
    max_price: 0 なら無制限。アクセサリー類の本体込みバンドル除外に使う。
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

    # バンドル・セット売りを除外（本体単体価格のみ採用）
    BUNDLE_WORDS = [
        'まとめ', 'セット売り', '同梱版', 'ソフト付', 'ゲーム付',
        '付属品あり', '本体セット', '本体+', '本体＋', '+コントローラー',
        '＋コントローラー', 'おまけ付', '本付き', '本付]', '本付 ',
        'コントローラー付', 'ゲームセット', 'ソフトセット', 'セット品',
        'レンズ付', 'レンズセット',
        '充電器付', 'ケース付', 'カバー付',
        'おまけ',
    ]
    def is_bundle(title: str) -> bool:
        t = title.replace('　', ' ')
        if any(w in t for w in BUNDLE_WORDS):
            return True
        if re.search(r'(ソフト|ゲーム)\d+本', t):
            return True
        return False

    # 状態不良品を除外（安値方向の外れ値対策）
    BAD_CONDITION_WORDS = [
        'ジャンク', '動作未確認', '難あり', '難有り', '訳あり', '訳有り',
        '破損', '欠品', '部品取り', '動作不良', '水没', '要修理', 'ノークレーム',
    ]
    def is_bad_condition(title: str) -> bool:
        return any(w in title for w in BAD_CONDITION_WORDS)

    def is_accessory(title: str) -> bool:
        return any(w in title for w in ACCESSORY_WORDS)

    matched = [
        it for it in items
        if matches(it['title'])
        and not is_bundle(it['title'])
        and not is_bad_condition(it['title'])
        and not is_accessory(it['title'])
        and (max_price == 0 or it['price'] <= max_price)
    ]
    if not matched:
        logger.info(f'  -- {name}: マッチする落札なし ({len(items)} 件中)')
        return []

    prices = [it['price'] for it in matched]

    # 外れ値除去（3件以上の場合）: 中央値の15%未満 or 400%超は除外
    if len(prices) >= 3:
        med = median(prices)
        prices = [p for p in prices if med * 0.15 <= p <= med * 4.0] or prices

    lo  = min(prices)
    hi  = max(prices)
    med = round(median(prices))
    url = matched[0]['url']  # 代表URL（最初にマッチしたもの）

    logger.info(
        f'  OK {name}: {len(matched)} 件 最安¥{lo:,} 中央値¥{med:,} 最高¥{hi:,}'
    )

    return [
        {'date': TODAY, 'product_name': name, 'store': 'ヤフオク 最安', 'price': lo,  'jan': '', 'url': url},
        {'date': TODAY, 'product_name': name, 'store': 'ヤフオク 中央値', 'price': med, 'jan': '', 'url': url},
        {'date': TODAY, 'product_name': name, 'store': 'ヤフオク 最高', 'price': hi,  'jan': '', 'url': url},
    ]


# ── CSV 書き込み ──────────────────────────────────────────────────────

def save_to_csv(records: list[dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_header = not DATA_FILE.exists() or DATA_FILE.stat().st_size == 0

    # 価格変化があった商品のみ追記
    last_price: dict[tuple, str] = {}
    if DATA_FILE.exists():
        with open(DATA_FILE, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                last_price[(row['product_name'], row['store'])] = row['price']

    new_records = [
        r for r in records
        if last_price.get((r['product_name'], r['store'])) != str(r['price'])
    ]

    if not new_records:
        logger.info('価格変化なし — 追記スキップ')
        return

    with open(DATA_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if write_header:
            writer.writeheader()
        writer.writerows(new_records)

    logger.info(f'CSV に {len(new_records)} 件追記（価格変化あり）')


# ── エントリポイント ──────────────────────────────────────────────────

def _already_scraped_today() -> bool:
    """マーカーファイルで今日実行済みか判定"""
    return SCRAPE_MARKER.exists() and SCRAPE_MARKER.read_text(encoding='utf-8').strip() == TODAY

def _mark_scraped_today() -> None:
    SCRAPE_MARKER.write_text(TODAY, encoding='utf-8')


async def main() -> None:
    logger.info(f'=== ヤフオク落札価格収集開始 {TODAY} (過去7日: {CUTOFF}〜) ===')

    if _already_scraped_today():
        logger.info('今日分データ取得済み — スキップ')
        return

    targets = [
        p for p in ALL_PRODUCTS
        if p.get('category') not in SKIP_CATEGORIES
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

            records = await scrape_product_yahoo(
                page, name, query, keywords,
                min_price=PRICE_FLOORS.get(name, 0),
                max_price=PRICE_CAPS.get(name, 0),
            )
            all_records.extend(records)

            # 20件ごとに中間保存
            if i % 20 == 0:
                save_to_csv(all_records)
                all_records = []
                logger.info(f'      ── 中間保存 ({i}/{len(targets)}) ──')

            await asyncio.sleep(random.uniform(1.0, 2.0))

        await browser.close()

    save_to_csv(all_records)
    _mark_scraped_today()
    logger.info('=== 完了 ===')


if __name__ == '__main__':
    asyncio.run(main())
