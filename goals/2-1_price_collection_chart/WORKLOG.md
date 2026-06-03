# 2-1. 買取価格収集・チャート表示 WORKLOG

## 2026-06-03 日次スクレイピング確認

- `data/prices.csv` / `docs/prices.csv` は同期済み。最新日付は `2026-06-03`、当日行は208件。
- 当日行の内訳は、買取一丁目61件、森森買取54件、買取ルデヤ29件、買取ホムラ27件、モバイル一番15件、買取商店8件、ヤフオク中央値7件、ヤフオク最高5件、ヤフオク最安2件。
- 追加5業者の当日行は133件、JAN欠けは0件。
- `data/raw/20260603_121704_*.csv` に追加5業者のraw保存あり。モバイル一番 iPhone 21商品、買取ホムラ iPhone 9商品はいずれもJAN欠け0件。
- `logs/scraper.log` の2026-06-03分に ERROR / Traceback / failed / Exception は0件。
- ヤフオク実データは取得済みだが、スクリプトの完了マーカーが `data/last_scrape_yahoo.txt` を書いており、運用側の `data/last_yahoo_scrape.txt` と不一致だった。
- `scraper/scrape_yahoo.py` の完了マーカーを `data/last_yahoo_scrape.txt` に統一し、`data/last_yahoo_scrape.txt` / `docs/last_yahoo_scrape.txt` を `2026-06-03` に整合。
- `python scraper/generate_coverage_report.py` を実行し、`reports/coverage_matrix.md` / `reports/coverage_matrix.csv` を更新。
- カバレッジは取得業者数0の商品1件（`トモダチコレクション Switch 2`）、取得業者数1の商品24件、前回比悪化0件。

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

## 2026-06-01

- 日次自動確認を実施
- `data/prices.csv` と `docs/prices.csv` は同期済み、`data/last_scrape.txt` と `docs/last_scrape.txt` はどちらも `2026-06-01`
- `data/raw/20260601_121703_*.csv` が追加5業者分保存されていることを確認
- raw確認では、モバイル一番 iPhone 17 Pro系21商品、買取ホムラ iPhone 17 Pro系9商品がJAN欠けなし
- 今日分の `prices.csv` は153行。追加5業者の今日分追記は79行、JAN欠け0件
- `logs/scraper.log` に2026-06-01分のERROR/Traceback/失敗/failedはなし
- 公開CSVは2026-06-01分153行を返すことを確認
- `python scraper/generate_coverage_report.py` を実行し、取得カバレッジを再生成
- カバレッジは完全未取得1件（トモダチコレクション Switch 2）、取得業者数1の商品24件で維持
- モバイル一番の取得実績は52件から53件へ増加

## 2026-06-01 商品名正規化

- 買取一丁目APIからJAN別の商品名を取得し、既存JAN付き商品名205件を買取一丁目側の名称へ正規化
- `scraper/products.py`、`docs/index.html`、`scraper/scrape_yahoo.py`、`scraper/scrape_msrp.py` の商品名キーを更新
- `data/prices.csv` / `docs/prices.csv` / `data/msrp.csv` / `docs/msrp.csv` の `product_name` を一括置換し、作業前バックアップを `.bak_20260601_212413` として保存
- `data/prices.csv` と `docs/prices.csv`、`data/msrp.csv` と `docs/msrp.csv` がバイト単位で一致することを確認
- `python -m py_compile scraper\products.py scraper\scrape.py scraper\scrape_yahoo.py scraper\scrape_msrp.py scraper\generate_coverage_report.py` 成功
- `python scraper\generate_coverage_report.py` 成功
- ローカル `http://localhost:8010/` で旧名の `Switch 新型ネオン` / `PlayStation5 Pro` が消え、買取一丁目側名称で表示されることを確認
- 買取一丁目名に含まれていた13桁JANを商品名から除去。JAN列・下段表示は維持
- 対象は41商品、`prices.csv` 375行、`msrp.csv` 41行。作業前バックアップを `.bak_20260601_215426` として保存
- マスタ・CSV内の商品名に13桁JANが残っていないこと、ローカル画面の商品リスト名にも13桁JANが出ないことを確認

## 2026-06-02 サブカテゴリタグ修正

- 買取一丁目名への正規化後、`Nintendo Switch` などのサブカテゴリが旧短縮名の `startsWith` 判定に依存していたため修正
- ゲーム、カメラ、ポケカ、ワンピのサブカテゴリ判定を新名称に合わせて更新
- ローカル `http://localhost:8010/` で `Nintendo Switch` 33件、`ゲームソフト` 15件、カメラ/ポケカ主要タグが空にならないことを確認

## 2026-06-02 日次スクレイピング確認

- `data/last_scrape.txt` / `docs/last_scrape.txt` / `data/last_yahoo_scrape.txt` / `docs/last_yahoo_scrape.txt` はすべて `2026-06-02`
- `data/prices.csv` と `docs/prices.csv` は同期済み。`data/msrp.csv` と `docs/msrp.csv` も同期済み
- `data/prices.csv` は全3233行、最新日付 `2026-06-02`、当日分281行
- 当日分の追加5業者は180行、JAN欠け0件
- `data/raw/20260602_121704_*.csv` は追加5業者分あり
- raw確認: モバイル一番 iPhone 17 Pro系21商品、買取ホムラ iPhone 17 Pro系9商品、どちらもJAN欠け0件
- `logs/scraper.log` の2026-06-02分にERROR/Traceback/失敗/failed/Exceptionは0件
- 公開CSV `https://makkinngami-cmd.github.io/sedori-navi/prices.csv` は全3233行、最新日付 `2026-06-02`
- `python scraper\generate_coverage_report.py` を実行し、カバレッジ表を再生成
- カバレッジ: 完全未取得1件（`トモダチコレクション Switch 2`）、取得業者数1の商品24件、前回比で悪化0件、改善8件
