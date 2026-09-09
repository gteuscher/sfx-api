"""REST API and preview page over the same core as the MCP server.

Run with `sfx-http` or `sfx serve-http`. The MCP server is also mounted at /mcp over
Streamable HTTP for hosts that prefer that to stdio.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from importlib import resources
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from sfx import store
from sfx.server.mcp_server import mcp
from sfx.spec.models import SoundSpec, spec_json_schema

mcp_app = mcp.streamable_http_app(streamable_http_path="/")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="sfx-api", version="0.1.0", lifespan=lifespan, docs_url="/api/docs", redoc_url=None)
app.mount("/mcp", mcp_app)


def _out(out_dir: str | None) -> Path | None:
    return Path(out_dir) if out_dir else None


def _err(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


class RenderBody(BaseModel):
    spec: dict[str, Any]
    out_dir: str | None = None


class PresetBody(BaseModel):
    overrides: dict[str, Any] | None = None
    out_dir: str | None = None


class PatchBody(BaseModel):
    patch: dict[str, Any]
    out_dir: str | None = None


class VariationsBody(BaseModel):
    count: int = Field(4, ge=1, le=32)
    sound_id: str | None = None
    spec: dict[str, Any] | None = None
    out_dir: str | None = None


class SavePresetBody(BaseModel):
    name: str
    spec: dict[str, Any] | None = None
    sound_id: str | None = None
    out_dir: str | None = None


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def preview_page() -> str:
    return (resources.files("sfx") / "preview.html").read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "out_dir": str(store.default_out_dir())}


@app.get("/api/schema")
def schema() -> dict[str, Any]:
    return spec_json_schema()


@app.get("/api/cookbook")
def cookbook() -> dict[str, str]:
    return {"cookbook": (resources.files("sfx") / "cookbook.md").read_text(encoding="utf-8")}


@app.get("/api/presets")
def presets() -> dict[str, Any]:
    return store.all_presets()


@app.post("/api/render")
def render(body: RenderBody) -> dict[str, Any]:
    try:
        model = SoundSpec.model_validate(body.spec)
        result = store.render_to_file(model, _out(body.out_dir))
    except Exception as exc:  # validation or render error
        raise _err(exc)
    result["spec"] = model.model_dump(mode="json")
    return result


@app.post("/api/presets/{name}/render")
def render_preset(name: str, body: PresetBody | None = None) -> dict[str, Any]:
    body = body or PresetBody()
    try:
        base = store.get_preset(name).model_dump(mode="json")
        model = SoundSpec.model_validate(store.merge_patch(base, body.overrides or {}))
        result = store.render_to_file(model, _out(body.out_dir))
    except Exception as exc:
        raise _err(exc)
    result["spec"] = model.model_dump(mode="json")
    return result


@app.post("/api/presets")
def save_preset(body: SavePresetBody) -> dict[str, Any]:
    try:
        if body.spec is None and body.sound_id is None:
            raise ValueError("pass spec or sound_id")
        model = SoundSpec.model_validate(body.spec) if body.spec else store.load_spec(body.sound_id, _out(body.out_dir))
        model.name = store.safe_name(body.name)
        path = store.save_preset(body.name, model)
    except Exception as exc:
        raise _err(exc)
    return {"name": model.name, "path": str(path)}


@app.get("/api/renders")
def list_renders(out_dir: str | None = None, limit: int = 100) -> dict[str, Any]:
    return {"renders": store.list_renders(_out(out_dir), limit=limit)}


@app.get("/api/renders/{sound_id}/audio", include_in_schema=False)
@app.get("/api/renders/{sound_id}.wav")
def get_audio(sound_id: str, out_dir: str | None = None):
    try:
        path = store.resolve_path(sound_id, _out(out_dir))
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return FileResponse(str(path), media_type="audio/wav", filename=path.name)


@app.get("/api/renders/{sound_id}")
def get_render(sound_id: str, out_dir: str | None = None) -> dict[str, Any]:
    try:
        spec = store.load_spec(sound_id, _out(out_dir))
        info = store.analyze_file(sound_id, _out(out_dir))
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"id": sound_id, "spec": spec.model_dump(mode="json"), **info}


@app.post("/api/renders/{sound_id}/tweak")
def tweak(sound_id: str, body: PatchBody) -> dict[str, Any]:
    try:
        base = store.load_spec(sound_id, _out(body.out_dir)).model_dump(mode="json")
        model = SoundSpec.model_validate(store.merge_patch(base, body.patch))
        result = store.render_to_file(model, _out(body.out_dir))
    except Exception as exc:
        raise _err(exc)
    result["spec"] = model.model_dump(mode="json")
    return result


@app.post("/api/renders/{sound_id}/play")
def play(sound_id: str, out_dir: str | None = None) -> dict[str, Any]:
    try:
        return store.play(sound_id, _out(out_dir), block=False)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/variations")
def variations(body: VariationsBody) -> dict[str, Any]:
    try:
        if body.spec is None and body.sound_id is None:
            raise ValueError("pass sound_id or spec")
        model = SoundSpec.model_validate(body.spec) if body.spec else store.load_spec(body.sound_id, _out(body.out_dir))
        parent = body.sound_id if body.spec is None else None
        out = store.render_variations_to_files(model, body.count, _out(body.out_dir), parent_id=parent)
    except Exception as exc:
        raise _err(exc)
    return {"variations": out}


@app.exception_handler(HTTPException)
async def _http_exc(_request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


def main() -> None:
    import argparse

    import uvicorn

    p = argparse.ArgumentParser(prog="sfx-http", description="sfx-api REST server and preview page")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    a = p.parse_args()
    uvicorn.run(app, host=a.host, port=a.port, log_level="info")


if __name__ == "__main__":
    main()
