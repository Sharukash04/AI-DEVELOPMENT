"""
E-Commerce Order MCP Server (UC4)
==================================
Exposes:
  Tools:
    - track_order(order_id)
    - check_stock(sku)
    - initiate_return(order_id, reason)
  Resource:
    - orders://catalog  (full product catalog, read-only snapshot)

Storage: SQLite (ecommerce.db), created by seed_data.py
Transport: stdio (for local testing / Claude Desktop / MCP Inspector)

Run:
    python seed_data.py      # creates/reset the mock DB
    python server.py         # starts the MCP server over stdio
"""

import json
import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone

import anyio
import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

# ============================================
# Paths / Logging
# ============================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "ecommerce.db")
LOG_FILE = os.path.join(BASE_DIR, "audit.log")

# Dedicated audit logger -> file only (never stdout, which stdio transport reserves
# for JSON-RPC messages).
audit_logger = logging.getLogger("mcp_audit")
audit_logger.setLevel(logging.INFO)
_handler = logging.FileHandler(LOG_FILE)
_handler.setFormatter(logging.Formatter("%(message)s"))
audit_logger.addHandler(_handler)


def log_tool_call(tool_name: str, arguments: dict, result_summary: str) -> None:
    """Log every tool invocation with timestamp + sanitized arguments."""
    sanitized = sanitize_arguments(arguments)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool": tool_name,
        "arguments": sanitized,
        "result": result_summary,
    }
    audit_logger.info(json.dumps(entry))


def sanitize_arguments(arguments: dict) -> dict:
    """Strip/obfuscate anything sensitive before logging. Customer names are
    partially masked; everything else is passed through since this is a
    mock/demo dataset with no real PII."""
    sanitized = dict(arguments or {})
    if "customer_name" in sanitized and sanitized["customer_name"]:
        name = str(sanitized["customer_name"])
        sanitized["customer_name"] = (name[0] + "***") if name else name
    return sanitized


