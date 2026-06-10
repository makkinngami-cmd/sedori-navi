# 2-1. 買取価格収集・チャート表示 WORKLOG

## 2026-06-07 方針決定

- 次の重点は、買取一丁目の商品を増やすことと、買取一丁目価格の異常上昇・値上げ候補を検知することに決定。
- 商品追加は、買取一丁目を商品マスターの親として扱い、まず商品一覧をスクレイピングして未登録候補表を作る方針にした。
- 候補表ではJANあり商品を優先し、JANなし商品は正式追加を慎重に判断する。
- 正式追加は候補表を見て優先順位を決めてから行う。いきなり `products.py` へ大量追加しない。
- 価格アラームは初期スコープを買取一丁目だけに絞る。複数業者横断の判定はやや複雑になるため後回し。
- アラーム条件はせどりナビ画面で変更可能にし、「何％以上かつ何円以上」「何％以上または何円以上」「何％以上のみ」「何円以上のみ」を扱う方針。
- 商品追加候補整理と価格アラームは別タスクとして分けることにした。先にフェーズ1として買取一丁目の商品一覧から未登録候補表を作り、その結果を見てからフェーズ2として価格アラームを実装する。
- Git整理として、`.claude/`、`data/raw/`、`.bak_*`、一時レポートを `.gitignore` 対象にした。削除ではなくGit追跡対象外への整理。
- `run_scraper.ps1` は日次運用に必要なため追跡対象にする方針。文字化けで壊れていたカバレッジ確認・ログ確認ブロックをASCIIログへ整理し、PowerShell構文チェックを通した。

## 2026-06-07 買取一丁目商品追加候補表

- `scraper/generate_ichome_product_candidates.py` を追加。
- 買取一丁目の通常商品APIとスマートフォンAPIを巡回し、既存商品をJAN・商品名で照合する候補表生成に対応。
- `reports/ichome_product_candidates.csv` に全件、`reports/ichome_product_candidates.md` にサマリーと優先候補を出力。
- 2026-06-07実行結果は、取得商品1596件、既存登録済み235件、未登録候補1361件。
- 未登録候補の優先度は、A 518件、B 812件、C 31件。Aはゲーム、スマートフォン、カード系、既存で扱う系統に近いカメラ商品を初回候補として抽出。
- 商品名にJANが含まれる場合は、候補表上では商品名とJAN列を分離するようにした。
- `python -m py_compile scraper\generate_ichome_product_candidates.py scraper\scrape.py scraper\generate_coverage_report.py` 成功。
- 商品マスターやCSV本体への追加は未実施。次に候補表を見て初回追加範囲を決める。

## 2026-06-07 ゲーム分野おすすめ候補

- 分野別調査の第1弾として、ゲーム系だけを抽出する `scraper/generate_ichome_game_recommendations.py` を追加。
- `reports/ichome_product_candidates.csv` の未登録候補から、カテゴリ `ゲーム` / `Steam Deck` の177件を対象にした。
- `reports/ichome_game_recommendations.csv` に全件、`reports/ichome_game_recommendations.md` にS/A候補を出力。
- 推薦分類は S 13件、A 26件、B 31件、保留107件。
- Sは携帯PC/Steam Deck、PS5限定・同梱本体、PlayStation限定品、Switch2本体セットを中心にした。
- AはXbox本体/上位周辺機器、Switch限定本体、PlayStation周辺機器、Switch2 Editionソフトを中心にした。
- JANなし候補は保留に落とした。Switch2ソフトはSではなくA扱いに調整。
- 実際の追加前に、ヤフオク落札実績、他業者取扱有無、取引予定の有無を確認する。

## 2026-06-06 日次スクレイピング確認

