"""
JAN充足タスク（一回限りの実行用スクリプト）。

data/raw/ の追加5業者スクレイプ結果（jan列に実際のJANが入っている）を突き合わせ、
products.py の PRODUCTS のうち jan フィールドを持たない商品にJANを埋める。

外部API不使用。data/raw/ は読み取りのみ。data/prices.csv / docs/prices.csv は触らない。
既存の jan は上書きしない。複数の異なるJANが見つかった商品は「要確認」として除外する。
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / 'data' / 'raw'
PRODUCTS_FILE = BASE_DIR / 'scraper' / 'products.py'
REPORT_FILE = BASE_DIR / 'reports' / 'jan_backfill_report.md'

JAN_RE = re.compile(r'^\d{13}$')


def normalize_jan(value: str) -> str:
    value = (value or '').strip()
    return value if JAN_RE.match(value) else ''


def collect_raw_jan_map() -> tuple[dict[str, set[str]], int, int]:
    """product_name -> {jan, ...} の対応表を data/raw/ 全CSVから作る"""
    jan_map: dict[str, set[str]] = defaultdict(set)
    files_read = 0
    rows_read = 0

    for path in sorted(RAW_DIR.glob('*.csv')):
        files_read += 1
        with path.open(newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                rows_read += 1
                name = (row.get('product_name') or '').strip()
                jan = normalize_jan(row.get('jan', ''))
                if name and jan:
                    jan_map[name].add(jan)

    return jan_map, files_read, rows_read


NAME_RE = re.compile(r"\{'name':\s*'((?:[^'\\]|\\.)*)'")
HAS_JAN_RE = re.compile(r"'jan':\s*'")


def backfill_products_py(jan_map: dict[str, set[str]]) -> tuple[list[tuple[str, str]], list[tuple[str, list[str]]], int]:
    """products.py を書き換え、(反映一覧, 要確認一覧, 未充足件数) を返す"""
    text = PRODUCTS_FILE.read_text(encoding='utf-8')
    lines = text.split('\n')

    applied: list[tuple[str, str]] = []
    conflicts: list[tuple[str, list[str]]] = []
    no_data = 0

    out_lines = []
    for line in lines:
        m = NAME_RE.search(line)
        if not m or not line.strip().startswith("{'name':") or HAS_JAN_RE.search(line):
            out_lines.append(line)
            continue

        name = m.group(1)
        jans = jan_map.get(name)

        if not jans:
            no_data += 1
            out_lines.append(line)
            continue

        if len(jans) > 1:
            conflicts.append((name, sorted(jans)))
            out_lines.append(line)
            continue

        jan = next(iter(jans))
        new_line = line.replace(
            f"{{'name': '{name}',",
            f"{{'name': '{name}', 'jan': '{jan}',",
            1,
        )
        if new_line == line:
            # フォールバック: パターンが想定外の場合は挿入位置を name の直後にする
            insert_at = m.end()
            new_line = line[:insert_at] + f", 'jan': '{jan}'" + line[insert_at:]
        applied.append((name, jan))
        out_lines.append(new_line)

    PRODUCTS_FILE.write_text('\n'.join(out_lines), encoding='utf-8')
    return applied, conflicts, no_data


def count_total_and_existing_jan() -> tuple[int, int]:
    text = PRODUCTS_FILE.read_text(encoding='utf-8')
    total = len(re.findall(r"^\s*\{'name':", text, flags=re.MULTILINE))
    with_jan = len(re.findall(r"^\s*\{'name':[^\n]*'jan':\s*'", text, flags=re.MULTILINE))
    return total, with_jan


def write_report(
    before_total: int,
    before_with_jan: int,
    applied: list[tuple[str, str]],
    conflicts: list[tuple[str, list[str]]],
    no_data: int,
    files_read: int,
    rows_read: int,
) -> None:
    after_total, after_with_jan = count_total_and_existing_jan()

    lines = [
        '# JAN充足レポート',
        '',
        f'data/raw/ 配下 {files_read} ファイル（{rows_read} 行）を突き合わせ。',
        '',
        '## サマリー',
        '',
        f'- 反映前: {before_with_jan}/{before_total} 件（{before_with_jan / before_total * 100:.1f}%）',
        f'- 反映後: {after_with_jan}/{after_total} 件（{after_with_jan / after_total * 100:.1f}%）',
        f'- 新規反映: {len(applied)} 件',
        f'- 要確認（JAN不一致）: {len(conflicts)} 件',
        f'- 未充足（rawに該当データなし）: {no_data} 件',
        '',
        '## 反映した商品一覧',
        '',
        '| 商品名 | JAN |',
        '|---|---|',
    ]
    for name, jan in sorted(applied):
        lines.append(f'| {name} | {jan} |')

    lines.extend([
        '',
        '## 要確認（JAN不一致 — products.pyには未反映）',
        '',
        '同一商品名で複数の異なるJANがrawに出現。人手での確認が必要。',
        '',
        '| 商品名 | 候補JAN |',
        '|---|---|',
    ])
    for name, jans in sorted(conflicts):
        lines.append(f'| {name} | {", ".join(jans)} |')

    lines.extend([
        '',
        f'## 未充足（{no_data}件）',
        '',
        'rawに一度も出現しなかった商品名（買取一丁目専売、または旧・廃盤商品の可能性）。',
        '個別確認は行っていない。',
    ])

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> None:
    before_total, before_with_jan = count_total_and_existing_jan()
    jan_map, files_read, rows_read = collect_raw_jan_map()
    applied, conflicts, no_data = backfill_products_py(jan_map)
    write_report(before_total, before_with_jan, applied, conflicts, no_data, files_read, rows_read)

    after_total, after_with_jan = count_total_and_existing_jan()
    print(f'files={files_read} rows={rows_read}')
    print(f'before: {before_with_jan}/{before_total}')
    print(f'after:  {after_with_jan}/{after_total}')
    print(f'applied={len(applied)} conflicts={len(conflicts)} no_data={no_data}')


if __name__ == '__main__':
    main()
