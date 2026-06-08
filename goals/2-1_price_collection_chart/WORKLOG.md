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