- `data/prices.csv` / `docs/prices.csv` は同期済み。最新日付は `2026-06-06`、当日行は140件。
- `data/last_scrape.txt` / `docs/last_scrape.txt` / `data/last_yahoo_scrape.txt` / `docs/last_yahoo_scrape.txt` はすべて `2026-06-06`。
- 当日行の内訳は、森森買取51件、買取一丁目28件、買取ルデヤ23件、買取商店16件、モバイル一番13件、買取ホムラ7件、ヤフオク中央値1件、ヤフオク最安1件。
- 追加5業者の当日行は110件、JAN欠けは0件。
- `data/raw/20260606_121705_*.csv` に追加5業者のraw保存あり。モバイル一番 iPhone 21商品、買取ホムラ iPhone 9商品はいずれもJAN欠け0件。
- `logs/scraper.log` の2026-06-06分に ERROR / Traceback / failed / Exception は0件。
- `python scraper/generate_coverage_report.py` を実行し、`reports/coverage_matrix.md` / `reports/coverage_matrix.csv` を更新。
- カバレッジは取得業者数0の商品1件（`トモダチコレクション Switch 2`）、取得業者数1の商品24件、前回比悪化0件、改善0件。

## 2026-06-05 日次スクレイピング確認

- `data/prices.csv` / `docs/prices.csv` は同期済み。最新日付は `2026-06-05`、当日行は134件。
- `data/last_scrape.txt` / `docs/last_scrape.txt` / `data/last_yahoo_scrape.txt` / `docs/last_yahoo_scrape.txt` はすべて `2026-06-05`。
- 当日行の内訳は、森森買取38件、買取ルデヤ29件、買取一丁目24件、買取ホムラ20件、買取商店8件、モバイル一番5件、ヤフオク最安5件、ヤフオク中央値3件、ヤフオク最高2件。
- 追加5業者の当日行は100件、JAN欠けは0件。
- `data/raw/20260605_121704_*.csv` に追加5業者のraw保存あり。モバイル一番 iPhone 21商品、買取ホムラ iPhone 9商品はいずれもJAN欠け0件。
- `logs/scraper.log` の2026-06-05分に ERROR / Traceback / failed / Exception は0件。
- `python scraper/generate_coverage_report.py` を実行し、`reports/coverage_matrix.md` / `reports/coverage_matrix.csv` を更新。
- カバレッジは取得業者数0の商品1件（`トモダチコレクション Switch 2`）、取得業者数1の商品24件、前回比悪化0件、改善0件。

## 2026-06-04 日次スクレイピング確認

- `data/prices.csv` / `docs/prices.csv` は同期済み。最新日付は `2026-06-04`、当日行は181件。
- 当日行の内訳は、買取一丁目44件、買取ホムラ39件、森森買取36件、買取ルデヤ23件、モバイル一番14件、買取商店13件、ヤフオク最安5件、ヤフオク中央値4件、ヤフオク最高3件。
- 追加5業者の当日行は125件、JAN欠けは0件。
- `data/raw/20260604_121704_*.csv` に追加5業者のraw保存あり。モバイル一番 iPhone 21商品、買取ホムラ iPhone 9商品はいずれもJAN欠け0件。
- `logs/scraper.log` の2026-06-04分に ERROR / Traceback / failed / Exception は0件。
- `data/last_yahoo_scrape.txt` は `2026-06-04` だったが、`docs/last_yahoo_scrape.txt` が `2026-06-03` のままだった。
- 原因は `run_scraper.ps1` が `data/last_yahoo_scrape.txt` を `docs/` にコピーせず、旧名 `data/last_scrape_yahoo.txt` を `git add` していたこと。
- `run_scraper.ps1` を修正し、`data/last_yahoo_scrape.txt` / `docs/last_yahoo_scrape.txt` をコピー・git add対象にした。PowerShell構文チェックは成功。
- `docs/last_yahoo_scrape.txt` を `2026-06-04` に同期。
- `python scraper/generate_coverage_report.py` を実行し、`reports/coverage_matrix.md` / `reports/coverage_matrix.csv` を更新。
- カバレッジは取得業者数0の商品1件（`トモダチコレクション Switch 2`）、取得業者数1の商品24件、前回比悪化0件、改善2件（PS5系2件）。

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