# ============================================
# Data access helpers
# ============================================
def get_connection() -> sqlite3.Connection:
    if not os.path.exists(DB_FILE):
        raise RuntimeError(
            f"Database not found at {DB_FILE}. Run `python seed_data.py` first."
        )
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================
# Server
# ============================================
app = Server("ecommerce-orders")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="track_order",
            description="Look up the current status, items, and shipping progress of an order by its order ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID to track (e.g. ORD-5001).",
                    }
                },
                "required": ["order_id"],
                "additionalProperties": False,
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "status": {"type": "string"},
                    "customer_name": {"type": "string"},
                    "sku": {"type": "string"},
                    "product_name": {"type": "string"},
                    "quantity": {"type": "integer"},
                    "order_date": {"type": "string"},
                    "return_status": {"type": ["string", "null"]},
                },
                "required": ["order_id", "status"],
            },
        ),
        types.Tool(
            name="check_stock",
            description="Check current stock quantity and price for a product by SKU.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sku": {
                        "type": "string",
                        "description": "The product SKU to check (e.g. SKU-1001).",
                    }
                },
                "required": ["sku"],
                "additionalProperties": False,
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "sku": {"type": "string"},
                    "name": {"type": "string"},
                    "price": {"type": "number"},
                    "stock_qty": {"type": "integer"},
                    "in_stock": {"type": "boolean"},
                },
                "required": ["sku", "in_stock"],
            },
        ),
        types.Tool(
            name="initiate_return",
            description="Start a return for a delivered order, given an order ID and a reason.",
            inputSchema={
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID to return (e.g. ORD-5001).",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the return (e.g. 'defective', 'wrong item').",
                    },
                },
                "required": ["order_id", "reason"],
                "additionalProperties": False,
            },
            outputSchema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "return_status": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["order_id", "return_status", "message"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    arguments = arguments or {}

    try:
        if name == "track_order":
            result = _track_order(arguments.get("order_id", ""))
        elif name == "check_stock":
            result = _check_stock(arguments.get("sku", ""))
        elif name == "initiate_return":
            result = _initiate_return(arguments.get("order_id", ""), arguments.get("reason", ""))
        else:
            result = {"error": f"Unknown tool: {name}"}

        log_tool_call(name, arguments, json.dumps(result)[:200])
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as exc:  # keep the server alive on bad input
        error_result = {"error": str(exc)}
        log_tool_call(name, arguments, f"ERROR: {exc}")
        return [types.TextContent(type="text", text=json.dumps(error_result, indent=2))]


def _track_order(order_id: str) -> dict:
    if not order_id:
        return {"error": "order_id is required"}
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT o.order_id, o.customer_name, o.sku, o.quantity, o.status,
                      o.order_date, o.return_status, p.name AS product_name
               FROM orders o
               JOIN products p ON p.sku = o.sku
               WHERE o.order_id = ? COLLATE NOCASE""",
            (order_id,),
        ).fetchone()
        if row is None:
            return {"error": f"Order '{order_id}' not found."}
        return dict(row)
    finally:
        conn.close()


def _check_stock(sku: str) -> dict:
    if not sku:
        return {"error": "sku is required"}
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT sku, name, price, stock_qty FROM products WHERE sku = ? COLLATE NOCASE",
            (sku,),
        ).fetchone()
        if row is None:
            return {"error": f"SKU '{sku}' not found."}
        data = dict(row)
        data["in_stock"] = data["stock_qty"] > 0
        return data
    finally:
        conn.close()


def _initiate_return(order_id: str, reason: str) -> dict:
    if not order_id or not reason:
        return {"error": "order_id and reason are both required"}
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT order_id, status, return_status FROM orders WHERE order_id = ? COLLATE NOCASE",
            (order_id,),
        ).fetchone()
        if row is None:
            return {"error": f"Order '{order_id}' not found."}
        if row["status"] != "delivered":
            return {
                "order_id": order_id,
                "return_status": "rejected",
                "message": f"Cannot return order in status '{row['status']}'. Only delivered orders are eligible.",
            }
        if row["return_status"] == "requested":
            return {
                "order_id": order_id,
                "return_status": "requested",
                "message": "A return has already been initiated for this order.",
            }
        conn.execute(
            "UPDATE orders SET return_status = 'requested' WHERE order_id = ? COLLATE NOCASE",
            (order_id,),
        )
        conn.commit()
        return {
            "order_id": order_id,
            "return_status": "requested",
            "message": f"Return initiated for order '{order_id}'. Reason logged: '{reason}'.",
        }
    finally:
        conn.close()


# ============================================
# Resources
# ============================================
@app.list_resources()
async def list_resources() -> list[types.Resource]:
    return [
        types.Resource(
            uri="orders://catalog",
            name="Product Catalog",
            description="Snapshot of all products with current stock and price.",
            mimeType="text/plain",
        ),
    ]


@app.read_resource()
async def read_resource(uri: str) -> str:
    if uri == "orders://catalog":
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT sku, name, price, stock_qty FROM products ORDER BY sku"
            ).fetchall()
        finally:
            conn.close()
        lines = ["Product Catalog", "=" * 30]
        for r in rows:
            status = "In stock" if r["stock_qty"] > 0 else "Out of stock"
            lines.append(f"{r['sku']}: {r['name']} — ${r['price']:.2f} [{status}, qty {r['stock_qty']}]")
        return "\n".join(lines)
    raise ValueError(f"Unknown resource: {uri}")


# ============================================
# Run
# ============================================
async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="ecommerce-orders",
                server_version="1.0.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    if not os.path.exists(DB_FILE):
        # IMPORTANT: never print to stdout in a stdio-transport server —
        # stdout is reserved for JSON-RPC messages once the client attaches.
        print(
            f"[startup] {DB_FILE} not found — run `python seed_data.py` first.",
            file=sys.stderr,
            flush=True,
        )
    anyio.run(main)