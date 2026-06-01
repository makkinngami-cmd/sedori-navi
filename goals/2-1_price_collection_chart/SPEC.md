# 2-1. 買取価格収集・チャート表示 SPEC

## 目的

買取店・ヤフオク価格を日次で収集し、商品をJAN中心に統合し、GitHub Pagesのチャートで仕入れ・売却判断に使える状態を維持する。

## やること

- 買取一丁目、モバイル一番、買取ルデヤ、森森買取、買取ホムラ、買取商店、ヤフオクの価格を収集する。
- 追加5業者は業者別raw CSVを `data/raw/` に保存する。
- JANありデータを本番CSVへ統合する。
- `data/prices.csv` と `docs/prices.csv` の同期を維持する。
- `data/msrp.csv` と `docs/msrp.csv` の同期を維持する。
- GitHub Pagesで `docs/` の表示が更新される状態を維持する。
- `reports/coverage_matrix.csv` と `reports/coverage_matrix.md` で商品別・業者別の取得状況を見える化する。
- データ未取得時は、スクレイパー、タスク設定、ワークフローなど仕組み側を直す。

## やらないこと

- 手動でCSVを埋めて、取得できたことにしない。
- `data/raw/` を削除しない。
- `.bak_...` ファイルを削除しない。
- 2-2の在庫管理連携はこのゴールでは扱わない。
- freeeなど外部サービス連携はこのゴールでは扱わない。
- 商品追加や定価変更は、必要になった場合だけ対象ファイルと同期ルールを確認して実施する。

## データ方針

- 正本は `data/prices.csv`。
- 公開用コピーは `docs/prices.csv`。
- 表示は `docs/prices.csv` を読む。
- `prices.csv` は価格変化があった時だけ追記されるため、同日行だけで取得件数全体を判断しない。
- 当日の全取得確認は `data/raw/YYYYMMDD_*.csv` を使う。
- JANを優先して商品を統合する。
- JANがない行はrawに残し、本番CSVへ入れるかは慎重に判断する。

## 自動実行

- 主運用は Windows タスクスケジューラの `sedori-navi-scraper`。
- 実行時刻は毎日 12:17 JST。
- GitHub Actions はバックアップ扱い。
- 日次確認は `sedori-navi-daily-scrape-check`。

## 成功条件

- 今日の日付が `data/last_scrape.txt` と `docs/last_scrape.txt` に入っている。
- `data/prices.csv` と `docs/prices.csv` が同期している。
- 追加5業者のraw CSVが当日分として保存されている。
- 追加5業者の本番CSV候補にJAN欠けが混ざっていない。
- モバイル一番のiPhone 17 Pro系21商品がrawで取れている。
- 買取ホムラのiPhone 17 Pro系9商品がrawで取れている。
- 公開CSVが最新日付を返す。
- カバレッジ表が再生成され、悪化がない。