## 2026-06-07 選定ゲーム商品追加

- 事前に作成した候補一覧 `reports/ichome_product_candidates.*` と `reports/ichome_game_recommendations.*` は削除・再生成せず保持した
- 既存の `Switch2 Proコン` を `Nintendo Switch 2 Proコントローラー` に名称変更し、JAN `4902370552843` を付与
- `PlayStation Portal リモートプレーヤー ブラック CFIJ-18001` と、A/B候補の通常版ゲームソフト30件を商品マスターへ追加
- 限定品は仕入れにくいという方針のため、30周年Portalや限定Proコントローラーは今回追加対象から外した
- `scraper/products.py`、`docs/index.html`、`scraper/scrape_yahoo.py`、`scraper/scrape_msrp.py` を更新
- `data/msrp.csv` / `docs/msrp.csv` にPortalブラックの参考価格 `39980` を追加。新規ソフトのMSRPは次回以降に確認する
- `data/prices.csv` / `docs/prices.csv` / `data/msrp.csv` / `docs/msrp.csv` 内の旧名 `Switch2 Proコン` を新名へ置換
- `SEDORI_FORCE_SCRAPE=1 python scraper/scrape.py` を実行し、2026-06-07分として131件の価格変化を仕組み側で追記
- `data/raw/20260607_223902_*.csv` が保存されたことを確認
- `data/prices.csv` と `docs/prices.csv`、`data/last_scrape.txt` と `docs/last_scrape.txt` を同期
- `python scraper/generate_coverage_report.py` を実行し、`reports/coverage_matrix.md` / `reports/coverage_matrix.csv` を更新
- `python -m py_compile scraper\products.py scraper\scrape.py scraper\scrape_yahoo.py scraper\scrape_msrp.py scraper\generate_coverage_report.py` 成功
- 商品マスターは272件。重複商品名0件、重複JAN0件、旧名 `Switch2 Proコン` 0件を確認
- 2026-06-07分の取得確認: `Nintendo Switch 2 Proコントローラー` は5業者、Portalブラックは4業者、NS2追加系18商品、PS5追加系12商品が取得対象に入った
- 取得業者数が少ない新規PS5ソフトが残るため、次回以降にヤフオク/他業者の取扱・キーワード精度を確認する

## 2026-06-07 追加商品の表示・MSRP確認

- ローカル `http://localhost:8010/` で `Nintendo Switch 2 Proコントローラー`、Portalブラック、`【NS2】ドンキーコング バナンザ` の検索・表示・選択を確認
- 新規ソフトはMSRP未登録のため、買取率が `—` になることを確認
- `python scraper\scrape_msrp.py` を試行したが、Amazonフォールバックでタイトル照合が空のまま価格を採用する例と、`price_type` 列を落としてCSVを書き換える副作用を確認
- 上記の自動取得結果は採用せず `data/msrp.csv` を元に戻した
- `scraper/scrape_msrp.py` を修正し、`price_type` 列を保持し、Amazonの検索結果タイトルが取れない場合は採用しないようにした
- 任天堂公式で確認できた新規NS2ソフト8件のMSRPを `data/msrp.csv` / `docs/msrp.csv` に追加
- パッケージ版がある商品は、せどり用途に合わせてパッケージ版の希望小売価格を基準にした
- ローカル画面で `【NS2】ドンキーコング バナンザ` の買取率が `74.6%`、定価が `¥8,980` と表示されることを確認
- 残りの新規ソフトMSRPは、公式ページなど信頼できるソース確認後に追加する

## 2026-06-08 日次スクレイピング・MSRP確認

