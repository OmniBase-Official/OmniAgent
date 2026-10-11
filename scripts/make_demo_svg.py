"""Render the demo as an animated SVG terminal cast for the README.

Why SVG rather than a GIF: it is a fraction of the size, stays sharp at any
zoom, and the text inside it is real text, so it can be searched and read by a
screen reader. GitHub renders it from an `<img>` tag in Markdown, and the
animation is CSS keyframes only -- no script, which GitHub would strip.

**The transcript is a snapshot of a real run**, not prose written to look like
one: `main.py --profile demo` on 2026-10-11, session f582a32fba9d, model
`omniagent-v2`, the run recorded in `data/demo-after-switch.txt`. The five
questions were piped in, so the `You >` lines carry no text in the capture and
are restored here from `docs/demo-script.md`, which is where they are measured.

Regenerate with:  .venv/Scripts/python.exe scripts/make_demo_svg.py
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "docs" / "demo1.svg"

#: (style, text). Styles map to the CSS classes below.
CAST: tuple[tuple[str, str], ...] = (
    ("cmd", "$ git clone https://github.com/mntoyg/OmniAgent.git"),
    ("cmd", "$ cd OmniAgent && python -m venv .venv && .venv\\Scripts\\activate"),
    ("cmd", "$ pip install -e ."),
    ("cmd", "$ ollama pull qwen2.5-coder:7b"),
    ("cmd", "$ python main.py --profile demo"),
    ("dim", ""),
    ("dim", "  local-only ReAct agent  -  no cloud, no framework"),
    ("dim", "    endpoint : http://localhost:11434/v1"),
    ("dim", "    model    : omniagent-v2"),
    ("dim", ""),
    ("you", "You > What is 144 * 12?"),
    ("step", "  [step 1]"),
    ("thought", "  Thought      : To solve this, I need the calculator tool."),
    ("action", "  Action       : calculate"),
    ("action", "  Action Input : 144 * 12"),
    ("obs", "  Observation  : 144 * 12 = 1728"),
    ("answer", "OmniAgent: 144 multiplied by 12 equals 1728."),
    ("dim", ""),
    ("you", "You > Now subtract 728 from that."),
    ("step", "  [step 1]"),
    ("action", "  Action       : calculate"),
    ("action", "  Action Input : 144 * 12 - 728"),
    ("obs", "  Observation  : 144 * 12 - 728 = 1000"),
    ("answer", "OmniAgent: The result of subtracting 728 from 144 multiplied by 12 is 1000."),
    ("dim", ""),
    ("you", "You > How many lines does tests/fakes.py have?"),
    ("step", "  [step 1]"),
    ("action", "  Action       : read_file"),
    ("err", "  Observation  : Error: tests/fakes.py is 3,670 characters, too long to"),
    ("err", "                 return in full. Use file_info for its size, first line"),
    ("err", "                 and last line, or search_text to find something inside."),
    ("step", "  [step 2]"),
    ("thought", "  Thought      : Since read_file cannot show me how many lines a long file"),
    ("thought", "                 has, I will use file_info instead."),
    ("action", "  Action       : file_info"),
    ("obs", "  Observation  : tests/fakes.py: 122 lines, 3,670 bytes"),
    ("answer", "OmniAgent: tests/fakes.py has 122 lines."),
    ("dim", ""),
    ("dim", "# the sandbox refused a read it could not answer, named the tool that"),
    ("dim", "# could, and the agent took the hint. 60/60 over twelve measured runs."),
)

#: Seconds each line waits before appearing, and how long the loop runs.
STEP = 0.45
TAIL = 4.0

STYLES = {
    "cmd": "#7ee787",
    "you": "#79c0ff",
    "step": "#6e7681",
    "thought": "#c9d1d9",
    "action": "#d2a8ff",
    "obs": "#a5d6ff",
    "err": "#ffa198",
    "answer": "#ffd866",
    "dim": "#6e7681",
}

LINE_HEIGHT = 19
PADDING_TOP = 44
WIDTH = 860


def render(cast: tuple[tuple[str, str], ...] = CAST) -> str:
    total = len(cast) * STEP + TAIL
    height = PADDING_TOP + len(cast) * LINE_HEIGHT + 20

    rules = [
        f".l{index} {{ animation: r {total}s steps(1) infinite; "
        f"animation-delay: {index * STEP:.2f}s; }}"
        for index in range(len(cast))
    ]
    # One keyframe set for every line: invisible until its delay elapses, then
    # visible for the rest of the loop. steps(1) keeps it from fading.
    keyframes = (
        "@keyframes r { 0% { opacity: 0 } "
        f"{100 * STEP / total:.3f}% {{ opacity: 1 }} 100% {{ opacity: 1 }} }}"
    )

    body = []
    for index, (style, text) in enumerate(cast):
        if not text:
            continue
        y = PADDING_TOP + index * LINE_HEIGHT
        body.append(
            f'<text class="l{index}" x="18" y="{y}" fill="{STYLES[style]}">{escape(text)}</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" \
viewBox="0 0 {WIDTH} {height}" font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" \
font-size="13" role="img" aria-label="OmniAgent demo: clone, install, and five measured questions">
<style>
text {{ opacity: 0; white-space: pre }}
{keyframes}
{chr(10).join(rules)}
</style>
<rect width="{WIDTH}" height="{height}" rx="8" fill="#0d1117"/>
<circle cx="20" cy="18" r="5" fill="#ff5f56"/><circle cx="38" cy="18" r="5" fill="#ffbd2e"/>\
<circle cx="56" cy="18" r="5" fill="#27c93f"/>
<text x="76" y="23" fill="#6e7681" font-size="12" style="opacity:1">OmniAgent — local-only, \
no framework</text>
{chr(10).join(body)}
</svg>
"""


def main() -> int:
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes, {len(CAST)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
