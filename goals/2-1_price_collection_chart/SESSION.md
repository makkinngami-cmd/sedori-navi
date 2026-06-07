# 2-1. 買取価格収集・チャート表示 セッション指示

## 担当範囲

買取店・ヤフオク価格を毎日収集し、JAN統合・公開ページ反映・チャート表示を安定稼働させる。

## 作業開始時に読むもの

1. `C:\Users\makki\sedori-navi\CLAUDE.md`
2. この `SESSION.md`
3. `C:\Users\makki\sedori-navi\goals\2-1_price_collection_chart\SPEC.md`
4. `C:\Users\makki\sedori-navi\goals\2-1_price_collection_chart\HANDOFF.md`
5. 必要に応じて `OPERATIONS.md`
6. 必要に応じて対象スクリプト

## 作業後に更新するもの

- 朝レポート用: `C:\Users\makki\sedori-navi\STATUS.md` の2-1関連部分。進捗は数字だけ。長文や詳細ログは書かない。
- 引き継ぎ用: このフォルダの `HANDOFF.md`。現在地・次にやること・未解決・触ってはいけないものだけを書く。
- 作業ログ: このフォルダの `WORKLOG.md`。古い経緯、完了済み作業、調査ログを書く。
- 仕様と担当範囲: このフォルダの `SPEC.md`。何をやるか・やらないかを書く。

## 日次スクレイプ＆カバレッジ確認（自動）

`run_scraper.ps1`（Windowsタスクスケジューラ 毎日12:17）が以下を自動実行する：
1. `scraper/scrape.py` — 買取店スクレイプ
2. `scraper/scrape_yahoo.py` — ヤフオク落札価格
3. `data/` → `docs/` コピー＆git push
4. `scraper/generate_coverage_report.py` — `reports/coverage_matrix.md/csv` 更新

**Codex automation（daily scrape and coverage check）は停止済み。通常の日次取得はWindowsタスクスケジューラで確認する。**

問題確認が必要なときはログを見る：
```powershell
Get-Content "C:\Users\makki\sedori-navi\logs\scraper.log" -Tail 50
```

## 注意事項

- データが取れていないとき、手動でCSVを埋めて終わりにしない
- `data/raw/` は削除しない
- `data/` と `docs/` のCSV同期に注意
- `HANDOFF.md` に古い完了済み情報や過去のバグ詳細を残さない。必要な履歴は `WORKLOG.md` に要約する
- 親フォルダ直下MDへ細かい作業内容を書き足さない
