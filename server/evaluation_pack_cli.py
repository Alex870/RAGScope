from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .evaluation import EvaluationPack, JudgedDataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or validate a podcast-evaluation-pack-v1 manifest without copying private data.")
    sub = parser.add_subparsers(dest="command", required=True)
    template = sub.add_parser("template")
    template.add_argument("output", type=Path)
    template.add_argument("--pack-id", default="local-podcast-evaluation")
    validate = sub.add_parser("validate")
    validate.add_argument("pack", type=Path)
    validate.add_argument("--base-path", type=Path)
    validate.add_argument("--document-ids", type=Path)
    validate.add_argument("--source-span-ids", type=Path)
    args = parser.parse_args()
    if args.command == "template":
        now = datetime.now(timezone.utc).isoformat()
        pack = EvaluationPack(args.pack_id, JudgedDataset("Local podcast evaluation", "unassigned", []), [], created_at=now, updated_at=now)
        pack.save(args.output)
        print(json.dumps({"created": str(args.output), "format": pack.format, "pack_id": pack.pack_id}))
        return 0
    document_ids = json.loads(args.document_ids.read_text(encoding="utf-8")) if args.document_ids else []
    span_ids = json.loads(args.source_span_ids.read_text(encoding="utf-8")) if args.source_span_ids else []
    pack = EvaluationPack.load(args.pack)
    report = pack.validate(args.base_path or args.pack.parent, available_document_ids=document_ids, available_source_span_ids=span_ids)
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
