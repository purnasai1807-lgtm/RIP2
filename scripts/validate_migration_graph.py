"""Validate that Alembic revisions form one linear chain with no missing parents."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "migrations" / "versions"


def main() -> int:
    revisions: dict[str, str | None] = {}
    for path in sorted(VERSIONS.glob("*.py")):
        if path.name.startswith("__"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        values = {}
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                value_node = node.value
                for target in targets:
                    if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}:
                        try:
                            values[target.id] = ast.literal_eval(value_node)
                        except Exception:
                            pass
        revision = values.get("revision")
        down = values.get("down_revision")
        if not isinstance(revision, str):
            raise SystemExit(f"{path.name}: missing string revision")
        if revision in revisions:
            raise SystemExit(f"Duplicate revision id: {revision}")
        if down is not None and not isinstance(down, str):
            raise SystemExit(f"{path.name}: merge/branch migration needs manual review")
        revisions[revision] = down
    missing = [(rev, parent) for rev, parent in revisions.items() if parent is not None and parent not in revisions]
    if missing:
        raise SystemExit("Missing migration parents: " + ", ".join(f"{rev}->{parent}" for rev, parent in missing))
    roots = [rev for rev, parent in revisions.items() if parent is None]
    if len(roots) != 1:
        raise SystemExit(f"Expected one migration root, found {len(roots)}: {roots}")
    children: dict[str, list[str]] = {rev: [] for rev in revisions}
    for rev, parent in revisions.items():
        if parent is not None:
            children[parent].append(rev)
    if any(len(kids) > 1 for kids in children.values()):
        raise SystemExit("Migration graph contains branches; add a reviewed merge migration.")
    seen = set()
    cursor = roots[0]
    while cursor:
        if cursor in seen:
            raise SystemExit(f"Migration cycle detected at {cursor}")
        seen.add(cursor)
        cursor = children[cursor][0] if children[cursor] else None
    if seen != set(revisions):
        raise SystemExit(f"Disconnected migration revisions: {sorted(set(revisions) - seen)}")
    head = next(rev for rev, kids in children.items() if not kids)
    print(f"PASS: {len(revisions)} migrations form one linear chain ({roots[0]} → {head}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