- `data/last_scrape.txt` / `docs/last_scrape.txt` はどちらも `2026-06-08`。
- `data/prices.csv` / `docs/prices.csv` は最新日付 `2026-06-08`、当日分189行、82商品、9ストアを確認。
- `logs/scraper.log` では `scrape_yahoo.py`、`copy to docs/`、`generate_coverage_report.py` まで完了。自動commit後、push前rebaseで `data/prices.csv` などが競合して失敗したログを確認。
- 現在のGit状態は `main...origin/main [ahead 9, behind 2]`、作業ツリーclean。push前にユーザー確認が必要。
- 2026-06-08表示対象のNS2/PS5ソフト18件を確認し、MSRP未登録10件を公式ソースで確認して `data/msrp.csv` / `docs/msrp.csv` に追加。
- NS2追加: `【NS2】あつまれ どうぶつの森 Nintendo Switch 2 Edition` 7,128円、任天堂公式商品情報。パッケージ版基準。
- NS2追加: `【NS2】ぽこ あ ポケモン` 8,980円、ポケモン公式商品情報。パッケージ版（キーカード）/ダウンロード版同額。
- NS2追加: `【NS2】カービィのエアライダー` 8,980円、任天堂公式ページ。ダウンロード版7,980円、パッケージ版8,980円のため、せどり用途に合わせてパッケージ版基準。
- NS2追加: `【NS2】ゼノブレイドクロス ディフィニティブエディション Nintendo Switch 2 Edition` 8,228円、任天堂公式ページ。ダウンロード版8,150円、パッケージ版8,228円のため、パッケージ版基準。
- NS2追加: `【NS2】ゼルダ無双 封印戦記/Switch 2` 8,980円、GAMECITY公式通常版。
- PS5追加: `【PS5】Ghost of Yotei` 8,980円、PlayStation公式/PS Store通常価格。
- PS5追加: `【PS5】SILENT HILL f` 8,580円、PlayStation公式/PS Store通常価格。セール中表示は採用せず通常価格を採用。
- PS5追加: `【PS5】アストロボット` 7,980円、PlayStation公式/PS Store通常価格。
- PS5追加: `【PS5】プラグマタ` 7,990円、PlayStation公式/PS Store通常価格。
- PS5追加: `【PS5】仁王3` 9,680円、PlayStation公式/PS Store通常価格。セール中表示は採用せず通常価格を採用。
- 反映後、2026-06-08表示対象のNS2/PS5ゲームソフト18件はMSRP未登録0件になったことを確認。

## 2026-06-08 PS5ソフト取得精度確認

- 次にやることの優先順を、1. PS5取得精度確認、2. 次分野の追加候補整理、3. 買取一丁目価格アラームへ整理した。
- 2026-06-08表示対象のPS5ソフトは5件。`Ghost of Yotei` は買取店2件＋ヤフオク3指標、`アストロボット` は買取一丁目＋ヤフオク3指標、`SILENT HILL f` / `プラグマタ` / `仁王3` はヤフオク3指標のみだった。
- 2026-06-08のヤフオクで、`SILENT HILL f` 660円、`アストロボット` 800円、`プラグマタ` 700円、`仁王3` 600円など、ソフト本体ではなく特典・DLC・関連品と思われる低額落札が混ざることを確認。
- 既存の `prices.csv` から該当行を削除するのは既存データ変更になるため今回は実施せず、今後の取得対策として `scraper/scrape_yahoo.py` の `PRICE_FLOORS` にPS5ソフト別の最低価格を追加した。
- 最低価格はおおむねMSRPの35%前後を目安にし、Minecraftなど低単価ソフトは個別に低めにした。
- `python -m py_compile scraper\scrape_yahoo.py` 成功。
- 2026-06-08の既存行に対するシミュレーションで、`仁王3` 600円、`SILENT HILL f` 660円、`プラグマタ` 700円、`アストロボット` 800円のヤフオク行が次回以降フィルタ対象になることを確認。

## 2026-06-08 カメラ候補整理

