/* Organizer analytics: dependency-free SVG bar chart with tooltips,
   metric (revenue/tickets) and range (7/14/30d) switching. */
(function () {
  var host = document.getElementById("salesChart");
  if (!host) return;
  var all = JSON.parse(document.getElementById("series-data").textContent);
  var events = JSON.parse(document.getElementById("events-data").textContent);
  var state = { metric: "revenue", range: 30 };
  var NS = "http://www.w3.org/2000/svg";
  var cur = window.CURRENCY || "";

  function el(name, attrs, parent) {
    var n = document.createElementNS(NS, name);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function fmt(v) { return state.metric === "revenue" ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) + " " + cur : v + (v === 1 ? " ticket" : " tickets"); }
  function niceMax(v) { if (v <= 0) return 4; var p = Math.pow(10, Math.floor(Math.log10(v))); var n = v / p; return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p; }

  var tip = document.createElement("div"); tip.className = "tip"; host.appendChild(tip);

  function draw() {
    host.querySelectorAll("svg, .chart-empty").forEach(function (n) { n.remove(); });
    var data = all.slice(-state.range);
    var vals = data.map(function (d) { return d[state.metric]; });
    var total = vals.reduce(function (a, b) { return a + b; }, 0);
    if (!total) {
      var e = document.createElement("div"); e.className = "chart-empty";
      e.innerHTML = "<div><i class='fa-regular fa-chart-bar' style='font-size:28px;margin-bottom:8px;display:block'></i>No confirmed sales in this period yet.</div>";
      host.appendChild(e); return;
    }
    var W = host.clientWidth, H = host.clientHeight, m = { l: 44, r: 8, t: 10, b: 26 };
    var iw = W - m.l - m.r, ih = H - m.t - m.b, max = niceMax(Math.max.apply(null, vals));
    var svg = el("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Sales chart" }, host);
    var g = el("g", { "class": "grid" }, svg);
    for (var i = 0; i <= 4; i++) {
      var y = m.t + ih - (ih * i / 4);
      el("line", { x1: m.l, x2: W - m.r, y1: y, y2: y }, g);
      var t = el("text", { x: m.l - 8, y: y + 4, "text-anchor": "end" }, svg);
      var tv = max * i / 4; t.textContent = tv >= 1000 ? (tv / 1000) + "k" : (Math.round(tv * 10) / 10);
    }
    var step = iw / data.length, bw = Math.max(4, Math.min(28, step * .62));
    var every = Math.ceil(data.length / (W < 480 ? 5 : 10));
    data.forEach(function (d, idx) {
      var h = Math.max(vals[idx] ? 3 : 0, ih * vals[idx] / max), x = m.l + step * idx + (step - bw) / 2, y = m.t + ih - h;
      var r = el("rect", { "class": "bar", x: x, y: m.t + ih, width: bw, height: 0, rx: Math.min(5, bw / 2) }, svg);
      requestAnimationFrame(function () { r.style.transition = "y .6s cubic-bezier(.2,.7,.2,1) " + idx * 12 + "ms, height .6s cubic-bezier(.2,.7,.2,1) " + idx * 12 + "ms"; r.setAttribute("y", y); r.setAttribute("height", h); });
      if (idx % every === 0) { var lx = el("text", { x: x + bw / 2, y: H - 6, "text-anchor": "middle" }, svg); lx.textContent = d.label; }
      var hit = el("rect", { x: m.l + step * idx, y: m.t, width: step, height: ih, fill: "transparent" }, svg);
      hit.addEventListener("mouseenter", function () {
        r.classList.add("hot");
        tip.innerHTML = "<span>" + d.label + "</span><b>" + fmt(vals[idx]) + "</b>";
        tip.classList.add("is-on");
        var left = Math.min(Math.max(x + bw / 2 - tip.offsetWidth / 2, 0), W - tip.offsetWidth);
        tip.style.left = left + "px"; tip.style.top = Math.max(0, y - tip.offsetHeight - 8) + "px";
      });
      hit.addEventListener("mouseleave", function () { r.classList.remove("hot"); tip.classList.remove("is-on"); });
    });
  }

  function bind(id, key, attr, parse) {
    var seg = document.getElementById(id);
    seg.addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      seg.querySelectorAll("button").forEach(function (x) { x.classList.remove("is-on"); });
      b.classList.add("is-on"); state[key] = parse(b.dataset[attr]); draw();
    });
  }
  bind("metricSeg", "metric", "metric", String);
  bind("rangeSeg", "range", "range", Number);
  var rt; window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(draw, 120); });
  draw();

  // Revenue by event
  var bars = document.getElementById("eventBars");
  var top = Math.max.apply(null, events.map(function (e) { return e.revenue; }).concat([1]));
  if (!events.length) bars.innerHTML = "<p class='muted'>No events yet.</p>";
  events.forEach(function (e) {
    var row = document.createElement("div"); row.className = "hbar-row";
    var l = document.createElement("div"); l.className = "lbl";
    var a = document.createElement("span"); a.textContent = e.title;
    var b = document.createElement("span"); b.className = "tnum"; b.textContent = e.revenue.toLocaleString(undefined, { maximumFractionDigits: 2 }) + " " + cur;
    l.appendChild(a); l.appendChild(b);
    var tr = document.createElement("div"); tr.className = "track";
    var f = document.createElement("div"); f.className = "fill"; f.style.setProperty("--c", e.color); tr.appendChild(f);
    row.appendChild(l); row.appendChild(tr); bars.appendChild(row);
    setTimeout(function () { f.style.width = Math.max(2, 100 * e.revenue / top) + "%"; }, 80);
  });
})();
