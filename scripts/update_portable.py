"""Stage/apply program-only updates; keep the documented CLI backwards compatible."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from companion.program_update import (PROGRAM_ROOTS, UPDATE_ROOTS, digest, checked_child,
    personal_snapshot, running_instances, stage_update, apply_update)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--sha256")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        if not args.plan:
            parser.error("--apply requires --plan")
        print(json.dumps(apply_update(args.plan, args.target), ensure_ascii=True))
    else:
        if not args.archive or not args.sha256:
            parser.error("Staging requires --archive and --sha256")
        print(json.dumps({"staged": str(stage_update(args.archive, args.target, args.sha256)), "applied": False}, ensure_ascii=True))


if __name__ == "__main__":
    main()