- 買取一丁目候補表 `reports/ichome_product_candidates.csv` からカメラ分野を確認。カメラ候補は980件、未登録候補は912件。
- 既存登録済みカメラは70件程度あり、X100VI、GR IV Black/Monochrome、G7X、SX740、PowerShot V1、Z50II、TAMRON一部などはすでにせどりナビに入っていることを確認。
- `scraper/generate_ichome_camera_recommendations.py` を追加し、カメラ候補をS/A/B/保留へ分類する仕組みを作成。
- 生成物: `reports/ichome_camera_recommendations.csv`、`reports/ichome_camera_recommendations.md`、`reports/ichome_camera_shortlist.csv`。
- 分類結果: カメラ未登録候補912件、S 14件、A 117件、B 157件、保留624件。
- 初回確認用の短表は20件。最優先は、X100V、GR IV HDF、GR IIIx/GR III HDF、GR III Street Edition、RX100M7/M6/M5A。優先はPowerShot G5 X Mark IIとPowerShot V10色違い。次点はX-E5、X-M5、Z5II、Z6IIIのボディ。
- `python -m py_compile scraper\generate_ichome_camera_recommendations.py` 成功。
- ユーザー確認後、短表20件を `scraper/products.py` と `docs/index.html` にカメラ商品として追加。
- 追加20件はJAN付き。`data/msrp.csv` / `docs/msrp.csv` には買取一丁目候補価格を初期の市場基準 `price_type=market` として追加。
- `scraper/scrape_yahoo.py` に20件の短いヤフオク検索語と、アクセサリー混入を避ける最低価格フィルタを追加。
- `python -m py_compile scraper\products.py scraper\scrape_yahoo.py scraper\generate_ichome_camera_recommendations.py` 成功。
- 追加20件について、商品マスター・MSRP・公開カテゴリへの登録漏れ0件、商品名重複0件、`data/msrp.csv` と `docs/msrp.csv` の同期を確認。
- 追加20件を確認するため、`SEDORI_FORCE_SCRAPE=1 python scraper\scrape.py` を実行。`data/prices.csv` に99件追記。
- ヤフオクは全件再取得ではなく、追加カメラ20件だけを対象に `scraper/scrape_yahoo.py` の関数を使って取得。`◆DSC-RX100M7` のヤフオク3指標を追記。
- `data/prices.csv` / `docs/prices.csv` と `data/msrp.csv` / `docs/msrp.csv` を同期し、`python scraper\generate_coverage_report.py` を実行。
- 2026-06-08当日分は359行、140商品。追加カメラ20件は全件価格取得あり。
- 複数店取得あり: X100V、GR IV/GR III HDF、RX100M7/M5A、PowerShot G5 X Mark II、PowerShot V10色違い。
- 買取一丁目のみ: `RICOH GR III Street Edition`、`FUJIFILM X-E5` 2色、`FUJIFILM X-M5` 2色、`Nikon Z5II ボディ`、`Nikon Z6III ボディ`。

## 2026-06-09 日次スクレイピング確認の訂正

- 2026-06-09の日次スクレイピングは実行済み。`data/prices.csv` / `docs/prices.csv` は同期済みで、2026-06-09分は177行、99商品。
- 一時的に「追加カメラ20件の今日行が少ないため未取得」と判断したが、これは誤り。CSVは価格変化ログ方式で、前回と同じ価格の商品は今日行が増えない。
- 価格保存方式は「前回と価格が変わった商品だけ追記」が正しい。誤って入れた日次観測追記コミット `0f95b1e` は `c9d819d` で取り消し済み。
- 追加カメラ20件は、最新価格データとして20/20件存在する。ブラウザは最新価格を表示するため、今日行の有無だけで表示可否を判断しない。

## 2026-06-09 カメラ買取一丁目のみ商品の確認

