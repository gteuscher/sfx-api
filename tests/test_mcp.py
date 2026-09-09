"""Drive the MCP server as a real stdio subprocess, the way Claude Code and Codex do."""

import os
import sys

import pytest

pytest.importorskip("mcp")

from mcp.client.session import ClientSession  # noqa: E402
from mcp.client.stdio import StdioServerParameters, stdio_client  # noqa: E402


@pytest.mark.anyio
async def test_tools_and_resources(tmp_path):
    env = dict(os.environ, SFX_NO_PLAYBACK="1", SFX_OUT_DIR=str(tmp_path))
    params = StdioServerParameters(command=sys.executable, args=["-m", "sfx.server.mcp_server"], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()

            tools = await client.list_tools()
            names = {t.name for t in tools.tools}
            assert {"sfx_render", "sfx_render_preset", "sfx_tweak", "sfx_variations", "sfx_play", "sfx_analyze"} <= names

            res = await client.read_resource("sfx://cookbook")
            assert "Laser" in res.contents[0].text

            r = await client.call_tool("sfx_render_preset", {"name": "coin"})
            assert not r.is_error, r.content
            data = r.structured_content
            assert os.path.exists(data["path"])
            sound_id = data["id"]

            t = await client.call_tool("sfx_tweak", {"sound_id": sound_id, "patch": {"master": {"target_lufs": -12}}})
            assert not t.is_error, t.content
            assert t.structured_content["spec"]["master"]["target_lufs"] == -12

            v = await client.call_tool("sfx_variations", {"sound_id": sound_id, "count": 2})
            assert not v.is_error, v.content
            assert len(v.structured_content["variations"]) == 2

            p = await client.call_tool("sfx_play", {"sound_id": sound_id})
            assert p.structured_content["played"] is False

            bad = await client.call_tool("sfx_render", {"spec": {"layers": [{"source": {"type": "nope"}}]}})
            assert bad.is_error
