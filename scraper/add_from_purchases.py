"""
購入履歴 CSV → 買取一丁目マッチング＆products.py 自動追記ツール

Usage:
    python add_from_purchases.py <購入履歴.csv> [--dry-run]

CSV 列名は自動検出（商品名, product_name, name, title などに対応）。
既に products.py に登録済みの商品はスキップ。
未登録の商品を買取一丁目 API でキーワード検索し、
インタラクティブに確認してから products.py と docs/index.html を更新する。
"""

import csv
import re
import sys
import time
from pathlib import Path

import requests

# ── パス設定 ──────────────────────────────────────────────────────────
SCRAPER_DIR  = Path(__file__).parent
PRODUCTS_PY  = SCRAPER_DIR / 'products.py'
INDEX_HTML   = SCRAPER_DIR.parent / 'docs' / 'index.html'

sys.path.insert(0, str(SCRAPER_DIR))
from products import ALL_PRODUCTS
from scrape import (
    match_product, _normalize,
    ICHOME_API, ICHOME_HEADERS, ICHOME_CATEGORIES,
)

# ── CSV 列名候補（商品名として使う列を自動検出） ──────────────────────
_PRODUCT_COL_HINTS = [
    '商品名', '商品タイトル', '品名', '商品', '商品名称', '注文商品',
    'product_name', 'item_name', 'name', 'title',
]


def detect_product_col(headers: list[str]) -> str | None:
    """ヘッダーリストから商品名列を推定する"""
    hl = [h.lower().strip() for h in headers]
    for hint in _PRODUCT_COL_HINTS:
        h = hint.lower()
        for i, col in enumerate(hl):
            if h in col or col in h:
                return headers[i]
    return None


def load_purchase_csv(path: str) -> list[str]:
    """CSV を読み込み、ユニークな商品名リストを返す"""
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        col = detect_product_col(headers)

        if not col:
            print(f"⚠️  商品名列が自動検出できませんでした。")
            print(f"   利用可能な列: {headers}")
            print("   列名を入力してください: ", end='', flush=True)
            col = input().strip()
            if col not in headers:
                print("❌ その列名は存在しません")
                sys.exit(1)

        names: list[str] = []
        for row in reader:
            name = (row.get(col) or '').strip()
            if name and name not in names:
                names.append(name)

    print(f"📋 購入履歴: {len(names)} 件のユニーク商品  （列: {col}）")
    return names


# ── キーワード生成 ─────────────────────────────────────────────────────

def clean_keyword(title: str, max_len: int = 30) -> str:
    """タイトルから検索キーワードを生成する"""
    s = re.sub(r'【[^】]*】', '', title)   # 【...】を除去
    s = re.sub(r'\s+', ' ', s).strip()
    return s[:max_len]


# ── 買取一丁目 API 検索 ───────────────────────────────────────────────

def search_ichome(keyword: str) -> list[dict]:
    """全カテゴリをキーワード検索してヒット一覧を返す"""
    session = requests.Session()
    results: list[dict] = []
    seen: set[str] = set()

    for cate_code, cate_name, is_impo in ICHOME_CATEGORIES:
        try:
            params = {
                'accCode': '',
                'page': 1,
                'size': 20,
                'keyword': keyword,
                'isImpo': 'true' if is_impo else 'false',
                'isCampaign': 'false',
                'cateCode': cate_code,
            }
            resp = session.get(
                ICHOME_API, params=params,
                headers=ICHOME_HEADERS, timeout=15,
            )
            if resp.status_code != 200:
                continue
            items = resp.json().get('data', {}).get('content', [])
            for item in items:
                title = item.get('title', '').strip()
                if not title or title in seen:
                    continue
                seen.add(title)
                price = None
                for detail in item.get('goodsKbDetails', []):
                    p = detail.get('kbDetailPrice')
                    if p and int(p) > 0:
                        price = int(p)
                        break
                if price is None:
                    p = item.get('price')
                    if p:
                        try:
                            price = int(p)
                        except ValueError:
                            pass
                results.append({
                    'title':     title,
                    'price':     price,
                    'cate_code': cate_code,
                    'cate_name': cate_name,
                })
        except Exception:
            pass
        time.sleep(0.3)

    return results