- 追加カメラ20件のうち、`docs/prices.csv` 上で買取一丁目のみのままの8件を確認: `FUJIFILM X-E5 ボディ [ブラック]`、`FUJIFILM X-E5 ボディ [シルバー]`、`FUJIFILM X-M5 ボディ [シルバー]`、`FUJIFILM X-M5 ボディ [ブラック]`、`RICOH GR III Street Edition`、`Nikon Z5II ボディ`、`Nikon Z6III ボディ`、`SONY DSC-RX100M6`。
- 上記8件はいずれも最新価格が2026-06-08の買取一丁目行。ヤフオク行は0件。
- `data/raw/20260609_*.csv` を対象にJANと型番断片（X-E5、X-M5、Z5II、Z6III、RX100M6、Street Edition）で確認したが、他店rawには対象ヒットなし。
- 2026-06-09のヤフオク実行ログでは、X-E5/X-M5/Z5II/Z6III/RX100M6は落札データなし。`RICOH GR III Street Edition` は候補1件中マッチなしで、価格CSVへは追加されていない。
- `RICOH GR III Street Edition` のJANは `4549212302763`。`4549212304507` は別のGR系商品と混同しない。
- 現時点では仕組みの修正や商品データ追加は不要。他店・ヤフオクに出てきたら次回以降のスクレイピング結果で拾う方針。

## 2026-06-09 ポケカ/ワンピ候補整理

- カメラの次分野として、買取一丁目候補表 `reports/ichome_product_candidates.csv` からポケカ/ワンピを確認。
- `scraper/generate_ichome_card_recommendations.py` を追加し、カード系候補を追加候補/要確認/保留へ分類する仕組みを作成。
- 生成物: `reports/ichome_card_recommendations.csv`、`reports/ichome_card_recommendations.md`、`reports/ichome_card_shortlist.csv`。
- 分類結果: カード系未登録候補19件、ポケカ7件、ワンピ12件。追加候補16件、要確認2件、保留1件。
- 追加候補は、ポケカのスペシャルBOX/デラックスBOX/単価ありBOX 6件と、ワンピの高単価BOX 10件。
- 要確認は `【OP-07】500年後の未来`、`【OP-08】二つの伝説`。保留は低単価の `【MEGA】スタートデッキ100 バトルコレクション`。
- カード系は定価/MSRPではなく、市場価格基準 `price_type=market` で扱う方針。商品マスターへの追加はまだ未実施。
- `python -m py_compile scraper\generate_ichome_card_recommendations.py` 成功。

## 2026-06-09 ポケカS/A候補追加

- ユーザー依頼により、カード短表のS/Aだけを追加対象にした。今回はポケカ6件のみで、ワンピB候補は未追加。
- 追加した商品: `ポケモンセンター スペシャルBOX ヒロシマ`、`ポケモンセンター スペシャルBOX フクオカ`、`【S＆V】ブラックボルト デラックス BOX`、`【S＆V】ホワイトフレア デラックス BOX`、`ポケモンセンター スペシャルBOX トウホク`、`【MEGA】 アビスアイ BOX`。
- `scraper/products.py` と `docs/index.html` にポケカ商品として追加。`data/msrp.csv` / `docs/msrp.csv` には買取一丁目候補価格を市場価格基準 `price_type=market` として追加。
- ポケカ/ワンピは既存仕様で `scraper/scrape_yahoo.py` と `scraper/scrape_msrp.py` の対象外カテゴリのため、ヤフオク検索語と公式MSRP取得は追加していない。
- `python -m py_compile scraper\products.py scraper\scrape.py scraper\scrape_msrp.py scraper\scrape_yahoo.py` 成功。
- `SEDORI_FORCE_SCRAPE=1 python scraper\scrape.py` を実行し、仕組み経由で `data/prices.csv` に2026-06-09分104件の価格変化を追記。`docs/prices.csv` へ同期し、`python scraper\generate_coverage_report.py` も実行。
- 追加6件はすべて2026-06-09価格を取得済み。ヒロシマ/フクオカ/トウホクは買取一丁目＋モバイル一番、ブラックボルトDX/ホワイトフレアDXは買取一丁目＋森森買取、アビスアイは買取一丁目/モバイル一番/森森買取/買取ルデヤ/買取ホムラで取得。
- `data/prices.csv` と `docs/prices.csv`、`data/msrp.csv` と `docs/msrp.csv` の同期を確認。

