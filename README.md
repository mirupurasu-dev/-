# SoraDeals — 海外航空券 激安チャートまとめサイト

世界各都市への航空券について、過去の価格推移チャートと現在価格を比較し、
「過去平均より圧倒的に安いタイミング」をひと目で見つけられる静的サイトです。

## 現在の状態(重要)

**実際の航空券価格APIには接続していません。** `data/fares.json` は
`scripts/generate_data.py` で生成したサンプルデータで、実在の価格ではありません。
まずはUI・チャート・「激安」判定ロジックのプロトタイプとして構築しています。

## 構成

- `index.html` / `assets/style.css` / `assets/app.js` — ビルド不要の静的サイト本体
- `data/fares.json` — 路線ごとの現在価格・過去24ヶ月分の価格履歴(サンプル)
- `scripts/generate_data.py` — サンプルデータ生成スクリプト(実データ差し替えの参考実装)

### 収録範囲(サンプル)

東京(成田/羽田)・大阪(関西)発で、北米・欧州・アジア・オセアニア・中東・
アフリカ・南米の主要24路線を収録。地域タブや検索、「激安のみ表示」フィルタ、
価格が安い順/お得な順のソートに対応しています。カードをクリックすると
Chart.jsによる過去24ヶ月の価格推移チャートが開きます。

「激安」判定は `discount_vs_avg_pct >= 25`(過去24ヶ月平均より25%以上安い)
をしきい値にしています。しきい値は `scripts/generate_data.py` 内の
`is_deal` 判定、および実データ接続後は好みのロジックに調整してください。

## 実データに接続するには

`data/fares.json` を、以下のスキーマを満たすJSONに差し替えれば
フロントエンドはそのまま動作します。

```json
{
  "generated_at": "YYYY-MM-DD",
  "currency": "JPY",
  "note": "...",
  "routes": [
    {
      "id": "NRT-BKK",
      "region": "asia",
      "region_label": "アジア",
      "origin": "NRT",
      "origin_name": "東京(成田)",
      "dest": "BKK",
      "dest_name": "バンコク",
      "dest_name_en": "Bangkok",
      "airlines": ["タイ国際航空"],
      "current_price": 45000,
      "historical_avg": 60000,
      "historical_min": 40000,
      "historical_max": 90000,
      "discount_vs_avg_pct": 25.0,
      "is_deal": true,
      "history": [{ "month": "2024-08", "price": 62000 }]
    }
  ]
}
```

実データ取得の選択肢:

- **Amadeus for Developers** などの無料枠APIキーを取得し、GitHub Actionsの
  定期実行(cron)で `data/fares.json` を更新するワークフローを追加する
- 有料のフライトデータAPI(Skyscanner, Kiwi.com Tequila API など)を利用する
- 手動で調べた特価情報を都度 `data/fares.json` に追記する運用にする

いずれの場合も、価格取得元の利用規約(スクレイピング禁止条項など)を
必ず確認してください。

## GitHub Pagesでの公開方法

1. リポジトリの **Settings → Pages** を開く
2. **Source** を `Deploy from a branch` に設定
3. Branch を `main`(またはこのブランチをマージ後のデフォルトブランチ)、
   フォルダを `/ (root)` に設定して Save
4. 数分待つと `https://<ユーザー名>.github.io/<リポジトリ名>/` で公開されます

ビルドステップは不要です(静的HTML/CSS/JSのみ)。

## ローカルで確認する

```bash
python3 -m http.server 8000
# http://localhost:8000 を開く
```

## サンプルデータの再生成

```bash
python3 scripts/generate_data.py
```
