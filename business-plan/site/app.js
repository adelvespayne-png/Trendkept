// Stillwater storefront — talks to the dependency-free demo API in ../api.
// Renders categories + a product grid. Keeps everything compliant: it renders
// only the copy/claims the API serves, shows the FDA disclaimer for
// supplements/vitamins, and a cosmetic note for skincare.
(function () {
  "use strict";

  var API = ""; // same-origin (served by server.py)
  var state = { categories: [], products: [], selected: {}, activeCat: "all" };

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (k) {
      if (k === "class") node.className = attrs[k];
      else if (k === "html") node.innerHTML = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) {
      if (c) node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return node;
  }

  function money(n) { return "£" + Number(n).toFixed(2); }

  function load() {
    fetch(API + "/api/products")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        state.categories = data.categories || [];
        state.products = data.products || [];
        // Default each product's selected option to its subscription.
        state.products.forEach(function (p) {
          var sub = p.options.filter(function (o) { return o.subscription; })[0];
          state.selected[p.id] = (sub || p.options[0]).sku;
        });
        renderCategoryNav();
        renderGrid();
      })
      .catch(function () {
        document.getElementById("shop-root").innerHTML =
          '<p class="muted">Shop unavailable. Start the API: ' +
          '<code>python3 business-plan/api/server.py</code></p>';
      });
  }

  function renderCategoryNav() {
    var nav = document.getElementById("category-nav");
    nav.innerHTML = "";
    var tabs = [{ id: "all", name: "All" }].concat(state.categories);
    tabs.forEach(function (c) {
      var b = el("button", {
        class: "cat-tab" + (state.activeCat === c.id ? " active" : "")
      }, [c.name]);
      b.addEventListener("click", function () {
        state.activeCat = c.id;
        renderCategoryNav();
        renderGrid();
      });
      nav.appendChild(b);
    });
  }

  function renderGrid() {
    var root = document.getElementById("shop-root");
    root.innerHTML = "";
    var cats = state.activeCat === "all"
      ? state.categories
      : state.categories.filter(function (c) { return c.id === state.activeCat; });

    cats.forEach(function (cat) {
      var items = state.products.filter(function (p) { return p.category === cat.id; });
      if (!items.length) return;
      root.appendChild(el("h3", { class: "cat-title" }, [cat.name]));
      root.appendChild(el("p", { class: "muted cat-blurb" }, [cat.blurb || ""]));
      var grid = el("div", { class: "grid" });
      items.forEach(function (p) { grid.appendChild(card(p)); });
      root.appendChild(grid);
    });
  }

  function card(p) {
    var node = el("div", { class: "pcard" });

    // Visual header with category-coloured gradient + abbreviation.
    var visual = el("div", { class: "pcard-visual t-" + (p.product_type || "supplement") }, [
      el("span", {}, [abbrev(p.name)]),
      el("span", { class: "pcard-type" }, [labelForType(p.product_type)])
    ]);
    node.appendChild(visual);

    var body = el("div", { class: "pcard-body" });
    body.appendChild(el("h4", {}, [p.name]));
    body.appendChild(el("p", { class: "muted small" }, [p.subtitle || ""]));
    body.appendChild(el("p", { class: "pcard-claim" }, [p.claim]));

    body.appendChild(el("div", { class: "badges" }, [
      p.third_party_tested ? el("span", { class: "badge" }, ["3rd-party tested"]) : null,
      p.coa_published ? el("span", { class: "badge" }, ["Lab results published"]) : null
    ]));

    // Option selector (subscription flagged as best value).
    var onetime = (p.options.filter(function (o) { return !o.subscription; })[0] || {}).price;
    p.options.forEach(function (opt) {
      var selected = state.selected[p.id] === opt.sku;
      var row = el("div", { class: "option" + (selected ? " selected" : "") });
      var left = el("div", {}, [el("div", { class: "label" }, [opt.label])]);
      if (opt.subscription && onetime && onetime > opt.price) {
        var pct = Math.round((1 - opt.price / onetime) * 100);
        left.appendChild(el("div", { class: "save" }, ["Save " + pct + "% · cancel anytime"]));
        row.appendChild(el("span", { class: "best-tag" }, ["Best value"]));
      }
      row.appendChild(left);
      row.appendChild(el("div", { class: "price" }, [money(opt.price)]));
      row.addEventListener("click", function () {
        state.selected[p.id] = opt.sku;
        renderGrid();
      });
      body.appendChild(row);
    });

    var btn = el("button", { class: "btn btn-primary btn-block" }, ["Add to order"]);
    btn.addEventListener("click", function () { placeOrder(p, btn); });
    body.appendChild(btn);

    // Compliance footer per regime.
    if (p.fda_disclaimer) {
      body.appendChild(el("p", { class: "pcard-fineprint" }, [p.fda_disclaimer]));
    } else if (p.cosmetic_note) {
      body.appendChild(el("p", { class: "pcard-fineprint" }, [p.cosmetic_note]));
    }
    node.appendChild(body);
    return node;
  }

  // Short 1-2 char code for the product visual (e.g. "Magnesium Glycinate"->"MG").
  function abbrev(name) {
    var m = (name || "").match(/[A-Z]\d+|\d+|[A-Za-z]+/g) || [];
    // Prefer a token with a digit (D3, K2, C, 1000) if present and short.
    var coded = m.filter(function (t) { return /\d/.test(t) && t.length <= 4; });
    if (coded.length) return coded[0].toUpperCase();
    return m.slice(0, 2).map(function (t) { return t[0]; }).join("").toUpperCase();
  }

  function labelForType(t) {
    if (t === "skincare") return "Skincare";
    if (t === "vitamin") return "Vitamin";
    return "Supplement";
  }

  function placeOrder(product, btn) {
    var email = (document.getElementById("email").value || "").trim();
    var consent = document.getElementById("consent").checked;
    var result = document.getElementById("order-result");
    result.className = "order-result";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      result.className = "order-result err";
      result.textContent = "Please enter a valid email at the top before ordering.";
      document.getElementById("email").focus();
      return;
    }
    btn.disabled = true;
    var prev = btn.textContent;
    btn.textContent = "Adding…";
    fetch(API + "/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sku: state.selected[product.id],
        email: email,
        marketing_consent: consent
      })
    })
      .then(function (r) { return r.json().then(function (b) { return { ok: r.ok, body: b }; }); })
      .then(function (res) {
        btn.disabled = false;
        btn.textContent = prev;
        if (!res.ok) {
          result.className = "order-result err";
          result.textContent = res.body.error || "Order failed.";
          return;
        }
        result.className = "order-result ok";
        var msg = product.name + " — order " + res.body.order.order_id + " placed (demo). ";
        if (res.body.subscription) {
          msg += "Subscription active, renews every " +
            res.body.subscription.interval_days + " days, one-click cancel anytime.";
        }
        result.textContent = msg;
        result.scrollIntoView({ behavior: "smooth", block: "center" });
      })
      .catch(function () {
        btn.disabled = false;
        btn.textContent = prev;
        result.className = "order-result err";
        result.textContent = "Network error — is the API running?";
      });
  }

  document.addEventListener("DOMContentLoaded", load);
})();
