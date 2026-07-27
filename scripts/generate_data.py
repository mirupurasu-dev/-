#!/usr/bin/env python3
"""
サンプル運賃データ生成スクリプト。

実際の運賃APIに接続していない現状では、過去24ヶ月分の運賃推移をそれっぽい
季節変動・ノイズ付きで生成し、data/fares.json に出力する。
実データに差し替える際は、この出力と同じスキーマ (routes[].history) を
満たすJSONを生成すればフロントエンドはそのまま動く。
"""
import json
import random
import datetime

random.seed(20260727)

ORIGINS = {
    "NRT": {"name": "東京(成田)", "name_en": "Tokyo (NRT)"},
    "HND": {"name": "東京(羽田)", "name_en": "Tokyo (HND)"},
    "KIX": {"name": "大阪(関西)", "name_en": "Osaka (KIX)"},
}

# region, dest code, dest name(jp), dest name(en), base fare(round trip, JPY), seasonality peak months(1-12), airlines
ROUTES = [
    # 北米
    ("north_america", "JFK", "ニューヨーク", "New York", "NRT", 128000, [3,7,8,12], ["ANA","JAL","デルタ航空"]),
    ("north_america", "LAX", "ロサンゼルス", "Los Angeles", "HND", 98000, [7,8,12], ["ANA","JAL","ユナイテッド航空"]),
    ("north_america", "HNL", "ホノルル", "Honolulu", "NRT", 78000, [1,7,8,12], ["ハワイアン航空","JAL","ANA"]),
    ("north_america", "YVR", "バンクーバー", "Vancouver", "NRT", 105000, [7,8], ["エア・カナダ","ANA"]),
    ("north_america", "ORD", "シカゴ", "Chicago", "HND", 118000, [7,8,12], ["ANA","ユナイテッド航空"]),
    # 欧州
    ("europe", "LHR", "ロンドン", "London", "HND", 132000, [7,8,12], ["ANA","JAL","ブリティッシュ・エアウェイズ"]),
    ("europe", "CDG", "パリ", "Paris", "NRT", 128000, [7,8,12], ["ANA","エールフランス"]),
    ("europe", "FCO", "ローマ", "Rome", "KIX", 138000, [7,8], ["ANA","ITAエアウェイズ"]),
    ("europe", "FRA", "フランクフルト", "Frankfurt", "NRT", 122000, [7,8,12], ["ANA","ルフトハンザ"]),
    ("europe", "BCN", "バルセロナ", "Barcelona", "NRT", 142000, [7,8], ["カタール航空","ターキッシュエアラインズ"]),
    # アジア
    ("asia", "BKK", "バンコク", "Bangkok", "NRT", 52000, [12,1,4], ["タイ国際航空","ANA","JAL"]),
    ("asia", "ICN", "ソウル", "Seoul", "HND", 28000, [1,7,8], ["大韓航空","ANA","JAL"]),
    ("asia", "TPE", "台北", "Taipei", "NRT", 32000, [1,7,8], ["チャイナエアライン","エバー航空"]),
    ("asia", "SIN", "シンガポール", "Singapore", "NRT", 68000, [12,1,7], ["シンガポール航空","ANA"]),
    ("asia", "DPS", "デンパサール(バリ)", "Bali (Denpasar)", "NRT", 74000, [7,8,12], ["ガルーダ・インドネシア航空","JAL"]),
    ("asia", "HAN", "ハノイ", "Hanoi", "NRT", 46000, [12,1], ["ベトナム航空","ANA"]),
    ("asia", "MNL", "マニラ", "Manila", "NRT", 48000, [12,4], ["フィリピン航空","セブパシフィック航空"]),
    # オセアニア
    ("oceania", "SYD", "シドニー", "Sydney", "HND", 98000, [12,1,7], ["ANA","カンタス航空"]),
    ("oceania", "AKL", "オークランド", "Auckland", "NRT", 108000, [12,1], ["ニュージーランド航空"]),
    # 中東
    ("middle_east", "DXB", "ドバイ", "Dubai", "NRT", 96000, [12,1,7], ["エミレーツ航空"]),
    ("middle_east", "IST", "イスタンブール", "Istanbul", "NRT", 112000, [7,8], ["ターキッシュエアラインズ"]),
    # アフリカ
    ("africa", "CAI", "カイロ", "Cairo", "NRT", 138000, [7,8,12], ["エジプト航空","カタール航空"]),
    ("africa", "NBO", "ナイロビ", "Nairobi", "HND", 158000, [7,8,12], ["エチオピア航空","カタール航空"]),
    # 南米
    ("south_america", "GRU", "サンパウロ", "Sao Paulo", "NRT", 168000, [12,1,7], ["エミレーツ航空","ラタム航空"]),
]

REGION_LABELS = {
    "north_america": "北米",
    "europe": "欧州",
    "asia": "アジア",
    "oceania": "オセアニア",
    "middle_east": "中東",
    "africa": "アフリカ",
    "south_america": "南米",
}

def month_seq(n=24):
    today = datetime.date(2026, 7, 1)
    months = []
    for i in range(n - 1, -1, -1):
        y = today.year
        m = today.month - i
        while m <= 0:
            m += 12
            y -= 1
        months.append(datetime.date(y, m, 1))
    return months

MONTHS = month_seq(24)

def gen_history(base_fare, peak_months):
    history = []
    price = base_fare
    for d in MONTHS:
        seasonal = 1.25 if d.month in peak_months else 1.0
        # ゆるいトレンド + ノイズ + 稀に飛び込みセール
        drift = random.uniform(-0.03, 0.03)
        price = price * (1 + drift)
        sale = 0.55 if random.random() < 0.06 else 1.0
        value = price * seasonal * sale
        value = max(value, base_fare * 0.4)
        history.append({"month": d.strftime("%Y-%m"), "price": int(round(value / 100) * 100)})
    return history

def build_routes():
    routes = []
    for region, code, name_jp, name_en, origin, base_fare, peak_months, airlines in ROUTES:
        history = gen_history(base_fare, peak_months)
        prices = [h["price"] for h in history]
        current = prices[-1]
        historical_avg = round(sum(prices[:-1]) / len(prices[:-1]))
        historical_min = min(prices[:-1])
        historical_max = max(prices[:-1])
        discount_vs_avg = round((1 - current / historical_avg) * 100, 1)
        is_deal = discount_vs_avg >= 25
        routes.append({
            "id": f"{origin}-{code}",
            "region": region,
            "region_label": REGION_LABELS[region],
            "origin": origin,
            "origin_name": ORIGINS[origin]["name"],
            "dest": code,
            "dest_name": name_jp,
            "dest_name_en": name_en,
            "airlines": airlines,
            "current_price": current,
            "historical_avg": historical_avg,
            "historical_min": historical_min,
            "historical_max": historical_max,
            "discount_vs_avg_pct": discount_vs_avg,
            "is_deal": is_deal,
            "history": history,
        })
    routes.sort(key=lambda r: -r["discount_vs_avg_pct"])
    return routes

def main():
    routes = build_routes()
    out = {
        "generated_at": "2026-07-27",
        "currency": "JPY",
        "note": "サンプルデータです。実際の運賃APIに接続していません。",
        "routes": routes,
    }
    with open("data/fares.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(routes)} routes to data/fares.json")

if __name__ == "__main__":
    main()
