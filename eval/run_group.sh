#!/usr/bin/env bash
# usage: run_group.sh <claude|codex> <A|B|C|D>
set -u
host=$1; group=$2
cd /c/dev/sfx-api
prompt="$(sed "s/GROUP/$group/g" eval/prompt_template.txt)"
prompt="$prompt
$(python -c "import json,sys; [print(f'{i+1}. {d}') for i,d in enumerate(json.load(open('eval/targets.json'))['$group'])]")"
mkdir -p eval/results
if [ "$host" = "claude" ]; then
  claude -p "$prompt" --mcp-config "C:/dev/sfx-api/eval/mcp.json" --strict-mcp-config --allowedTools mcp__sfx \
    --output-format json --max-turns 60 > "eval/results/claude_$group.json" 2> "eval/results/claude_$group.err"
else
  # TOML literal strings (single quotes) so Windows backslashes need no escaping
  codex exec \
    -c "mcp_servers.sfx.command='C:\dev\sfx-api\.venv\Scripts\sfx-mcp.exe'" \
    -c "mcp_servers.sfx.env.SFX_OUT_DIR='C:\dev\sfx-api\out\eval'" \
    -c "mcp_servers.sfx.env.SFX_NO_PLAYBACK='1'" \
    --dangerously-bypass-approvals-and-sandbox -o "eval/results/codex_$group.last.txt" "$prompt" \
    > "eval/results/codex_$group.log" 2> "eval/results/codex_$group.err"
fi
echo "$host $group exit=$?"
