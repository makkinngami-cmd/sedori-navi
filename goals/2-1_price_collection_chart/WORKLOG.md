# 2-1. 買取価格収集・チャート表示 WORKLOG

## 2026-05-28

- ゴール別セッション運用に向けて `SESSION.md`、`HANDOFF.md`、`WORKLOG.md` を作成
- 実装データや既存スクリプトは未移動
- `CLAUDE.md` と `goals/2-1_price_collection_chart/SESSION.md` を読み、2-1担当セッションのMD運用を確認
- スクリプト・自動実行は `goals/` 配下MDを参照して動く構造ではないため、記録先移行だけでは既存運用は壊れないと判断
- 日次自動確認 `sedori-navi-daily-scrape-check` のプロンプトを更新し、今後は `CLAUDE.md` / `SESSION.md` を読んだうえで、詳細ログを `HANDOFF.md` / `WORKLOG.md` に書く運用へ変更

## 2026-05-30

- 日次自動確認を実施
- 12:17 のローカル `scrape.py` は `data/last_scrape.txt=2026-05-30` を見てスキップしていた
- 原因は、GitHub Actions 側の `chore: update prices 2026-05-30` が先に入り、ローカル実行前に当日マーカーが存在していたこと
- このままだと本番CSVには今日分が入っても、ローカル `data/raw/20260530_*.csv` が残らないため運用要件を満たさない
- ローカル `run_scraper.ps1` の `scrape.py` 実行時に `SEDORI_FORCE_SCRAPE=1` を付与し、当日マーカーがあってもローカルでは追加業者rawを生成するよう修正
- `SEDORI_FORCE_SCRAPE=1 python scraper/scrape.py` で仕組み側を再テストし、追加5業者 raw 合計539件、本番CSV候補533件、価格変化あり89件を取得
- `data/prices.csv` と `docs/prices.csv` を同期し、2026-05-30分は334行、追加5業者251行、追加5業者JAN欠け0件になった
- iPhone 17 Pro系は21商品/167行、モバイル一番21件、買取ホムラ9件、JAN欠け0件を確認
- `python scraper/generate_coverage_report.py` を実行し、取得カバレッジを再生成
- カバレッジは完全未取得1件（トモダチコレクション Switch 2）、取得業者数1の商品24件で維持

## 2026-05-31

- 日次自動確認を実施
- `data/prices.csv` と `docs/prices.csv` は同期済み、`data/last_scrape.txt` と `docs/last_scrape.txt` はどちらも `2026-05-31`
- `data/raw/20260531_121703_*.csv` が追加5業者分保存されていることを確認
- raw確認では、モバイル一番 iPhone 17 Pro系21商品、買取ホムラ iPhone 17 Pro系9商品がJAN欠けなし
- 今日分の `prices.csv` は146行。価格変化追記方式のため、今日の日付だけではiPhone全商品数を判定しない
- `logs/scraper.log` に2026-05-31分のERROR/Traceback/失敗/failedはなし
- `python scraper/generate_coverage_report.py` を実行し、取得カバレッジを再生成
- カバレッジは完全未取得1件（トモダチコレクション Switch 2）、取得業者数1の商品24件で維持