# ── カテゴリ推定 ──────────────────────────────────────────────────────

_CATE_CODE_TO_CAT = {
    '10000005':         'ゲーム',
    '20304465':         'ゲーム',   # Steam Deck
    '10000001':         'カメラ',
    '20279112':         'カメラ',   # インスタントカメラ
    '20985614':         'カメラ',   # チェキフィルム
    'IIzyMdayU5wp7T4G': 'ポケカ',
    'SEbO7gSBevo6KsPE': 'ワンピ',
}

def guess_category(cate_code: str) -> str:
    return _CATE_CODE_TO_CAT.get(cate_code, 'その他')


# ── products.py 更新 ──────────────────────────────────────────────────

def append_to_products_py(
    category: str, name: str, keywords: list[str], dry_run: bool,
) -> bool:
    text = PRODUCTS_PY.read_text(encoding='utf-8')
    lines = text.splitlines(keepends=True)

    # カテゴリ開始行を探す
    cat_line_idx = None
    for i, line in enumerate(lines):
        if f"    '{category}': [" in line:
            cat_line_idx = i
            break
    if cat_line_idx is None:
        print(f"  ❌ カテゴリ '{category}' が products.py に見つかりません")
        return False

    # そのカテゴリの閉じ ], を探す
    close_idx = None
    for i in range(cat_line_idx + 1, len(lines)):
        if lines[i].strip() in ('],', '],'):
            close_idx = i
            break
    if close_idx is None:
        print("  ❌ 閉じブラケットが見つかりません")
        return False

    kw_str = ', '.join(f"'{k}'" for k in keywords)
    new_line = f"        {{'name': '{name}', 'keywords': [{kw_str}]}},\n"

    if dry_run:
        print(f"  [DRY-RUN] products.py → {category} カテゴリ末尾に追記予定:")
        print(f"    {new_line.strip()}")
        return True

    lines.insert(close_idx, new_line)
    PRODUCTS_PY.write_text(''.join(lines), encoding='utf-8')
    return True


# ── index.html の PRODUCT_CATEGORIES 更新 ────────────────────────────

def append_to_index_html(name: str, category: str, dry_run: bool) -> bool:
    if not INDEX_HTML.exists():
        print("  ⚠️  docs/index.html が見つかりません（スキップ）")
        return False

    text = INDEX_HTML.read_text(encoding='utf-8')
    marker = 'const PRODUCT_CATEGORIES = {'
    if marker not in text:
        print("  ⚠️  index.html の PRODUCT_CATEGORIES が見つかりません（スキップ）")
        return False

    start = text.index(marker)
    close_pos = text.index('};', start + len(marker))

    # その商品がすでに記載されていないか確認
    snippet = text[start:close_pos]
    if f"'{name}'" in snippet:
        print(f"  ℹ️  index.html にはすでに '{name}' が存在します")
        return True

    new_line = f"  '{name}': '{category}',\n"

    if dry_run:
        print(f"  [DRY-RUN] index.html PRODUCT_CATEGORIES に追記予定:")
        print(f"    {new_line.strip()}")
        return True

    new_text = text[:close_pos] + new_line + text[close_pos:]
    INDEX_HTML.write_text(new_text, encoding='utf-8')
    return True


# ── インタラクティブ選択 ──────────────────────────────────────────────

