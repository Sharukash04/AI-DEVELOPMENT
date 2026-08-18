import json
import os
from datetime import datetime
import asyncio

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.types as types
import mcp.server.stdio

# ============================================
# Data Store
# ============================================
DATA_FILE = "library_data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        default = {
            "books": [
                {"id": "B001", "title": "Python Crash Course", "author": "Eric Matthes", "available": True},
                {"id": "B002", "title": "Deep Learning", "author": "Ian Goodfellow", "available": False},
                {"id": "B003", "title": "AI: A Modern Approach", "author": "Norvig", "available": True},
                {"id": "B004", "title": "Clean Code", "author": "Robert Martin", "available": True},
            ],
            "reservations": []
        }
        with open(DATA_FILE, "w") as f:
            json.dump(default, f, indent=2)
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ============================================
# Create Server
# ============================================
app = Server("campus-library")

# ============================================
# Tools
# ============================================

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_book",
            description="Search for books by title (partial match)",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Title to search for"}
                },
                "required": ["title"],
            },
        ),
        types.Tool(
            name="check_availability",
            description="Check if a specific book is available",
            inputSchema={
                "type": "object",
                "properties": {
                    "book_id": {"type": "string", "description": "Book ID (e.g., B001)"}
                },
                "required": ["book_id"],
            },
        ),
        types.Tool(
            name="reserve_book",
            description="Reserve an available book for a student",
            inputSchema={
                "type": "object",
                "properties": {
                    "book_id": {"type": "string", "description": "Book ID"},
                    "student_name": {"type": "string", "description": "Student's full name"}
                },
                "required": ["book_id", "student_name"],
            },
        ),
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    data = load_data()

    if name == "search_book":
        title = arguments.get("title", "")
        results = []
        for book in data["books"]:
            if title.lower() in book["title"].lower():
                status = "Available" if book["available"] else "Checked out"
                results.append(f"{book['id']}: {book['title']} by {book['author']} ({status})")
        if not results:
            return [types.TextContent(type="text", text="No books found.")]
        return [types.TextContent(type="text", text="\n".join(results))]

    elif name == "check_availability":
        book_id = arguments.get("book_id")
        for book in data["books"]:
            if book["id"].lower() == book_id.lower():
                status = "Available" if book["available"] else "Checked out"
                return [types.TextContent(type="text", text=f"Book {book_id}: {book['title']} – {status}")]
        return [types.TextContent(type="text", text=f"Book '{book_id}' not found.")]

    elif name == "reserve_book":
        book_id = arguments.get("book_id")
        student = arguments.get("student_name")
        for book in data["books"]:
            if book["id"].lower() == book_id.lower():
                if not book["available"]:
                    return [types.TextContent(type="text", text=f"Book '{book_id}' is not available.")]
                book["available"] = False
                data["reservations"].append({
                    "book_id": book_id,
                    "student": student,
                    "timestamp": datetime.now().isoformat()
                })
                save_data(data)
                return [types.TextContent(type="text", text=f"✅ '{book['title']}' reserved for {student}.")]
        return [types.TextContent(type="text", text=f"Book '{book_id}' not found.")]

    else:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

# ============================================
# Resources
# ============================================

@app.list_resources()
async def list_resources() -> list[types.Resource]:
    return [
        types.Resource(
            uri="catalog://books",
            name="Library Catalog",
            description="List of all books with availability",
            mimeType="text/plain",
        ),
    ]

@app.read_resource()
async def read_resource(uri: str) -> str:
    if uri == "catalog://books":
        data = load_data()
        output = "📚 Library Catalog\n" + "="*30 + "\n"
        for b in data["books"]:
            status = "✅ Available" if b["available"] else "❌ Checked out"
            output += f"{b['id']}: {b['title']} – {b['author']} [{status}]\n"
        return output
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
                server_name="campus-library",
                server_version="1.0.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),  # FIXED!
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    print("📚 Campus Library MCP Server")
    print("="*40)
    print("Tools: search_book, check_availability, reserve_book")
    print("Resource: catalog://books")
    print("="*40)
    asyncio.run(main())