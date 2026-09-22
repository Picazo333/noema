#!/usr/bin/env python3
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", default="ui/derived/snapshots/2026-10.actual.json")
    p.add_argument("--template", default="ui/monolith-template.html")
    p.add_argument("--out", default="ui/stackia.html")
    args = p.parse_args()

    snapshot = (ROOT / args.snapshot).read_text(encoding="utf-8").replace("</script", "<\\/script")
    template = (ROOT / args.template).read_text(encoding="utf-8")
    marker = "__STACKIA_DATA__"
    if template.count(marker) != 1:
        raise SystemExit("template must contain exactly one __STACKIA_DATA__ marker")
    output = template.replace(marker, snapshot)
    (ROOT / args.out).write_text(output, encoding="utf-8")
    print(f"wrote {args.out} ({len(output)} chars)")

if __name__ == "__main__":
    main()
