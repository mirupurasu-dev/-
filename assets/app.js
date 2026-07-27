(function () {
  "use strict";

  const state = {
    data: null,
    region: "all",
    query: "",
    sort: "deal",
    dealOnly: false,
    chart: null,
  };

  const yen = (n) => "¥" + Number(n).toLocaleString("ja-JP");

  async function loadData() {
    const res = await fetch("data/fares.json", { cache: "no-store" });
    if (!res.ok) throw new Error("failed to load data/fares.json");
    return res.json();
  }

  function buildRegionTabs(routes) {
    const seen = new Map();
    routes.forEach((r) => seen.set(r.region, r.region_label));
    const tabs = document.getElementById("regionTabs");
    seen.forEach((label, key) => {
      const btn = document.createElement("button");
      btn.className = "tab";
      btn.dataset.region = key;
      btn.textContent = label;
      tabs.appendChild(btn);
    });
    tabs.addEventListener("click", (e) => {
      const btn = e.target.closest(".tab");
      if (!btn) return;
      state.region = btn.dataset.region;
      [...tabs.children].forEach((c) => c.classList.toggle("active", c === btn));
      render();
    });
  }

  function filteredSorted() {
    const q = state.query.trim().toLowerCase();
    let routes = state.data.routes.filter((r) => {
      if (state.region !== "all" && r.region !== state.region) return false;
      if (state.dealOnly && !r.is_deal) return false;
      if (!q) return true;
      const hay = [r.dest_name, r.dest_name_en, r.dest, r.origin, r.origin_name, r.region_label]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
    switch (state.sort) {
      case "price_asc":
        routes.sort((a, b) => a.current_price - b.current_price);
        break;
      case "price_desc":
        routes.sort((a, b) => b.current_price - a.current_price);
        break;
      case "region":
        routes.sort((a, b) => a.region_label.localeCompare(b.region_label, "ja"));
        break;
      default:
        routes.sort((a, b) => b.discount_vs_avg_pct - a.discount_vs_avg_pct);
    }
    return routes;
  }

  function renderStats(routes) {
    const strip = document.getElementById("statsStrip");
    const dealCount = state.data.routes.filter((r) => r.is_deal).length;
    const cheapest = [...state.data.routes].sort((a, b) => a.current_price - b.current_price)[0];
    const topDeal = [...state.data.routes].sort((a, b) => b.discount_vs_avg_pct - a.discount_vs_avg_pct)[0];
    strip.innerHTML = `
      <div class="stat-box"><div class="label">掲載路線数</div><div class="value">${state.data.routes.length}</div></div>
      <div class="stat-box"><div class="label">激安判定中の路線</div><div class="value">${dealCount}</div></div>
      <div class="stat-box"><div class="label">最安値路線</div><div class="value">${cheapest.dest_name} ${yen(cheapest.current_price)}</div></div>
      <div class="stat-box"><div class="label">最大割引率</div><div class="value">${topDeal.dest_name} -${topDeal.discount_vs_avg_pct}%</div></div>
    `;
  }

  function cardHTML(r) {
    const discountClass = r.discount_vs_avg_pct >= 0 ? "positive" : "negative";
    const sign = r.discount_vs_avg_pct >= 0 ? "-" : "+";
    return `
      <article class="card ${r.is_deal ? "deal" : ""}" data-id="${r.id}">
        ${r.is_deal ? '<span class="deal-badge">激安</span>' : ""}
        <div class="route">${r.origin_name} → ${r.dest_name_en}</div>
        <div class="dest">${r.dest_name} (${r.dest})</div>
        <span class="region-chip">${r.region_label}</span>
        <div class="price-row">
          <span class="current-price">${yen(r.current_price)}</span>
          <span class="price-unit">往復</span>
        </div>
        <div class="hist-line">
          過去平均 ${yen(r.historical_avg)} ・
          <span class="discount ${discountClass}">${sign}${Math.abs(r.discount_vs_avg_pct)}%</span>
        </div>
        <div class="airlines">${r.airlines.join(" / ")}</div>
      </article>
    `;
  }

  function render() {
    const routes = filteredSorted();
    renderStats(routes.length ? routes : state.data.routes);
    const grid = document.getElementById("routeGrid");
    if (!routes.length) {
      grid.innerHTML = '<div class="loading">該当する路線が見つかりませんでした。</div>';
      return;
    }
    grid.innerHTML = routes.map(cardHTML).join("");
    grid.querySelectorAll(".card").forEach((el) => {
      el.addEventListener("click", () => openModal(el.dataset.id));
    });
  }

  function openModal(id) {
    const r = state.data.routes.find((x) => x.id === id);
    if (!r) return;
    const backdrop = document.getElementById("modalBackdrop");
    const body = document.getElementById("modalBody");
    body.innerHTML = `
      <h2>${r.origin_name} → ${r.dest_name} (${r.dest_name_en})</h2>
      <div class="modal-sub">${r.region_label} ・ ${r.airlines.join(" / ")}</div>
      <div class="modal-metrics">
        <div class="metric"><div class="label">現在価格</div><div class="value">${yen(r.current_price)}</div></div>
        <div class="metric"><div class="label">過去24ヶ月平均</div><div class="value">${yen(r.historical_avg)}</div></div>
        <div class="metric"><div class="label">過去最安値</div><div class="value">${yen(r.historical_min)}</div></div>
        <div class="metric"><div class="label">過去最高値</div><div class="value">${yen(r.historical_max)}</div></div>
      </div>
    `;
    backdrop.classList.add("open");

    const ctx = document.getElementById("priceChart").getContext("2d");
    if (state.chart) state.chart.destroy();
    state.chart = new Chart(ctx, {
      type: "line",
      data: {
        labels: r.history.map((h) => h.month),
        datasets: [
          {
            label: "往復運賃 (円)",
            data: r.history.map((h) => h.price),
            borderColor: "#4fb0ff",
            backgroundColor: "rgba(79,176,255,0.15)",
            fill: true,
            tension: 0.25,
            pointRadius: 2,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          y: { ticks: { callback: (v) => "¥" + v.toLocaleString("ja-JP") } },
        },
      },
    });
  }

  function closeModal() {
    document.getElementById("modalBackdrop").classList.remove("open");
  }

  function wireControls() {
    document.getElementById("searchInput").addEventListener("input", (e) => {
      state.query = e.target.value;
      render();
    });
    document.getElementById("sortSelect").addEventListener("change", (e) => {
      state.sort = e.target.value;
      render();
    });
    document.getElementById("dealOnly").addEventListener("change", (e) => {
      state.dealOnly = e.target.checked;
      render();
    });
    document.getElementById("modalClose").addEventListener("click", closeModal);
    document.getElementById("modalBackdrop").addEventListener("click", (e) => {
      if (e.target.id === "modalBackdrop") closeModal();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeModal();
    });
  }

  async function init() {
    const notice = document.getElementById("dataNotice");
    try {
      state.data = await loadData();
      notice.textContent = `⚠️ ${state.data.note} (最終更新: ${state.data.generated_at})`;
      buildRegionTabs(state.data.routes);
      wireControls();
      render();
    } catch (err) {
      notice.textContent = "データの読み込みに失敗しました: " + err.message;
      document.getElementById("routeGrid").innerHTML = "";
    }
  }

  init();
})();
