from mcp.server.mcpserver.server import MCPServer
import inspect

src = inspect.getsource(MCpServer)
lines = src.split('\n')
for i, line in enumerate(lines):
    if i >= 147 and i < 500:
        print(f'{i:3d}: {line}')
