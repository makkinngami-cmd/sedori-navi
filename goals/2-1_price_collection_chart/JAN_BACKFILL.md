# JANコード充足タスク（products.py の既存商品にJANを埋める）

Codex向けの実装指示。**外部API呼び出しは不要。手元の data/raw/ に既にJANが眠っている。**

---

## 最初に読むもの

1. `C:\Users\makki\sedori-navi\CLAUDE.md`
2. `C:\Users\makki\sedori-navi\goals\2-1_price_collection_chart\SESSION.md`
3. `C:\Users\makki\sedori-navi\goals\2-1_price_collection_chart\SPEC.md`
4. `C:\Users\makki\sedori-navi\goals\2-1_price_collection_chart\HANDOFF.md`
5. このファイル

---

## 背景・目的

`scraper/products.py` の `PRODUCTS` は359商品あるが、`jan` フィールドがあるのは119件（33%）のみ。
一方、追加5業者（買取ルデヤ・森森買取・買取ホムラ・買取商店・モバイル一番）の日次スクレイプは
`data/raw/YYYYMMDD_HHMMSS_{店名}.csv` に生データを残しており、この `jan` 列には**各店のページから
実際に取得したJANコードが既に入っている**（外部APIなしで取れる）。

このJANを `products.py` の該当商品に書き戻せば、外部照合なしでJAN充足率を上げられる。
また `scrape.py` の `known_jan_for_product()` は products.py の jan をフォールバックとして使うため、
一度埋めれば**今後の日次スクレイプで買取一丁目を含む全店舗のprices.csv行にもJANが自動で乗るようになる**
（将来分の改善も兼ねる）。

---

## やること

### 1. raw データの収集
`data/raw/` 配下の全CSV（複数日ぶんある。日付が新しいものを優先して構わないが、
取りこぼしを減らすため直近30日分程度をまとめて読むこと）を読み込む。
各行は `date,product_name,store,price,jan,url` 形式。

### 2. product_name → jan の対応表を作る
- `jan` 列が13桁の数字として正規化できる行のみ対象にする（空・不正値は無視）
- 同一 `product_name` に対して**複数の異なるJANが見つかった場合は自動採用しない**。
  対象商品名をリストアップし「要確認（JAN不一致）」として報告すること（後述の3-cで判断が必要な点として扱う）
- 同一 `product_name` に対して同じJANが複数回（複数日・複数店）出現するのは正常（採用してよい）

### 3. products.py への反映
- `PRODUCTS` を走査し、**現在 `jan` キーを持たない商品**のみを対象にする
  （既存の `jan` は上書きしない）
- 対応表の `product_name` と `products.py` の `name` が**完全一致**するものだけ反映する
  （曖昧一致・部分一致はしない。誤爆防止のため）
- 反映は `'jan': '該当13桁'` を該当商品dictに追加する形。既存のインデント・カンマの書式に合わせること
- CUSTOM_QUERIES など他のデータ構造は触らない

### 4. 反映内容の記録
`reports/jan_backfill_report.md` を新規作成し、以下を記載する（既存の
`reports/ichome_boost_candidates.*` と同じ運用ノリでよい）。

- 反映件数（例: 240件中◯件に新規JANを付与）
- 反映した商品名とJANの一覧
- 「要確認（JAN不一致）」リスト（複数の異なるJANが見つかった商品名とその候補JAN群）
- 反映後もJANが埋まらなかった商品数（raw側に該当データが一度も出現しなかった商品）

---

## やらないこと

- 楽天プロダクト製品検索APIなど外部APIは呼ばない（このタスクの範囲外。将来必要なら別途指示する）
- `data/prices.csv` / `docs/prices.csv` を直接書き換えない（次回の日次スクレイプで
  `known_jan_for_product()` 経由で自然に反映される。手で埋めない方針は `SPEC.md` の
  「データが取れていないとき、手動でCSVを埋めて終わりにしない」に準ずる）
- 既存の `jan` を持つ119商品の値を変更・上書きしない
- 「要確認（JAN不一致）」に分類した商品は products.py に反映しない（人間の判断待ち）
- `data/raw/` のファイルを削除・移動しない（読み取りのみ）

---

## 完了時に報告してほしいこと

- `reports/jan_backfill_report.md` の内容（サマリーでよい）
- 反映前後のJAN充足率（119/359 → ◯/359）
- 「要確認（JAN不一致）」件数と、代表的な2〜3件の中身
- git commit はせず、差分を残した状態でユーザー確認を待つこと