## 2026-06-10 スマホ候補整理

- ユーザー判断でカードは完了扱いとし、次分野としてスマホを必要機種だけに絞る作業を開始。
- 買取一丁目候補表 `reports/ichome_product_candidates.csv` のスマホ未登録候補242件を確認。
- `scraper/generate_ichome_smartphone_recommendations.py` を追加し、スマホ候補を初回追加候補/次点候補/要確認/保留へ分類する仕組みを作成。
- 生成物: `reports/ichome_smartphone_recommendations.csv`、`reports/ichome_smartphone_recommendations.md`、`reports/ichome_smartphone_shortlist.csv`。
- 分類結果: 初回追加候補24件、次点候補28件、要確認44件、保留146件。
- 初回追加候補は iPhone 16 Pro/Pro Max の256GB/512GB/1TB、各4色。既存登録済みのiPhone 17 Pro/Pro Maxは触らない。
- 128GB、2TB、iPhone 15以前、iPhone Airは次点または要確認に落とした。商品マスターへの追加はまだ未実施。
- `python -m py_compile scraper\generate_ichome_smartphone_recommendations.py` 成功。
- ユーザー判断により、スマホ初回追加候補24件はいずれも追加しないことにした。

## 2026-06-10 買取一丁目価格アラーム初期実装

- 次項目として、買取一丁目価格アラームを実装。最初は `docs/index.html` 内に置いたが、画面が混み合うため `docs/alerts.html` へ別ページ化した。
- 画面上で、上昇率、上昇額、条件（両方/どちらか/率のみ/円のみ）を変更できるようにした。設定は `localStorage` に保存。
- 判定対象は買取一丁目のみ。商品ごとの直近価格と、その前の異なる価格を比較し、上昇額と上昇率を計算する。
- `docs/index.html` には価格アラームへのリンクと、`?product=` パラメータで該当商品を開く処理だけを追加。
- アラーム行をクリックすると `index.html?product=...` へ遷移し、該当商品のチャートを表示する。
- ローカル `http://127.0.0.1:8010/alerts.html` で確認。初期条件（5%、1,000円、両方）では6件表示。先頭は `CANON PowerShot V1`、+880.0%、+88,000円。
- Playwrightで `alerts.html` 表示、トップページ導線、アラーム行クリック後の該当商品選択を確認し、コンソールエラーなし。

## 2026-06-10 価格アラームページ内チャート追加

- ユーザー依頼により、価格アラームを別ページにしたまま、`docs/alerts.html` 内にも価格チャートを追加。
- アラーム行は遷移リンクではなく選択ボタンに変更。商品を選ぶと同じページ内のチャートタイトル、期間、価格推移が切り替わる。
- チャートは `docs/index.html` と同じ考え方で、買取店は前値補完、ヤフオクは実データ日のみ表示。ヤフオク最安〜最高の幅もエラーバーとして描画。
- `チャートページで開く` リンクは残し、選択中の商品を `index.html?product=...` で開けるようにした。
- Playwrightで `http://127.0.0.1:8010/alerts.html` を確認。初期条件で6件表示、初期選択は `CANON PowerShot V1`。2件目クリックで `CANON PowerShot G7 X Mark III PowerShot 30th Anniversary Edition` にチャートが切り替わることを確認。
- デスクトップ幅とスマホ幅でチャート表示、選択状態、コンソールエラーなしを確認。確認画像は `reports/alerts_chart_preview.png` / `reports/alerts_chart_mobile_preview.png`。
- ユーザー確認後、デスクトップ幅の配置を左アラーム一覧・右チャートへ変更。1900px幅では一覧430px、チャート約1160pxの2カラム表示を確認。1180px未満は上下配置へ戻すレスポンシブにした。
