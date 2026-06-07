# 2-1. 買取価格収集・チャート表示 HANDOFF

## 最新引き継ぎ 2026-06-07

### 現在地

- 日次スクレイピング、JAN統合、GitHub Pages向け `docs/` 反映は稼働中。
- Codexの日次確認オートメーションは停止済み。主運用は Windows タスクスケジューラの `run_scraper.ps1`。
- 商品追加フェーズ1として、買取一丁目の商品候補一覧とゲーム推薦表を作成済み。
- 候補一覧は保持中: `reports/ichome_product_candidates.csv` / `.md`、`reports/ichome_game_recommendations.csv` / `.md`。
- 初回追加として、`Nintendo Switch 2 Proコントローラー`、Portalブラック、A/B候補の通常版ゲームソフト30件を追加済み。
- 2026-06-07に仕組み側の強制スクレイプを実行し、追加商品が当日データへ入ることを確認済み。
- 追加商品のローカル表示は、Switch 2 Proコントローラー、Portalブラック、ドンキーコング バナンザで確認済み。
- `scraper/scrape_msrp.py` は `price_type` 列を保持し、Amazonタイトル不明時に採用しないよう修正済み。
- `data/prices.csv` と `docs/prices.csv`、`data/msrp.csv` と `docs/msrp.csv` は同期済み。

### 次にやること

1. 追加商品のブラウザ表示を最終確認する。
2. 新規ソフトの定価/MSRPを公式ページなど信頼できるソースで確認し、必要なら `data/msrp.csv` / `docs/msrp.csv` へ追加する。
3. 取得業者数が少ない新規PS5ソフトのキーワード精度と他業者取扱を確認する。
4. 次の追加候補は、既存候補一覧から分野別に選ぶ。候補一覧ファイルは捨てない。
5. フェーズ2として、買取一丁目だけを対象に価格上昇アラーム仕様を実装する。

### 未解決

- 新規ソフトのMSRPは未整備。自動取得だけでは誤値が混ざるため、公式ページなどで確認してから追加する。
- 新規PS5ソフトの一部は取得業者数1から2件で、実態確認が必要。
- 価格アラームは未実装。条件は「何%以上」「何円以上」「AND/OR/片方のみ」を画面で変更できる方針。

### 触ってはいけないもの

- `data/raw/` は削除しない。
- `.bak_...` ファイルは削除しない。
- 候補一覧 `reports/ichome_product_candidates.*` / `reports/ichome_game_recommendations.*` は捨てない。
- データ未取得時にCSVを手で埋めて終わらせない。仕組み側を確認する。
- 親フォルダ直下MDへ細かい作業ログを書き足さない。履歴は `WORKLOG.md` に書く。
