# 2-1. 買取価格収集・チャート表示 HANDOFF

## 次回見ること

- 2026-05-31以降の日次データが正常に収集・保存されているか
- モバイル一番の価格が毎日取れているか
- JAN未取得商品の改善余地
- rawと未マッチログから未統合商品がないか

## 未解決・注意

- GitHub Pagesが古いCSVを返す場合はDeploy GitHub Pagesを確認する
- 詳細な作業ログ・判断ログは親フォルダ直下MDへ増やさず、このフォルダの `WORKLOG.md` に記録する
- 引き継ぎはこの `HANDOFF.md` に集約し、`STATUS.md` は朝レポート用の2-1サマリーだけにする
- 2026-05-30はGitHub Actionsが先に当日マーカーを作り、ローカル `scrape.py` がスキップしたため raw が残らなかった。ローカル `run_scraper.ps1` に `SEDORI_FORCE_SCRAPE=1` を追加して対処済み
- `run_scraper.ps1` はローカル固有の未追跡ファイル。次回、12:17の通常実行で `data/raw/YYYYMMDD_*.csv` が自動生成されるか確認する
- 2026-05-31の通常実行では `data/raw/20260531_121703_*.csv` が生成済み。モバイル一番iPhone21商品、買取ホムラiPhone9商品もrawで確認済み
