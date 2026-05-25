# sedori-navi Operations

## 目的

sedori-navi は、買取業者とヤフオクの価格を日次で収集し、GitHub Pages のブラウザ画面で価格推移・買取率・定価比較を確認するための運用システム。

このメモは、スクレイピング対象、データ保存ルール、自動実行、監視、今後の作業方針を残すための運用ノート。

## 現在のスクレイピング対象

本番CSVへ反映する対象:

- 買取一丁目
- モバイル一番
- 買取ルデヤ
- 森森買取
- 買取ホムラ
- 買取商店
- ヤフオク

追加5業者は、まず業者別 raw CSV に保存し、そのうち JAN がある行だけ本番CSVへ統合する。

## データ保存ルール

本番データ:

- `data/prices.csv`
- `docs/prices.csv`

ブラウザ表示は `docs/prices.csv` を読む。`run_scraper.ps1` が `data/prices.csv` を `docs/prices.csv` にコピーする。

追加業者の raw データ:

- `data/raw/{timestamp}_{store}.csv`

raw CSV は業者ごとの元データ確認用。業者追加やスクレイパー修正時に、元データを壊さないために残す。

バックアップ:

- 大きなCSV変更前は `.bak_YYYYMMDD_HHMMSS` を作成する。
- 不要になっても、削除はユーザー確認後に行う。

## JAN照合ルール

業者ごとに商品名がバラバラなので、商品統合は JAN を優先する。

ルール:

- JAN が取れた商品は JAN でのみ照合する。
- JAN がない商品だけ、商品名キーワードでフォールバック照合する。
- 追加5業者については、本番CSV統合は JAN あり行だけに限定する。
- JAN なし行は raw CSV に残し、本番CSVには入れない。

理由:

- 誤った商品名マッチで価格履歴を壊さないため。
- 業者追加のたびに既存データが混ざるリスクを下げるため。

## 自動実行

ローカル実行:

- Windows タスクスケジューラ
- タスク名: `sedori-navi-scraper`
- 実行時刻: 毎日 12:17 JST
- 実行ファイル: `run_scraper.ps1`

`run_scraper.ps1` の流れ:

1. `scraper/scrape.py`
2. `scraper/scrape_yahoo.py`
3. `data/prices.csv` を `docs/prices.csv` にコピー
4. `data/msrp.csv` を `docs/msrp.csv` にコピー
5. `last_scrape.txt` を `docs` にコピー
6. 変更があれば git commit / push

GitHub Actions バックアップ:

- `.github/workflows/scrape.yml`
- cron: `17 3 * * *`
- JST 12:17 相当

## 日次監視

Codex heartbeat automation:

- ID: `sedori-navi-daily-scrape-check`
- 実行時刻: 毎日 12:45 JST

確認対象:

- `logs/scraper.log`
- `data/prices.csv`
- `docs/prices.csv`
- `data/raw/`
- `data/last_scrape.txt`
- `docs/last_scrape.txt`

確認すること:

- 今日の日付のデータが入っているか。
- 追加5業者の JAN ありデータが本番CSVに統合されているか。
- raw CSV が業者別に保存されているか。
- JAN なし行が本番CSVに混ざっていないか。
- エラーが出ていないか。

失敗時の方針:

- 手動でCSVを埋めて終わりにしない。
- 原因を調査し、スクレイパー・タスク設定・ワークフローなど仕組み側を直す。
- 修正後にテストし、仕組みでデータが取れる状態までPDCAを回す。
- 削除、外部サービス更新、pushなど影響の大きい操作はユーザー確認を取る。

## 定価データの扱い

定価データ:

- `data/msrp.csv`
- `docs/msrp.csv`

画面側は `effective_date <= 表示日` の中で最新の定価を使う。値上げ・値下げがある場合、既存行を上書きせず、新しい `effective_date` の履歴行を追加する。

例:

- 旧定価: `2000-01-01`
- 新定価: `2026-05-25`

2026-05-25 に追加した Switch 系の定価履歴:

- Switch2 国内版: 59,980
- Switch2 多言語版: 69,980
- Switch2 国内版マリカーセット: 53,980
- Switch 有機EL: 47,980
- Switch 新型: 43,980
- Switch Lite: 29,980

注意:

- `scraper/scrape_msrp.py` は一回限り実行前提の定価スクレイパー。
- 既存定価がある商品は基本スキップするため、価格改定の自動検知には向いていない。
- 定価改定は公式情報を確認し、履歴行として追加する。

## ブラウザ表示ルール

表示ファイル:

- `docs/index.html`

現在の表示方針:

- チャート上部のチェック欄でプロットを表示/非表示にする。
- Chart.js 標準凡例は非表示。
- 定価だけ破線スウォッチ。
- その他の業者は丸スウォッチ。
- 買取商店は白い丸。
- ヤフオク中央値は黄色の丸。
- CSVキャッシュ回避は `Date.now()` を使う。

## 既知の注意点

- `data/raw/` は業者別元データ確認用なので、不要でも勝手に削除しない。
- `.bak_...` ファイルも削除前に確認する。
- `.claude/` と `run_scraper.ps1` は未追跡ファイルとして存在するが、勝手に削除しない。
- `docs/index.html` は文字化けして見える箇所があるが、既存状態なので不要に触らない。
- GitHub Actions はバックアップ扱い。主運用は Windows タスクスケジューラ。

## 次にやること

優先度高:

- 2026-05-26 12:45 の日次確認で、追加5業者が自動統合されるか検証する。
- 取れていない業者があれば、ログと raw CSV から原因を調査し、仕組み側を修正する。
- モバイル一番は継続して安定取得できるか重点確認する。

優先度中:

- JAN なし raw 行の一覧を定期的に確認し、JAN取得方法を改善できる業者を洗い出す。
- `scrape_msrp.py` を、価格改定検知にも使える設計へ見直す。
- UIの色・線種は、ユーザー指示の対象だけを変更する。

運用原則:

- 元データを壊さない。
- 本番CSVには JAN で確実に照合できたものを入れる。
- 手動修正で終わらせず、再発しない仕組みに直す。
