# 2-1. 買取価格収集・チャート表示 HANDOFF

## 最新引き継ぎ 2026-06-07

### 現在地

- 買取店・ヤフオク価格の日次収集、JAN統合、GitHub Pages反映は稼働中。
- 主運用は Windows タスクスケジューラの `run_scraper.ps1`。Codexの毎日確認オートメーションは停止済み。
- 直近確認では、2026-06-06の日次スクレイピング、追加5業者raw保存、JAN欠け0件、カバレッジ更新まで確認済み。
- フェーズ1の候補表作成スクリプト `scraper/generate_ichome_product_candidates.py` を追加済み。
- `reports/ichome_product_candidates.csv` / `reports/ichome_product_candidates.md` に買取一丁目の商品追加候補を生成済み。
- ゲーム分野は `scraper/generate_ichome_game_recommendations.py` で追加おすすめ候補を作成済み。
- `reports/ichome_game_recommendations.csv` / `reports/ichome_game_recommendations.md` に、ゲーム系未登録177件をS/A/B/保留へ分類済み。
- 次はゲーム分野のS/A候補を見て、初回追加対象にするか、ヤフオク・他業者確認を先に行うか決める。

### 次にやること

1. フェーズ1: `reports/ichome_game_recommendations.md` のS/A候補を確認する。
2. フェーズ1: 必要ならS候補からヤフオク落札実績・他業者取扱有無を確認し、追加対象をさらに絞る。
3. フェーズ1: 初回追加対象が決まったら、`scraper/products.py`、`docs/index.html`、必要に応じて `data/msrp.csv` / `docs/msrp.csv` へ反映する。
4. フェーズ1: 反映後に既存スクレイパーでJAN統合と表示を確認する。
5. フェーズ2: 買取一丁目だけを対象にした価格アラーム仕様を実装する。
6. フェーズ2: アラーム条件は画面で変更できるようにし、「％かつ円」「％または円」「％のみ」「円のみ」を扱う。

### 未解決

- `data/last_scrape_yahoo.txt` が過去の誤マーカーとして残っている。削除は未実施。
- 取得業者数0の商品 `トモダチコレクション Switch 2` と、取得業者数1の商品24件は、次フェーズの候補整理後に優先度を再確認する。
- 価格アラームはフェーズ1完了後に着手する。商品追加候補整理と同時に混ぜて実装しない。
- 候補表は未登録候補が多い。優先度Aでも518件あるため、一括追加せず初回追加範囲を決める。

### 触ってはいけないもの

- `data/raw/` は削除しない。
- `.bak_...` ファイルは削除しない。
- データ未取得時にCSVを手で埋めて完了扱いにしない。必ず仕組み側を確認する。
- 親フォルダ直下MDへ細かい作業ログを書き足さない。履歴は `WORKLOG.md` に書く。
