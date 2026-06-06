# 2-1. 買取価格収集・チャート表示 HANDOFF

## 最新引き継ぎ 2026-06-06

### 現在地

- 2026-06-06の日次スクレイピングは完了。`data/prices.csv` / `docs/prices.csv` は同期済み、当日行は140件。
- 追加5業者の当日行は110件、JAN欠けは0件。
- rawは `data/raw/20260606_121705_*.csv` に保存済み。モバイル一番 iPhone 21商品、買取ホムラ iPhone 9商品はいずれもJAN欠け0件。
- `logs/scraper.log` の2026-06-06分に ERROR / Traceback / failed / Exception は0件。
- ヤフオク完了マーカーは `data/last_yahoo_scrape.txt` / `docs/last_yahoo_scrape.txt` とも `2026-06-06` に同期済み。
- `scraper/scrape_yahoo.py` は `data/last_yahoo_scrape.txt` を書く。`run_scraper.ps1` も同マーカーを `docs/` へコピーし、git addするよう修正済み。
- `reports/coverage_matrix.md` / `reports/coverage_matrix.csv` は2026-06-06版に更新済み。

### 次にやること

- 取得業者数0の商品 `トモダチコレクション Switch 2` を優先調査する。
- 取得業者数1の商品24件は、`reports/coverage_matrix.csv` を見て対象業者・対象サイトの差異を順に調査する。

### 未解決

- `data/last_scrape_yahoo.txt` が過去の誤マーカーとして残っている。削除は未実施。
- `run_scraper.ps1` は未追跡ファイル。ローカル運用に必要なため、追跡対象にするか扱いは要確認。

### 触ってはいけないもの

- `data/raw/` は削除しない。
- `.bak_...` ファイルは削除しない。
- データ未取得時にCSVを手で埋めて完了扱いにしない。必ず仕組み側を確認する。

## 現在地

- 買取店・ヤフオク価格の日次収集、JAN統合、GitHub Pages反映は稼働中。
- 主運用は Windows タスクスケジューラ、GitHub Actions はバックアップ扱い。
- 2026-06-02時点で、CSV同期、追加5業者raw保存、モバイル一番iPhone21商品、買取ホムラiPhone9商品は確認済み。
- JAN付き商品205件は、買取一丁目APIのJAN別商品名に合わせて正規化済み。
- 2026-06-02の日次確認ではカバレッジ悪化0件、改善8件。

## 次にやること

- 次回日次確認で、今日分CSV、追加5業者raw、JAN欠け、公開CSV、カバレッジを確認する。
- `reports/coverage_matrix.csv` を見て、取得業者数1の商品と完全未取得商品から改善候補を整理する。
- 完全未取得の `トモダチコレクション Switch 2` を優先調査する。

## 未解決

- 完全未取得: `トモダチコレクション Switch 2`
- 取得業者数1の商品が24件残っている。
- `run_scraper.ps1` はローカル固有の未追跡ファイル。12:17通常実行でrawが継続生成されるか引き続き確認する。

## 触ってはいけないもの

- `data/raw/` を削除しない。
- `.bak_...` ファイルを削除しない。
- データ未取得時にCSVを手動で埋めて終わらせない。必ず仕組み側を確認する。
- 親フォルダ直下MDへ細かい作業ログを書き足さない。履歴は `WORKLOG.md` に書く。
