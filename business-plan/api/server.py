#!/usr/bin/env python3
"""Stillwater reference API + static-site server (dependency-free).

A small, standard-library-only HTTP server that demonstrates the operational
backbone described in the business plan. It is a REFERENCE / DEMO implementation
-- it uses an in-memory store and a mock fulfillment hand-off. It is NOT a
production payment system. In production you would run on a real e-commerce
platform (see ../06-ai-automation-stack.md); the value here is showing the
compliant shapes of each endpoint.

Endpoints
  GET  /api/health             -> liveness
  GET  /api/products           -> catalog (compliant copy + disclaimer)
  POST /api/claims-check       -> run the claims-compliance gate (file 06)
  POST /api/economics          -> run the unit-economics gates (file 04)
  POST /api/orders             -> create a mock order / subscription
  GET  /                       -> serves the static site in ../site

Run:
    python3 server.py            # serves on http://127.0.0.1:8000
    PORT=9000 python3 server.py  # custom port
"""
from __future__ import annotations

import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

# --- Make sibling modules and the ../tools calculator importable -------------
HERE = Path(__file__).resolve().parent
SITE_DIR = HERE.parent / "site"
TOOLS_DIR = HERE.parent / "tools"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TOOLS_DIR))

import claims  # noqa: E402  (local module)
import catalog  # noqa: E402  (local module)
import unit_economics as ue  # noqa: E402  (../tools/unit_economics.py)

# --- In-memory stores (demo only; reset on restart) --------------------------
ORDERS: dict[str, dict] = {}
SUBSCRIPTIONS: dict[str, dict] = {}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_BODY_BYTES = 64 * 1024  # reject oversized payloads


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Handler(BaseHTTPRequestHandler):
    server_version = "StillwaterDemo/0.1"

    # ---- helpers ------------------------------------------------------------
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _read_json(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if length <= 0:
            return {}
        if length > MAX_BODY_BYTES:
            return None
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else None
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def log_message(self, fmt: str, *args) -> None:  # quieter logging
        sys.stderr.write(f"{self.address_string()} - {fmt % args}\n")

    # ---- routing ------------------------------------------------------------
    def do_OPTIONS(self) -> None:  # CORS preflight
        self._send_json(204, {})

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            return self._send_json(200, {"status": "ok", "time": _now()})
        if path == "/api/products":
            return self._send_json(200, {"products": catalog.list_products()})
        if path.startswith("/api/"):
            return self._send_json(404, {"error": "unknown endpoint"})
        return self._serve_static(path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        data = self._read_json()
        if data is None:
            return self._send_json(400, {"error": "invalid or oversized JSON body"})
        if path == "/api/claims-check":
            return self._handle_claims(data)
        if path == "/api/economics":
            return self._handle_economics(data)
        if path == "/api/orders":
            return self._handle_order(data)
        return self._send_json(404, {"error": "unknown endpoint"})

    # ---- endpoint handlers --------------------------------------------------
    def _handle_claims(self, data: dict) -> None:
        copy = data.get("copy")
        if not isinstance(copy, str) or not copy.strip():
            return self._send_json(400, {"error": "field 'copy' (string) required"})
        result = claims.screen(copy)
        return self._send_json(200, result.to_dict())

    def _handle_economics(self, data: dict) -> None:
        try:
            scenario = ue.Scenario(
                price=float(data.get("price", 35.0)),
                cogs=float(data.get("cogs", 9.0)),
                shipping=float(data.get("shipping", 4.0)),
                fulfillment_fee=float(data.get("fulfillment_fee", 2.0)),
                processing_rate=float(data.get("processing_rate", 0.03)),
                cac=float(data.get("cac", 30.0)),
                expected_orders=float(data.get("expected_orders", 6.0)),
                cycle_days=float(data.get("cycle_days", 30.0)),
            )
        except (TypeError, ValueError):
            return self._send_json(400, {"error": "numeric fields must be numbers"})
        result = ue.evaluate(scenario)
        gate_list = [
            {"name": name, "passed": passed, "detail": detail}
            for name, passed, detail in ue.gates(result)
        ]
        return self._send_json(200, {
            "contribution_per_order": round(result.contribution_per_order, 2),
            "gross_margin": round(result.gross_margin, 4),
            "ltv": round(result.ltv, 2),
            "ltv_cac": round(result.ltv_cac, 2),
            "payback_orders": round(result.payback_orders, 2),
            "payback_days": round(result.payback_days, 1),
            "gates": gate_list,
            "all_gates_pass": all(g["passed"] for g in gate_list),
        })

    def _handle_order(self, data: dict) -> None:
        sku = data.get("sku")
        email = data.get("email", "")
        consent = bool(data.get("marketing_consent", False))

        if not isinstance(sku, str):
            return self._send_json(400, {"error": "field 'sku' (string) required"})
        if not isinstance(email, str) or not EMAIL_RE.match(email):
            return self._send_json(400, {"error": "valid 'email' required"})

        found = catalog.find_option(sku)
        if not found:
            return self._send_json(404, {"error": f"unknown sku '{sku}'"})

        product, option = found["product"], found["option"]
        order_id = "ord_" + uuid.uuid4().hex[:12]
        order = {
            "order_id": order_id,
            "sku": sku,
            "product_name": product["name"],
            "price": option["price"],
            "email": email,
            # ../02: explicit consent + easy cancel; no surprise auto-ship.
            "marketing_consent": consent,
            "created_at": _now(),
            # Mock fulfillment hand-off to the blind-ship supplier (../07).
            "fulfillment": {"status": "queued_to_supplier", "blind_ship": True},
        }
        ORDERS[order_id] = order

        response = {"order": order}
        if option.get("subscription"):
            sub_id = "sub_" + uuid.uuid4().hex[:12]
            SUBSCRIPTIONS[sub_id] = {
                "subscription_id": sub_id,
                "order_id": order_id,
                "sku": sku,
                "email": email,
                "interval_days": option.get("interval_days", 30),
                "status": "active",
                "created_at": _now(),
                # ../02 + ../07: cancellation must be genuinely easy.
                "cancel_url": f"/account/subscriptions/{sub_id}/cancel",
                "one_click_cancel": True,
            }
            response["subscription"] = SUBSCRIPTIONS[sub_id]
        return self._send_json(201, response)

    # ---- static file serving ------------------------------------------------
    def _serve_static(self, path: str) -> None:
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (SITE_DIR / rel).resolve()
        # Prevent path traversal: target must stay inside SITE_DIR.
        if not str(target).startswith(str(SITE_DIR.resolve())):
            return self._send_json(403, {"error": "forbidden"})
        if not target.is_file():
            return self._send_json(404, {"error": "not found"})
        content_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json",
            ".svg": "image/svg+xml",
        }
        ctype = content_types.get(target.suffix, "application/octet-stream")
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)


def main() -> int:
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Stillwater demo server on http://{host}:{port}")
    print("  GET  /                 -> website")
    print("  GET  /api/products     -> catalog")
    print("  POST /api/claims-check -> compliance gate")
    print("  POST /api/economics    -> unit-economics gates")
    print("  POST /api/orders       -> mock order/subscription")
    print("Ctrl-C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
