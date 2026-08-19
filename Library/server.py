import json
import logging
import sys
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Setup logging ONLY to sys.stderr (Crucial: stdout breaks stdio MCP transport)
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

DATA_FILE = Path(__file__).parent / "library_data.json"

# Initialize FastMCP Server
mcp = FastMCP("Campus Library MCP Server")

def log_audit(tool_name: str, args: dict):
    """Audit logger requirement: logs timestamp and sanitized arguments."""
    sanitized_args = {
        k: ("***" if "pass" in k.lower() or "token" in k.lower() else v)
        for k, v in args.items()
    }
    logging.info(f"AUDIT LOG | Tool Invoked: '{tool_name}' | Arguments: {json.dumps(sanitized_args)}")

def load_data() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"books": []}

def save_data(data: dict):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

@mcp.tool()
def search_book(query: str) -> list[dict]:
    """Search for books in the campus library catalog by title or author.
    
    Args:
        query: Search keyword for title or author name.
    """
    log_audit("search_book", {"query": query})
    data = load_data()
    q = query.lower()
    return [
        b for b in data["books"]
        if q in b["title"].lower() or q in b["author"].lower()
    ]

@mcp.tool()
def check_availability(book_id: str) -> dict:
    """Check status and reservation state of a specific book by ID.
    
    Args:
        book_id: Unique identifier for the book (e.g., 'B001').
    """
    log_audit("check_availability", {"book_id": book_id})
    data = load_data()
    for book in data["books"]:
        if book["id"] == book_id:
            return {
                "book_id": book["id"],
                "title": book["title"],
                "available": book["available"],
                "reserved_by": book["reserved_by"]
            }
    return {"error": "Book not found", "book_id": book_id}

@mcp.tool()
def reserve_book(book_id: str, student_name: str) -> dict:
    """Reserve an available book for a specific student.
    
    Args:
        book_id: ID of the book to reserve.
        student_name: Full name of the requesting student.
    """
    log_audit("reserve_book", {"book_id": book_id, "student_name": student_name})
    data = load_data()
    for book in data["books"]:
        if book["id"] == book_id:
            if not book["available"]:
                return {
                    "success": False,
                    "message": f"Book '{book['title']}' is already reserved by {book['reserved_by']}."
                }
            book["available"] = False
            book["reserved_by"] = student_name
            save_data(data)
            return {
                "success": True,
                "message": f"Book '{book['title']}' successfully reserved for {student_name}."
            }
    return {"success": False, "message": f"Book ID '{book_id}' not found."}

@mcp.resource("catalog://books")
def get_catalog() -> str:
    """Retrieve the complete current catalog of books as JSON."""
    logging.info("AUDIT LOG | Resource Requested: catalog://books")
    data = load_data()
    return json.dumps(data["books"], indent=2)

if __name__ == "__main__":
    mcp.run()