def interactive_add(purchase_name: str, results: list[dict], dry_run: bool) -> bool:
    """検索結果を表示してユーザーに選択させ、必要なら products.py を更新する"""
    print(f"\n─── 「{purchase_name[:60]}」")

    if not results:
        print("  買取一丁目に該当商品なし → スキップ")
        return False

    show = results[:10]
    for i, r in enumerate(show, 1):
        price_str = f"¥{r['price']:,}" if r['price'] else "価格不明"
        print(f"  [{i:2d}] {price_str:>10}  {r['title'][:55]}  ({r['cate_name']})")

    print("\n  番号を選択して追加 / [s] スキップ / [q] 終了: ", end='', flush=True)
    choice = input().strip().lower()

    if choice == 'q':
        print("終了します")
        sys.exit(0)
    if choice in ('s', ''):
        print("  → スキップ")
        return False

    try:
        idx = int(choice) - 1
        if not (0 <= idx < len(show)):
            raise ValueError
        selected = show[idx]
    except ValueError:
        print("  → 無効な入力、スキップ")
        return False

    # 短い名前
    suggested_name = clean_keyword(selected['title'], 20)
    print(f"  商品の短い名前 [{suggested_name}]: ", end='', flush=True)
    entered = input().strip()
    name = entered if entered else suggested_name

    # すでに同名が存在するか確認
    existing = {p['name'] for p in ALL_PRODUCTS}
    if name in existing:
        print(f"  ⚠️  '{name}' はすでに products.py に存在します → スキップ")
        return False

    # キーワード
    suggested_kw = clean_keyword(selected['title'], 30)
    print(f"  キーワード（カンマ区切り）[{suggested_kw}]: ", end='', flush=True)
    entered_kw = input().strip()
    if entered_kw:
        keywords = [k.strip() for k in entered_kw.split(',') if k.strip()]
    else:
        keywords = [suggested_kw]

    # カテゴリ
    auto_cat = guess_category(selected['cate_code'])
    print(f"  カテゴリ [{auto_cat}] (変更: ゲーム/カメラ/ポケカ/ワンピ/その他): ", end='', flush=True)
    entered_cat = input().strip()
    category = entered_cat if entered_cat else auto_cat

    # 書き込み
    ok1 = append_to_products_py(category, name, keywords, dry_run)
    ok2 = append_to_index_html(name, category, dry_run)

    if ok1:
        status = "[DRY-RUN] " if dry_run else ""
        print(f"  ✅ {status}'{name}' を {category} に追加しました")
    return ok1


# ── エントリポイント ──────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python add_from_purchases.py <購入履歴.csv> [--dry-run]")
        sys.exit(1)

    csv_path = sys.argv[1]
    dry_run  = '--dry-run' in sys.argv

    if dry_run:
        print("🔍 DRY-RUN モード（ファイルは変更されません）\n")

    # ── 1. CSV 読み込み
    purchase_names = load_purchase_csv(csv_path)

    # ── 2. 既存商品を分類
    print()
    already_tracked: list[str] = []
    unmatched:       list[str] = []

    for pname in purchase_names:
        matched = match_product(pname)
        if matched:
            already_tracked.append(pname)
            print(f"  ✓ 追跡済み: {matched['name']}  ← {pname[:50]}")
        else:
            unmatched.append(pname)

    print(f"\n  追跡済み: {len(already_tracked)} 件 / 未登録: {len(unmatched)} 件")

    if not unmatched:
        print("\n✅ すべての商品がすでに追跡対象です。")
        return

    # ── 3. 未登録商品を API 検索 → インタラクティブ追加
    print(f"\n🔎 未登録 {len(unmatched)} 件を買取一丁目で検索します\n")

    added = 0
    for i, pname in enumerate(unmatched, 1):
        kw = clean_keyword(pname, 30)
        print(f"[{i}/{len(unmatched)}] 検索: {kw}", flush=True)
        results = search_ichome(kw)
        ok = interactive_add(pname, results, dry_run)
        if ok:
            added += 1
        time.sleep(0.3)

    # ── 4. 完了メッセージ
    print(f"\n{'─'*50}")
    print(f"✅ 完了: {added} 件追加")
    if added > 0 and not dry_run:
        print()
        print("次のステップ:")
        print("  1. git add scraper/products.py docs/index.html")
        print("  2. git commit -m 'feat: add products from purchase history'")
        print("  3. git push")
        print("  → GitHub Actions が翌 JST 12:00 に自動スクレイプ")
        print("     （または Actions タブから workflow_dispatch で手動実行）")


if __name__ == '__main__':
    main()
