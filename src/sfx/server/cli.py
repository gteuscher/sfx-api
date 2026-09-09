"""Command line: render specs and presets, play, analyze, serve."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sfx import store
from sfx.spec.models import SoundSpec, spec_json_schema


def _load_spec(path: str) -> SoundSpec:
    return SoundSpec.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _print(obj) -> None:
    print(json.dumps(obj, indent=2))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sfx", description="Parametric game SFX synthesis")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("render", help="render a spec JSON file to WAV")
    r.add_argument("spec")
    r.add_argument("-o", "--out-dir")
    r.add_argument("--play", action="store_true")

    pr = sub.add_parser("preset", help="render a named preset")
    pr.add_argument("name")
    pr.add_argument("-o", "--out-dir")
    pr.add_argument("--play", action="store_true")
    pr.add_argument("--set", action="append", default=[], metavar="JSON", help="merge patch, may repeat")

    v = sub.add_parser("variations", help="render randomized siblings of a spec, preset, or render id")
    v.add_argument("source", help="spec file, preset name, or render id")
    v.add_argument("-n", "--count", type=int, default=4)
    v.add_argument("-o", "--out-dir")

    pl = sub.add_parser("play", help="play a WAV by path or id")
    pl.add_argument("target")
    pl.add_argument("-o", "--out-dir")

    an = sub.add_parser("analyze", help="print features of a WAV")
    an.add_argument("target")
    an.add_argument("-o", "--out-dir")

    sub.add_parser("list", help="list presets")
    sub.add_parser("schema", help="print the SoundSpec JSON schema")
    sub.add_parser("cookbook", help="print the cookbook")

    d = sub.add_parser("demo", help="render every preset")
    d.add_argument("-o", "--out-dir")
    d.add_argument("--play", action="store_true")

    sub.add_parser("serve", help="run the MCP server over stdio")

    a = p.parse_args(argv)
    out_dir = Path(a.out_dir) if getattr(a, "out_dir", None) else None

    if a.cmd == "render":
        res = store.render_to_file(_load_spec(a.spec), out_dir)
        _print(res)
        if a.play:
            store.play(res["path"])
    elif a.cmd == "preset":
        spec = store.get_preset(a.name).model_dump(mode="json")
        for patch in a.set:
            spec = store.merge_patch(spec, json.loads(patch))
        res = store.render_to_file(SoundSpec.model_validate(spec), out_dir)
        _print(res)
        if a.play:
            store.play(res["path"])
    elif a.cmd == "variations":
        src = a.source
        if Path(src).suffix == ".json" and Path(src).exists():
            spec = _load_spec(src)
        elif src in store.all_presets():
            spec = store.get_preset(src)
        else:
            spec = store.load_spec(src, out_dir)
        _print(store.render_variations_to_files(spec, a.count, out_dir))
    elif a.cmd == "play":
        _print(store.play(a.target, out_dir))
    elif a.cmd == "analyze":
        _print(store.analyze_file(a.target, out_dir))
    elif a.cmd == "list":
        for name in store.all_presets():
            print(name)
    elif a.cmd == "schema":
        _print(spec_json_schema())
    elif a.cmd == "cookbook":
        from importlib import resources

        print((resources.files("sfx") / "cookbook.md").read_text(encoding="utf-8"))
    elif a.cmd == "demo":
        for name in store.all_presets():
            res = store.render_to_file(store.get_preset(name), out_dir)
            f = res["features"]
            print(f"{name:16s} {f['duration_ms']:7.1f} ms  {f['lufs']!s:>7} LUFS  {res['path']}  {' '.join(res['warnings'])}")
            if a.play:
                store.play(res["path"])
    elif a.cmd == "serve":
        from sfx.server.mcp_server import main as serve

        serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
