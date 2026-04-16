# 競馬予想AI (KeibaAI)

JRA中央競馬の予想AI。**展開シナリオ別の因果的スコアリング** と **期待値ベースの買い目推奨** を中心に据え、**スマホで見られるスタイリッシュなライブダッシュボード**を備える。

```
┌────────────────────────────────────────────────────────────┐
│   特徴量   → 想定ペース分類 → シナリオ別LambdaRank×3       │
│   (脚質/テン/上がり/苦手/馬場傾向/枠順)                     │
│              → Plackett–Luce合成 → P(1着/2着/3着/複勝)     │
│              → 10秒間隔オッズ × EV × 分数ケリー            │
│              → 推奨買い目（単/複/馬連/馬単/3連複/3連単）   │
└────────────────────────────────────────────────────────────┘
```

## 構成

```
.
├── src/keiba_ai/         # Python: データ層・特徴量・モデル・買い目・API・CLI
├── web/                  # フロント: Next.js 14 + Tailwind (モバイルダッシュボード)
├── scripts/              # サンプルデータ生成など
├── tests/                # pytest
├── config/config.yaml    # 設定
└── sample_data/          # (生成物) サンプルCSV
```

## クイックスタート

### 1. 依存インストール

```bash
pip install -e ".[dev]"
```

### 2. サンプルデータ生成

```bash
python scripts/bootstrap_sample_data.py --n-races 1500 --seed 42
# → sample_data/ に races.csv / runners.csv / results.csv / odds.csv
```

### 3. 学習

```bash
keiba train --config config/config.yaml --model-dir models
```

ペース分類器 (3クラス) + シナリオ別 LambdaRank ×3本 (`high`/`mid`/`slow`) を学習して `models/` に保存。

### 4. 予測 (CLI)

```bash
keiba predict R000500
```

各馬の P(1着)/P(2着)/P(3着)/P(複勝) と脚質・テン指数・上がり指数を表示。

### 5. 買い目推奨

```bash
keiba recommend R000500 --budget 10000
```

期待値 > +10% の買い目のみを抽出し、**分数ケリー (1/4)** で推奨額を算出。

### 6. API サーバ

```bash
uvicorn keiba_ai.api.app:app --reload --port 8000
# http://localhost:8000/docs で OpenAPI ドキュメント
```

主なエンドポイント:
- `GET  /api/races/today` — 本日のレース一覧
- `GET  /api/races/{id}` — レース詳細（出走表）
- `GET  /api/predict/{id}` — 着順確率（各馬）
- `GET  /api/recommend/{id}?budget=10000` — 推奨買い目
- `POST /api/live/start/{id}` — 10秒オッズポーラ起動（Mock）
- `WS   /ws/live/{id}` — オッズ・推奨のリアルタイム配信

### 7. フロント（スマホダッシュボード）

```bash
cd web
cp .env.example .env.local
npm install
npm run dev
# http://localhost:3000
```

- スマホで確認する場合は、同一LAN内から `http://<PC IP>:3000` を開く（スマホ側では `.env.local` の `NEXT_PUBLIC_API_BASE` を合わせて調整）
- iPhone Safari で「ホーム画面に追加」→ PWA として起動可能

**画面**:
- `/` ダッシュボード（本日のレース一覧）
- `/race/:id` レース予測（確率積み上げバー、脚質チップ、根拠、推奨買い目）
- `/race/:id/live` ライブ画面（10秒ごとにWebSocket更新、オッズ変動のflashアニメ）
- `/backtest` `/bankroll` `/settings`

### 8. テスト

```bash
pytest -q
```

---

## 主要設計

### 予測コア

`src/keiba_ai/service.py` がオーケストレータ。

1. **特徴量生成** (`features/pipeline.py`)
   - 過去走から脚質確率（EWMA付き）・テン偏差値・上がり偏差値・実力指数・距離/馬場/馬場状態適性・コース複勝率・休養日数を算出
   - **リーク防止**: レース日より厳密に前の結果だけを参照
2. **想定ペース分類** (`models/pace_classifier.py`)
   - 出走馬の脚質分布・テン分布からレース前半のペース (`high`/`mid`/`slow`) を多クラス分類
3. **シナリオ別ランキング学習** (`models/ranker.py`)
   - 過去レースを実際の前半3Fタイムでシナリオに分け、それぞれで LambdaRank を学習
4. **確率合成** (`models/scenario_mix.py` + `plackett_luce.py`)
   - 各シナリオで Plackett–Luce 分解 → `P(1着)/P(2着)/P(3着)` を解析的算出
   - シナリオ確率で加重して最終確率を得る
5. **根拠説明** (`models/explainer.py`)
   - スコアとレース内特徴量の相関から主要寄与ファクターを抽出

### 買い目推奨

`src/keiba_ai/betting/`

- `expected_value.py`: EV = odds × p − 1
- `kelly.py`: フルケリー比率 `f* = (b·p − 1)/(b − 1)`、および **分数ケリー** （既定 1/4, 上限 5%）
- `recommender.py`: 全券種を列挙 → EV 閾値通過 → EV 降順にケリーで発注額を割り付け → 予算内上位 N 点

### リアルタイムオッズ

`src/keiba_ai/betting/odds_poller.py` + `odds_stream.py`

- 10秒間隔でバックエンドから取得（ハッシュ差分で無駄配信カット、発走間近は間隔短縮）
- `MockOddsBackend`: 確定オッズに±5%のノイズを乗せて擬似配信（JV-Link前の検証用）
- 取得したオッズは `OddsStream` に publish され、FastAPI の WebSocket から購読者へ送られる
- フロント `useLiveFeed` フックが WebSocket を張り、差分を UI に反映

### データソース

- 現状 `CsvDataSource` のみ実装。`sample_data/` からロード
- JV-Link 実装（`jvlink_client.py` / `parser.py`）は Windows 専用で **M2 マイルストン**

---

## マイルストン

- [x] **M1**: 足場（データ→特徴→学習→推論→買い目→API→フロント→テスト）
- [ ] **M2**: JV-Link 実装（Windows、pywin32）
- [ ] **M3**: 特徴量強化（調教・血統・馬場傾向リアルタイム反映）、Isotonic較正
- [ ] **M4**: バックテストダッシュボード（月次PL・回収率推移）
- [ ] **M5**: 運用（日次バッチ、LINE/Web Push通知）

## 免責

- 合法的に取得したデータ（JRA-VAN DataLab、自前記録など）のみを利用すること。netkeiba 等のスクレイピングは利用規約に抵触する場合があります
- 競馬は本質的に低シグナル・高分散の対象。**回収率100%超の長期達成は極めて困難**です
- 推奨買い目は教育・研究目的の参考値です。購入の判断とリスクはご自身で負ってください
