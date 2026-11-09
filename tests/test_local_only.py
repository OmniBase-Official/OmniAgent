"""Keep the smoke test's documentation aligned with local-only training."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_smoke_train_does_not_point_the_reader_at_a_hosted_notebook() -> None:
    """The manifest records an RTX 3050 Laptop GPU; standard 1 is local only."""
    source_path = REPO_ROOT / "scripts" / "smoke_train.py"
    source = source_path.read_text(encoding="utf-8")
    offending = next(
        (line.strip() for line in source.splitlines() if "colab" in line.lower()),
        "",
    )

    assert "colab" not in source.lower(), (
        f"{source_path} contains hosted notebook framing: {offending}"
    )
