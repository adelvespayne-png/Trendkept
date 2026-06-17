// Stillwater storefront — talks to the dependency-free demo API in ../api.
// Keeps everything compliant: renders only the copy/claims the API serves,
// and surfaces the FDA disclaimer.
(function () {
  "use strict";

  var API = ""; // same-origin (served by server.py). Set to a full URL if split.
  var state = { product: null, selectedSku: null };

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (k) {
      if (k === "class") node.className = attrs[k];
      else if (k === "html") node.innerHTML = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) {
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return node;
  }

  function money(n) { return "£" + Number(n).toFixed(2); }

  function loadProduct() {
    fetch(API + "/api/products")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var p = (data.products || [])[0];
        if (!p) throw new Error("no product");
        state.product = p;
        // Default selection: the subscription (the profit engine).
        var sub = p.options.filter(function (o) { return o.subscription; })[0];
        state.selectedSku = (sub || p.options[0]).sku;
        renderProduct();
        // Inject the FDA disclaimer from the source of truth (the catalog).
        if (p.fda_disclaimer) {
          var d = document.getElementById("fda-disclaimer");
          if (d) d.textContent = p.fda_disclaimer;
        }
      })
      .catch(function () {
        document.getElementById("product-root").innerHTML =
          '<p class="muted">Product unavailable. Start the API: ' +
          '<code>python3 business-plan/api/server.py</code></p>';
      });
  }

  function renderProduct() {
    var p = state.product;
    var root = document.getElementById("product-root");
    root.innerHTML = "";

    // Left: product info
    var info = el("div", { class: "product-info" }, [
      el("h3", {}, [p.name]),
      el("p", { class: "muted" }, [p.subtitle || ""]),
      el("p", { class: "product-claim" }, [p.claim]),
      el("div", { class: "badges" }, [
        p.third_party_tested ? el("span", { class: "badge" }, ["3rd-party tested"]) : "",
        p.coa_published ? el("span", { class: "badge" }, ["CoA published"]) : "",
        el("span", { class: "badge" }, [p.servings + " servings"])
      ].filter(Boolean)),
      el("p", { class: "muted small" }, ["Ingredients:"]),
      el("ul", {}, (p.ingredients || []).map(function (i) {
        return el("li", {}, [i]);
      }))
    ]);

    // Right: buy box
    var buybox = el("div", { class: "buybox" });
    var onetimePrice = (p.options.filter(function (o) { return !o.subscription; })[0] || {}).price;
    p.options.forEach(function (opt) {
      var row = el("div", {
        class: "option" + (opt.sku === state.selectedSku ? " selected" : "")
      });
      var left = el("div", {}, [el("div", { class: "label" }, [opt.label])]);
      if (opt.subscription && onetimePrice && onetimePrice > opt.price) {
        var pct = Math.round((1 - opt.price / onetimePrice) * 100);
        left.appendChild(el("div", { class: "save" }, ["Save " + pct + "% · cancel anytime"]));
      }
      row.appendChild(left);
      row.appendChild(el("div", { class: "price" }, [money(opt.price)]));
      row.addEventListener("click", function () {
        state.selectedSku = opt.sku;
        renderProduct();
      });
      buybox.appendChild(row);
    });

    // Email + consent + buy
    var emailField = el("div", { class: "field" }, [
      el("label", { for: "email" }, ["Email"]),
      el("input", { type: "email", id: "email", placeholder: "you@example.com" })
    ]);
    var consent = el("label", { class: "consent" }, [
      el("input", { type: "checkbox", id: "consent" }),
      el("span", {}, ["Email me product tips and refill reminders. " +
        "Optional — you can unsubscribe anytime."])
    ]);
    var btn = el("button", { class: "btn btn-primary", id: "buy" }, ["Place order"]);
    var result = el("div", { class: "order-result", id: "order-result" });

    btn.addEventListener("click", function () { placeOrder(btn, result); });

    buybox.appendChild(emailField);
    buybox.appendChild(consent);
    buybox.appendChild(btn);
    buybox.appendChild(result);

    root.appendChild(info);
    root.appendChild(buybox);
  }

  function placeOrder(btn, result) {
    var email = (document.getElementById("email").value || "").trim();
    var consent = document.getElementById("consent").checked;
    result.className = "order-result";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      result.className = "order-result err";
      result.textContent = "Please enter a valid email address.";
      return;
    }
    btn.disabled = true;
    btn.textContent = "Placing…";
    fetch(API + "/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sku: state.selectedSku,
        email: email,
        marketing_consent: consent
      })
    })
      .then(function (r) { return r.json().then(function (b) { return { ok: r.ok, body: b }; }); })
      .then(function (res) {
        btn.disabled = false;
        btn.textContent = "Place order";
        if (!res.ok) {
          result.className = "order-result err";
          result.textContent = res.body.error || "Order failed.";
          return;
        }
        result.className = "order-result ok";
        var msg = "Order " + res.body.order.order_id + " placed (demo). ";
        if (res.body.subscription) {
          msg += "Subscription active — renews every " +
            res.body.subscription.interval_days +
            " days, one-click cancel anytime.";
        }
        result.textContent = msg;
      })
      .catch(function () {
        btn.disabled = false;
        btn.textContent = "Place order";
        result.className = "order-result err";
        result.textContent = "Network error — is the API running?";
      });
  }

  document.addEventListener("DOMContentLoaded", loadProduct);
})();
