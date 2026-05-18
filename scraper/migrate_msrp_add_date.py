"""
msrp.csv に effective_date 列を追加するマイグレーション（一回限り実行）
既存の全行に effective_date = '2000-01-01' を付与する。
"""
import csv, sys, io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.parent
MSRP_FILE = BASE_DIR / 'data' / 'msrp.csv'
DOCS_FILE = BASE_DIR / 'docs' / 'msrp.csv'

OLD_FIELDS = ['product_name', 'msrp', 'source_url', 'matched_title']
NEW_FIELDS = ['product_name', 'msrp', 'effective_date', 'source_url', 'matched_title']


def migrate(path: Path) -> None:
    if not path.exists():
        print(f'  スキップ（ファイルなし）: {path}')
        return

    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        existing_fields = reader.fieldnames or []

    if 'effective_date' in existing_fields:
        print(f'  すでにマイグレーション済み: {path}')
        return

    for row in rows:
        row['effective_date'] = '2000-01-01'

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=NEW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f'  完了 ({len(rows)} 件): {path}')


print('msrp.csv マイグレーション開始')
migrate(MSRP_FILE)
migrate(DOCS_FILE)
print('完了')
