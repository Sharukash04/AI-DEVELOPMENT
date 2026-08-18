import asyncio

from mcp.server import MCPServer
from mcp.server.stdio import stdio_server


server=MCPServer(
    name="E-Commerce Order Server",
    version="1.0.0"
)


@server.tool()
async def hello() -> str:
    """Return a simple message from the E-Commerce MCP server."""
    return "E-Commerce MCP server is running"


async def main():
    async with stdio_server() as streams:
        await server.run_stdio_async(
            streams[0],
            streams[1],
            server.create_initialization_options()
        )


if __name__=="__main__":
    asyncio.run(main())