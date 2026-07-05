"""
買取価格スクレイパー
- 買取一丁目 (requests + JSON REST API)
"""

import csv
from html import unescape
import logging
import os
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
RUN_STAMP = datetime.now(JST).strftime('%Y%m%d_%H%M%S')

BASE_DIR      = Path(__file__).parent.parent
DATA_FILE     = BASE_DIR / 'data' / 'prices.csv'
RAW_DIR       = BASE_DIR / 'data' / 'raw'
SCRAPE_MARKER = BASE_DIR / 'data' / 'last_scrape.txt'
CSV_HEADERS   = ['date', 'product_name', 'store', 'price', 'jan', 'url']

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

def _normalize_jan(jan: str | int | None) -> str:
    """JANを数字13桁だけの文字列に正規化する"""
    if jan is None:
        return ''
    m = _JAN_RE.search(str(jan))
    return m.group(1) if m else ''


def _product_jans(product: dict) -> list[str]:
    jans = []
    if product.get('jan'):
        jans.append(product['jan'])
    jans.extend(product.get('jans', []))
    return [_normalize_jan(jan) for jan in jans if _normalize_jan(jan)]


def _build_jan_index() -> dict[str, dict]:
    """products.py と既存CSVから JAN -> 商品マスタ の照合辞書を作る"""
    by_name = {product['name']: product for product in ALL_PRODUCTS}
    by_jan: dict[str, dict] = {}

    for product in ALL_PRODUCTS:
        for jan in _product_jans(product):
            by_jan.setdefault(jan, product)

    if DATA_FILE.exists():
        with open(DATA_FILE, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                product = by_name.get(row.get('product_name', ''))
                jan = _normalize_jan(row.get('jan'))
                if product and jan:
                    by_jan.setdefault(jan, product)

    return by_jan


JAN_PRODUCT_INDEX = _build_jan_index()


def known_jan_for_product(product: dict) -> str:
    """既存CSVや商品マスタから分かる代表JANを返す。"""
    for jan, indexed_product in JAN_PRODUCT_INDEX.items():
        if indexed_product.get('name') == product.get('name'):
            return jan
    return ''


def match_product_by_jan(jan: str | int | None) -> dict | None:
    """JANが分かる場合はJANを最優先で商品マスタに対応させる"""
    return JAN_PRODUCT_INDEX.get(_normalize_jan(jan))


def match_product(text: str) -> dict | None:
    """テキストが products.py のどの商品に対応するか（JANなし時のフォールバック）"""
    text_n = _normalize(text)
    for product in ALL_PRODUCTS:
        for kw in product['keywords']:
            if _normalize(kw) in text_n:
                return product
    return None


def match_product_record(text: str, jan: str | int | None = None) -> dict | None:
    """業者横断の照合。JANが取れた商品はJAN一致のみ、JANなし商品だけ商品名で照合する。"""
    normalized_jan = _normalize_jan(jan)
    if normalized_jan:
        return match_product_by_jan(normalized_jan)
    return match_product(text)


# ════════════════════════════════════════════════════════════════════════
# モバイル一番スクレイパー（HTML）
# ════════════════════════════════════════════════════════════════════════
MOBILE_ICHIBAN_BASE = 'https://www.mobile-ichiban.com'
MOBILE_ICHIBAN_URLS = [
    (MOBILE_ICHIBAN_BASE + '/Prod/1', 'スマホ'),
    (MOBILE_ICHIBAN_BASE + '/Prod/2', '家電・ゲーム・カメラ'),
    (MOBILE_ICHIBAN_BASE + '/Prod/3', 'おもちゃ・トレカ'),
]


def _clean_html_text(text: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', text)
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _prefer_new_record(current: dict | None, new: dict) -> bool:
    """同じ商品で複数候補がある場合はJAN付き候補を優先する"""
    if current is None:
        return True
    current_jan = bool(_normalize_jan(current.get('jan')))
    new_jan = bool(_normalize_jan(new.get('jan')))
    if current_jan != new_jan:
        return new_jan
    return int(new.get('price') or 0) > int(current.get('price') or 0)


def _mobile_ichiban_color_variants(block: str, item_id: str) -> list[tuple[str, int]]:
    select_m = re.search(
        rf'<select[^>]+id="NewColor_{re.escape(item_id)}"[^>]*>(.*?)</select>',
        block,
        re.S,
    )
    if not select_m:
        return []

    color_map = {
        '銀': 'シルバー',
        '青': 'ディープブルー',
        '橙': 'コズミックオレンジ',
    }
    variants = []
    for value, option_html in re.findall(r'<option\s+value="([^"]+)"[^>]*>(.*?)</option>', select_m.group(1), re.S):
        if value == '0':
            continue
        option_text = _clean_html_text(option_html)
        color_key = re.sub(r'\s*\(.*?\)\s*', '', option_text).strip()
        color_name = color_map.get(color_key)
        if not color_name:
            continue

        adjustment = 0
        adj_m = re.search(r'\(([-−+]?[0-9,]+)円\)', option_text)
        if adj_m:
            adjustment = int(adj_m.group(1).replace('−', '-').replace(',', ''))
        variants.append((color_name, adjustment))

    return variants


def _mobile_ichiban_status(block: str) -> str:
    labels = re.findall(
        r'<label[^>]+title="([^"]+)"[^>]*style="height:21px"[^>]*>',
        block,
    )
    return _clean_html_text(labels[1]) if len(labels) > 1 else ''


def _mobile_ichiban_cards(html: str) -> list[dict]:
    """モバイル一番の商品カードHTMLから title/JAN/price を抽出する"""
    cards = []
    img_matches = list(re.finditer(r'id="Img_(S\d+)"', html))

    for i, match in enumerate(img_matches):
        item_id = match.group(1)
        start = match.start()
        end = img_matches[i + 1].start() if i + 1 < len(img_matches) else len(html)
        block = html[start:end]

        title_m = re.search(
            r'<label[^>]+title="([^"]+)"[^>]*style="height:21px"[^>]*>',
            block,
        )
        price_m = re.search(
            rf'id="NewPrice_{re.escape(item_id)}"[^>]*>\s*([0-9,]+)\s*円',
            block,
        )
        jan_m = re.search(r'JAN[:：]\s*([0-9]{13})', block)
        if not title_m or not price_m:
            continue

        title = _clean_html_text(title_m.group(1))
        price = int(price_m.group(1).replace(',', ''))
        jan = jan_m.group(1) if jan_m else ''
        if title and price > 0:
            status = _mobile_ichiban_status(block)
            variants = _mobile_ichiban_color_variants(block, item_id)
            if variants and title.startswith('iPhone '):
                for color_name, adjustment in variants:
                    cards.append({
                        'item_id': item_id,
                        'title': f'{title} {color_name}',
                        'status': status,
                        'jan': jan,
                        'price': price + adjustment,
                    })
            else:
                cards.append({
                    'item_id': item_id,
                    'title': title,
                    'status': status,
                    'jan': jan,
                    'price': price,
                })

    return cards


def scrape_mobile_ichiban() -> list[dict]:
    results = []
    store = 'モバイル一番'
    found_products: dict[str, dict] = {}
    session = requests.Session()

    for url, page_name in MOBILE_ICHIBAN_URLS:
        try:
            resp = session.get(url, headers=COMMON_HEADERS, timeout=30)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
        except Exception as e:
            logger.error(f'モバイル一番 {page_name}: 取得エラー {e}')
            continue

        cards = _mobile_ichiban_cards(resp.text)
        matched = 0
        for card in cards:
            if card['title'].startswith('iPhone ') and '開封' in card.get('status', '') and '未開封' not in card.get('status', ''):
                continue
            product = match_product_record(card['title'], card['jan'])
            if not product:
                continue
            matched += 1
            jan = _normalize_jan(card['jan']) or known_jan_for_product(product)
            candidate = {
                'price': card['price'],
                'jan': jan,
                'url': f'{url}#Img_{card["item_id"]}',
            }
            if not _prefer_new_record(found_products.get(product['name']), candidate):
                continue
            found_products[product['name']] = candidate
            logger.info(
                f'  ✓ {product["name"]} → ¥{card["price"]:,}  '
                f'({card["title"]} / JAN:{jan})'
            )

        logger.info(f'  {page_name}: {len(cards)} アイテム取得, {matched} 件マッチ')
        time.sleep(1)

    for name, info in found_products.items():
        results.append({
            'date': TODAY, 'product_name': name,
            'store': store, 'price': info['price'],
            'jan': info['jan'], 'url': info['url'],
        })

    logger.info(f'モバイル一番: {len(results)} 件')
    return results


# ════════════════════════════════════════════════════════════════════════
# 買取ルデヤスクレイパー（HTML）
# ════════════════════════════════════════════════════════════════════════
RUDEYA_BASE = 'https://kaitori-rudeya.com'
RUDEYA_URLS = [
    (RUDEYA_BASE + '/', 'トップ'),
    (RUDEYA_BASE + '/category/detail/214', 'Nintendo Switch 2'),
    (RUDEYA_BASE + '/category/detail/1', 'Nintendo Switch'),
    (RUDEYA_BASE + '/category/detail/2', 'PlayStation5'),
    (RUDEYA_BASE + '/category/detail/159', 'PlayStation Portal'),
    (RUDEYA_BASE + '/category/detail/32', 'ゲームソフト'),
    (RUDEYA_BASE + '/category/detail/3', 'Xbox'),
    (RUDEYA_BASE + '/category/detail/55', 'Steam Deck'),
    (RUDEYA_BASE + '/category/detail/11', 'カメラ'),
    (RUDEYA_BASE + '/category/detail/131', 'チェキフィルム'),
    (RUDEYA_BASE + '/category/detail/220', 'iPhone17 ProMax'),
    (RUDEYA_BASE + '/category/detail/219', 'iPhone17 Pro'),
    (RUDEYA_BASE + '/category/detail/224', 'ONE PIECE カード'),
]


def _rudeya_items(html: str, page_url: str) -> list[dict]:
    items = []

    for m in re.finditer(r'<div class="td td1"[^>]*>(.*?)(?=<div class="td td1"|\Z)', html, re.S):
        block = m.group(1)
        title_m = re.search(r'<h2>(.*?)</h2>', block, re.S)
        price_m = re.search(r'<div class="td2wrap">\s*([0-9,]+)', block, re.S)
        if not title_m or not price_m:
            continue
        jan_m = re.search(r'<p class="janc">\s*([0-9]{13})', block, re.S)
        href_m = re.search(r'<a href="([^"]+)">', block)
        items.append({
            'title': _clean_html_text(title_m.group(1)),
            'jan': jan_m.group(1) if jan_m else '',
            'price': int(price_m.group(1).replace(',', '')),
            'url': href_m.group(1) if href_m else page_url,
        })

    for m in re.finditer(r'<a href="([^"]+)" class="product-card">(.*?)</a>', html, re.S):
        href, block = m.groups()
        title_m = re.search(r'<div class="title-text">(.*?)</div>', block, re.S)
        price_m = re.search(r'<span class="kuikomi-price">\s*([0-9,]+)', block, re.S)
        if title_m and price_m:
            items.append({
                'title': _clean_html_text(title_m.group(1)),
                'jan': '',
                'price': int(price_m.group(1).replace(',', '')),
                'url': href,
            })

    return items


def scrape_rudeya() -> list[dict]:
    results = []
    store = '買取ルデヤ'
    found_products: dict[str, dict] = {}
    session = requests.Session()

    for url, page_name in RUDEYA_URLS:
        try:
            resp = session.get(url, headers=COMMON_HEADERS, timeout=30)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
        except Exception as e:
            logger.error(f'買取ルデヤ {page_name}: 取得エラー {e}')
            continue

        items = _rudeya_items(resp.text, url)
        matched = 0
        for item in items:
            product = match_product_record(item['title'], item['jan'])
            if not product:
                continue
            matched += 1
            jan = _normalize_jan(item['jan']) or known_jan_for_product(product)
            item = {**item, 'jan': jan}
            if not _prefer_new_record(found_products.get(product['name']), item):
                continue
            found_products[product['name']] = item
            logger.info(
                f'  ✓ {product["name"]} → ¥{item["price"]:,}  '
                f'({item["title"]} / JAN:{item["jan"]})'
            )

        logger.info(f'  {page_name}: {len(items)} アイテム取得, {matched} 件マッチ')
        time.sleep(1)

    for name, info in found_products.items():
        results.append({
            'date': TODAY, 'product_name': name,
            'store': store, 'price': info['price'],
            'jan': info['jan'], 'url': info['url'],
        })

    logger.info(f'買取ルデヤ: {len(results)} 件')
    return results


# ════════════════════════════════════════════════════════════════════════
# 森森買取スクレイパー（価格表HTML）
# ════════════════════════════════════════════════════════════════════════
MORIMORI_BASE = 'https://www.morimori-kaitori.jp'
MORIMORI_HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Encoding': 'identity',
    'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
    'Connection': 'close',
}
MORIMORI_SEARCH_TERMS = [
    'switch2',
    'Nintendo Switch',
    'PlayStation5',
    'Steam Deck',
    'Meta Quest',
    'RICOH GR',
    'PowerShot',
    'instax',
    'ポケモンカード',
    'ONE PIECEカード',
    'iPhone 17 Pro Max',
    'iPhone 17 Pro',
]


def _morimori_items(html: str, page_url: str) -> list[dict]:
    items = []
    for m in re.finditer(r'<tr>(.*?)</tr>', html, re.S):
        row = m.group(1)
        cols = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
        if len(cols) < 6:
            continue
        title = _clean_html_text(cols[4])
        jan = _normalize_jan(_clean_html_text(cols[5]))
        price = None
        for col in cols[6:]:
            price_m = re.search(r'([0-9,]+)\s*円', _clean_html_text(col))
            if price_m:
                price = int(price_m.group(1).replace(',', ''))
                break
        if not title or not price:
            continue
        href_m = re.search(r'href=[\'"]([^\'"]+)[\'"]', cols[4])
        item_url = page_url
        if href_m:
            href = href_m.group(1)
            item_url = href if href.startswith('http') else MORIMORI_BASE + href
        items.append({'title': title, 'jan': jan, 'price': price, 'url': item_url})
    return items


def scrape_morimori() -> list[dict]:
    results = []
    store = '森森買取'
    found_products: dict[str, dict] = {}
    session = requests.Session()

    for term in MORIMORI_SEARCH_TERMS:
        url = MORIMORI_BASE + '/search/' + requests.utils.quote(term)
        params = {'price-list': 'true', 'sk': term}
        try:
            resp = session.get(url, params=params, headers=MORIMORI_HEADERS, timeout=30)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
        except Exception as e:
            logger.error(f'森森買取 {term}: 取得エラー {e}')
            continue

        items = _morimori_items(resp.text, resp.url)
        matched = 0
        for item in items:
            product = match_product_record(item['title'], item['jan'])
            if not product:
                continue
            matched += 1
            if not _prefer_new_record(found_products.get(product['name']), item):
                continue
            found_products[product['name']] = item
            logger.info(
                f'  ✓ {product["name"]} → ¥{item["price"]:,}  '
                f'({item["title"]} / JAN:{item["jan"]})'
            )

        logger.info(f'  {term}: {len(items)} アイテム取得, {matched} 件マッチ')
        time.sleep(1)

    for name, info in found_products.items():
        results.append({
            'date': TODAY, 'product_name': name,
            'store': store, 'price': info['price'],
            'jan': info['jan'], 'url': info['url'],
        })

    logger.info(f'森森買取: {len(results)} 件')
    return results


# ════════════════════════════════════════════════════════════════════════
# 買取ホムラスクレイパー（HTML）
# ════════════════════════════════════════════════════════════════════════
HOMURA_BASE = 'https://kaitori-homura.com'
HOMURA_URLS = [
    (HOMURA_BASE + '/', 'トップ'),
    (HOMURA_BASE + '/products?q%5Bproduct_sub_category_id_eq%5D=97&q%5Bproduct_sub_category_product_category_id_eq%5D=10', 'iPhone 17 Pro Max'),
    (HOMURA_BASE + '/products?q%5Bproduct_sub_category_id_eq%5D=96&q%5Bproduct_sub_category_product_category_id_eq%5D=10', 'iPhone 17 Pro'),
    (HOMURA_BASE + '/products?q%5Bproduct_sub_category_id_eq%5D=122&q%5Bproduct_sub_category_product_category_id_eq%5D=13', 'PlayStation'),
    (HOMURA_BASE + '/products?q%5Bproduct_sub_category_id_eq%5D=124&q%5Bproduct_sub_category_product_category_id_eq%5D=13', 'Switch'),
    (HOMURA_BASE + '/products?q%5Bproduct_sub_category_id_eq%5D=125&q%5Bproduct_sub_category_product_category_id_eq%5D=13', 'Switch ソフト'),
    (HOMURA_BASE + '/products?q%5Bproduct_sub_category_id_eq%5D=121&q%5Bproduct_sub_category_product_category_id_eq%5D=13', 'Meta Quest'),
    (HOMURA_BASE + '/products?q%5Bproduct_sub_category_id_eq%5D=126&q%5Bproduct_sub_category_product_category_id_eq%5D=13', 'Xbox'),
    (HOMURA_BASE + '/products?q%5Bproduct_sub_category_id_eq%5D=128&q%5Bproduct_sub_category_product_category_id_eq%5D=14', 'ポケカ シュリンク有り'),
    (HOMURA_BASE + '/products?q%5Bproduct_sub_category_id_eq%5D=132&q%5Bproduct_sub_category_product_category_id_eq%5D=14', 'ワンピース 未開封BOX'),
    (HOMURA_BASE + '/products?q%5Bproduct_sub_category_id_eq%5D=112&q%5Bproduct_sub_category_product_category_id_eq%5D=12', 'Canon'),
    (HOMURA_BASE + '/products?q%5Bproduct_sub_category_id_eq%5D=113&q%5Bproduct_sub_category_product_category_id_eq%5D=12', 'FUJIFILM'),
    (HOMURA_BASE + '/products?q%5Bproduct_sub_category_id_eq%5D=117&q%5Bproduct_sub_category_product_category_id_eq%5D=12', 'RICOH'),
    (HOMURA_BASE + '/products?q%5Bproduct_sub_category_id_eq%5D=120&q%5Bproduct_sub_category_product_category_id_eq%5D=12', 'TAMRON'),
    (HOMURA_BASE + '/products?q%5Bproduct_sub_category_id_eq%5D=111&q%5Bproduct_sub_category_product_category_id_eq%5D=11', 'INSTAX'),
    (HOMURA_BASE + '/products?q%5Bproduct_sub_category_id_eq%5D=166&q%5Bproduct_sub_category_product_category_id_eq%5D=19', 'たまごっち'),
]


def _homura_items(html: str, page_url: str) -> list[dict]:
    items = []
    for m in re.finditer(r'<a href="(/products/\d+(?:\?[^"]*)?)">\s*<h5\b.*?</h5>\s*</a>', html, re.S):
        start = m.start()
        end = min(len(html), m.end() + 2500)
        block = html[start:end]

        href = unescape(m.group(1))
        title_m = re.search(r'<h5\b[^>]*>(.*?)</h5>', block, re.S)
        jan_m = re.search(r'</h5>\s*</a>\s*<span[^>]*>\s*([0-9]{13})\s*</span>', block, re.S)
        price_m = re.search(r'買取金額（税込）.*?<span[^>]*>\s*([0-9,]+)\s*円\s*</span>', block, re.S)
        if not price_m:
            price_m = re.search(r'<span[^>]*>\s*([0-9,]+)\s*円\s*</span>', block, re.S)
        if not title_m or not price_m:
            continue

        items.append({
            'title': _clean_html_text(title_m.group(1)),
            'jan': jan_m.group(1) if jan_m else '',
            'price': int(price_m.group(1).replace(',', '')),
            'url': HOMURA_BASE + href,
        })

    return items


def scrape_homura() -> list[dict]:
    results = []
    store = '買取ホムラ'
    found_products: dict[str, dict] = {}
    session = requests.Session()

    for url, page_name in HOMURA_URLS:
        try:
            resp = session.get(url, headers=COMMON_HEADERS, timeout=30)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
        except Exception as e:
            logger.error(f'買取ホムラ {page_name}: 取得エラー {e}')
            continue

        items = _homura_items(resp.text, url)
        matched = 0
        for item in items:
            product = match_product_record(item['title'], item['jan'])
            if not product:
                continue
            matched += 1
            jan = _normalize_jan(item['jan']) or known_jan_for_product(product)
            item = {**item, 'jan': jan}
            if not _prefer_new_record(found_products.get(product['name']), item):
                continue
            found_products[product['name']] = item
            logger.info(
                f'  ✓ {product["name"]} → ¥{item["price"]:,}  '
                f'({item["title"]} / JAN:{item["jan"]})'
            )

        logger.info(f'  {page_name}: {len(items)} アイテム取得, {matched} 件マッチ')
        time.sleep(1)

    for name, info in found_products.items():
        results.append({
            'date': TODAY, 'product_name': name,
            'store': store, 'price': info['price'],
            'jan': info['jan'], 'url': info['url'],
        })

    logger.info(f'買取ホムラ: {len(results)} 件')
    return results


# ════════════════════════════════════════════════════════════════════════
# 買取商店スクレイパー（HTML）
# ════════════════════════════════════════════════════════════════════════
KAITORI_SHOUTEN_BASE = 'https://www.kaitorishouten-co.jp'
KAITORI_SHOUTEN_URLS = [
    (KAITORI_SHOUTEN_BASE + '/keitai', '携帯'),
    (KAITORI_SHOUTEN_BASE + '/kaden', '家電・ゲーム・カメラ'),
]


def _kaitori_shouten_items(html: str, page_url: str) -> list[dict]:
    items = []
    for m in re.finditer(r'<form name="form\d+".*?</form>', html, re.S):
        block = m.group(0)
        title_m = re.search(r'<h4 class="item-title">\s*(.*?)\s*</br>\s*</h4>', block, re.S)
        jan_m = re.search(
            r'<span class="product-code-default">JAN:</span>\s*'
            r'<span class="product-code-default">\s*([0-9]{13})\s*</span>',
            block,
            re.S,
        )
        price_m = re.search(r'<div class="item-price encrypt-price plain-price">\s*([0-9,]+)\s*円\s*</div>', block)
        if not title_m or not price_m:
            continue
        items.append({
            'title': _clean_html_text(title_m.group(1)),
            'jan': jan_m.group(1) if jan_m else '',
            'price': int(price_m.group(1).replace(',', '')),
            'url': page_url,
        })
    return items


def scrape_kaitori_shouten() -> list[dict]:
    results = []
    store = '買取商店'
    found_products: dict[str, dict] = {}
    session = requests.Session()

    for url, page_name in KAITORI_SHOUTEN_URLS:
        try:
            resp = session.get(url, headers=COMMON_HEADERS, timeout=30)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
        except Exception as e:
            logger.error(f'買取商店 {page_name}: 取得エラー {e}')
            continue

        items = _kaitori_shouten_items(resp.text, url)
        matched = 0
        for item in items:
            product = match_product_record(item['title'], item['jan'])
            if not product:
                continue
            matched += 1
            if not _prefer_new_record(found_products.get(product['name']), item):
                continue
            found_products[product['name']] = item
            logger.info(
                f'  ✓ {product["name"]} → ¥{item["price"]:,}  '
                f'({item["title"]} / JAN:{item["jan"]})'
            )

        logger.info(f'  {page_name}: {len(items)} アイテム取得, {matched} 件マッチ')
        time.sleep(1)

    for name, info in found_products.items():
        results.append({
            'date': TODAY, 'product_name': name,
            'store': store, 'price': info['price'],
            'jan': info['jan'], 'url': info['url'],
        })

    logger.info(f'買取商店: {len(results)} 件')
    return results


# ════════════════════════════════════════════════════════════════════════
# 買取一丁目スクレイパー（JSON REST API）
# ════════════════════════════════════════════════════════════════════════
ICHOME_BASE = 'https://www.1-chome.com'
ICHOME_API  = ICHOME_BASE + '/api/goods/listPage'
KEITAI_API  = ICHOME_BASE + '/api/keitai/listPage'
KEITAI_CATE = 'RGNg976kptBN7UjF'
# 携帯・タブレット系カテゴリ（買取一丁目 keitai API）
# iPhoneはRGNg...、iPad Pro/Airは別カテゴリなので複数を巡回する
KEITAI_CATES = [
    'RGNg976kptBN7UjF',   # iPhone 等
    'qPwbIzxLPrjhoFsg',   # iPad Pro (M5)
    'm90g88jevgDkyzop',   # iPad Air (M4)
    'ThqjW9LGrBjz4ApX',   # Google Fitbit
]
KEITAI_TARGETS = {'iPhone 17', 'iPad', 'Fitbit'}

# (cateCode, 説明, isImpo)
# isImpo=true: 主要商品のみ（ハードのみ47件）
# isImpo=false: 全商品（ハード＋ソフト298件）
# トレカ系は isImpo=false でないと 0 件になる
ICHOME_CATEGORIES = [
    ('10000005',         'ゲーム',                False),   # falseで全商品（ソフト含む）
    ('20304465',         'Steam Deck',            True),
    ('10000001',         'カメラ本体・周辺',        False),  # falseで全商品（99→973件）
    ('20279112',         'インスタントカメラ',      False),  # falseで全商品
    ('20985614',         'チェキフイルム',          False),  # falseで全商品
    ('IIzyMdayU5wp7T4G', 'ポケモンカード',          False),
    ('SEbO7gSBevo6KsPE', 'ONE PIECE カード',        False),
    ('20482781',         'たまごっち',              False),  # electricAppliance配下
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


KEITAI_UNOPENED_LABELS = {'未開封', '新品'}


def _keitai_price_per_color(item: dict) -> list[dict]:
    """未開封（または新品）× 各色の (color, jan, price) リストを返す"""
    miko = next(
        (d for d in item.get('goodsKbDetails', [])
         if d.get('kbDetailName') in KEITAI_UNOPENED_LABELS and d.get('kbDetailPrice')),
        None,
    )
    if not miko:
        return []
    base_price = miko['kbDetailPrice']
    detail_id  = miko['allGoodsKbDetailId']

    results = []
    for opt in item.get('keitaiColorOptions', []):
        color = opt.get('color', '')
        jan   = str(opt.get('jan') or '')
        var   = 0
        for rel in opt.get('keitaiKbDetailColorRels', []):
            if rel.get('keitaiKbDetailId') == detail_id and rel.get('varPrice') is not None:
                var = rel['varPrice']
                break
        final = base_price + var
        if final > 0:
            results.append({'color': color, 'jan': jan, 'price': final})
    return results


def scrape_ichome_keitai() -> list[dict]:
    """携帯・スマートフォン系（/api/keitai/listPage）未開封 × 色別価格を取得"""
    results = []
    store   = '買取一丁目'
    session = requests.Session()
    headers = {
        **COMMON_HEADERS,
        'Accept': 'application/json, text/plain, */*',
        'Referer': f'{ICHOME_BASE}/mobile?category={KEITAI_CATE}',
    }

    total_fetched = 0
    for cate in KEITAI_CATES:
        page = 1
        while True:
            params = {
                'accCode': '', 'page': page, 'size': 50,
                'keyword': '', 'isImpo': 'false',
                'isCampaign': 'false', 'cateCode': cate,
                'kbNames': '', 'isImpoCate': 'false',
            }
            try:
                resp = session.get(KEITAI_API, params=params, headers=headers, timeout=30)
                if resp.status_code != 200:
                    logger.warning(f'keitai API HTTP {resp.status_code} (cate={cate})')
                    break
                data = resp.json().get('data', {})
            except Exception as e:
                logger.error(f'keitai API エラー (cate={cate}): {e}')
                break

            content = data.get('content', [])
            if not content:
                break
            total_fetched += len(content)

            for item in content:
                title = item.get('title', '').strip()
                if not any(t in title for t in KEITAI_TARGETS):
                    continue
                goods_id = item.get('goodsId', '')
                url = (f'{ICHOME_BASE}/mobileDetail/{goods_id}/{goods_id}' if goods_id
                       else f'{ICHOME_BASE}/mobile?category={cate}')
                for ci in _keitai_price_per_color(item):
                    pname = f'{title} {ci["color"]}'
                    results.append({
                        'date': TODAY, 'product_name': pname,
                        'store': store, 'price': ci['price'],
                        'jan': ci['jan'], 'url': url,
                    })
                    logger.info(f'  ✓ {pname} → ¥{ci["price"]:,}')

            total_pages = data.get('totalPages', 1)
            if page >= total_pages:
                break
            page += 1
            time.sleep(0.5)

    logger.info(f'  keitai: {total_fetched} アイテム取得, {len(results)} 件マッチ')
    return results


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
                jan = str(item.get('jan') or '') or ''
                product = match_product_record(title, jan)
                if product and product['name'] not in found_products:
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

    # 価格変化があった商品のみ追記（同一価格の連続記録を防ぐ）
    last_price: dict[tuple, str] = {}
    if DATA_FILE.exists():
        with open(DATA_FILE, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                last_price[(row['product_name'], row['store'])] = row['price']

    new_records = [
        r for r in records
        if last_price.get((r['product_name'], r['store'])) != str(r['price'])
    ]
    for r in new_records:
        r.setdefault('jan', '')
        r.setdefault('url', '')

    if not new_records:
        logger.info('価格変化なし — 追記スキップ')
        return

    with open(DATA_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if write_header:
            writer.writeheader()
        writer.writerows(new_records)

    logger.info(f'CSV に {len(new_records)} 件追記（価格変化あり）: {DATA_FILE}')


def save_raw_csv(store_name: str, records: list[dict]) -> None:
    """検証用に業者別raw CSVへ保存する。本番prices.csvには混ぜない。"""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    safe_store = re.sub(r'[^\w一-龥ぁ-んァ-ンー]+', '_', store_name)
    raw_file = RAW_DIR / f'{RUN_STAMP}_{safe_store}.csv'

    normalized = []
    for r in records:
        row = {key: r.get(key, '') for key in CSV_HEADERS}
        row['store'] = row.get('store') or store_name
        normalized.append(row)

    with open(raw_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(normalized)

    logger.info(f'raw CSV に {len(normalized)} 件保存: {raw_file}')


def scrape_extra_stores_to_raw() -> tuple[int, list[dict]]:
    """追加業者をraw保存し、JANがある行だけ本番CSV候補として返す。"""
    stores = [
        ('モバイル一番', scrape_mobile_ichiban),
        ('買取ルデヤ', scrape_rudeya),
        ('森森買取', scrape_morimori),
        ('買取ホムラ', scrape_homura),
        ('買取商店', scrape_kaitori_shouten),
    ]

    total = 0
    production_records: list[dict] = []
    for store_name, scraper in stores:
        logger.info(f'--- {store_name} (raw) ---')
        records = scraper()
        save_raw_csv(store_name, records)
        total += len(records)

        jan_records = [r for r in records if _normalize_jan(r.get('jan'))]
        skipped = len(records) - len(jan_records)
        production_records.extend(jan_records)
        logger.info(
            f'{store_name}: JANあり {len(jan_records)} 件を本番CSV候補、'
            f'JANなし {skipped} 件はrawのみ'
        )

    return total, production_records


# ════════════════════════════════════════════════════════════════════════
# エントリポイント
# ════════════════════════════════════════════════════════════════════════

def _already_scraped_today() -> bool:
    """マーカーファイルで今日実行済みか判定（価格変化なしでも正しく判定できる）"""
    if os.environ.get('SEDORI_FORCE_SCRAPE') == '1':
        logger.info('SEDORI_FORCE_SCRAPE=1 のため今日分も再取得します')
        return False
    return SCRAPE_MARKER.exists() and SCRAPE_MARKER.read_text(encoding='utf-8').strip() == TODAY

def _mark_scraped_today() -> None:
    SCRAPE_MARKER.write_text(TODAY, encoding='utf-8')


def main() -> None:
    logger.info(f'=== 価格収集開始 {TODAY} ===')

    if _already_scraped_today():
        logger.info('今日分データ取得済み — スキップ')
        logger.info('=== 完了（スキップ） ===')
        return

    logger.info('--- 買取一丁目 (通常商品) ---')
    all_records = scrape_ichome()

    logger.info('--- 買取一丁目 (スマートフォン) ---')
    all_records += scrape_ichome_keitai()

    logger.info(f'本番CSV対象 {len(all_records)} 件取得')
    save_to_csv(all_records)

    raw_total, extra_records = scrape_extra_stores_to_raw()
    logger.info(f'追加業者 raw 合計 {raw_total} 件取得')

    if extra_records:
        logger.info(f'追加業者 本番CSV対象 {len(extra_records)} 件取得（JANありのみ）')
        save_to_csv(extra_records)
    else:
        logger.info('追加業者 本番CSV対象なし（JANあり0件）')

    _mark_scraped_today()
    logger.info('=== 完了 ===')


if __name__ == '__main__':
    main()
