"""Small CLI for local validation without an MCP client."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import (
    audit_existing_draft,
    audit_source_provenance,
    build_timeline,
    draft_arco_request,
    select_legal_basis,
    select_escalation_basis,
    validate_arco_case,
)


def _load_json(path: str) -> dict:
    try:
        with Path(path).open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        print(f"Error: archivo no encontrado: {path}", file=sys.stderr)
        raise SystemExit(1)
    except json.JSONDecodeError as exc:
        print(f"Error: JSON invalido en {path}: {exc}", file=sys.stderr)
        raise SystemExit(1)


def _dump(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="ARCO rights local CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_validate = sub.add_parser("validate", help="Validate a case JSON")
    p_validate.add_argument("case_json")

    p_basis = sub.add_parser("basis", help="Select legal basis for case JSON")
    p_basis.add_argument("case_json")

    p_source = sub.add_parser("source-audit", help="Audit source provenance for case JSON")
    p_source.add_argument("case_json")

    p_draft = sub.add_parser("draft", help="Draft request from case JSON")
    p_draft.add_argument("case_json")
    p_draft.add_argument("--force", action="store_true")

    p_audit = sub.add_parser("audit-draft", help="Audit an existing draft")
    p_audit.add_argument("draft_file")
    p_audit.add_argument("--case-json")

    p_time = sub.add_parser("timeline", help="Calculate business-day timeline")
    p_time.add_argument("fecha_recepcion")
    p_time.add_argument("--fecha-respuesta")
    p_time.add_argument("--fecha-presentacion-secretaria")
    p_time.add_argument("--fecha-notificacion-secretaria")
    p_time.add_argument("--holidays-json", default="[]")

    p_esc = sub.add_parser("escalation-basis", help="Get legal basis for escalation phase")
    p_esc.add_argument("--etapa", default="escalamiento_secretaria",
                       choices=["escalamiento_secretaria", "amparo"])

    args = parser.parse_args()

    if args.cmd == "validate":
        _dump(validate_arco_case(_load_json(args.case_json)))
    elif args.cmd == "basis":
        _dump(select_legal_basis(_load_json(args.case_json)))
    elif args.cmd == "source-audit":
        _dump(audit_source_provenance(_load_json(args.case_json)))
    elif args.cmd == "draft":
        _dump(draft_arco_request(_load_json(args.case_json), force=args.force))
    elif args.cmd == "audit-draft":
        draft = Path(args.draft_file).read_text(encoding="utf-8")
        case = _load_json(args.case_json) if args.case_json else None
        _dump(audit_existing_draft(draft, case))
    elif args.cmd == "timeline":
        holidays = json.loads(args.holidays_json)
        _dump(build_timeline(
            args.fecha_recepcion,
            args.fecha_respuesta,
            holidays,
            args.fecha_presentacion_secretaria,
            args.fecha_notificacion_secretaria,
        ))
    elif args.cmd == "escalation-basis":
        _dump(select_escalation_basis(args.etapa))
    else:
        parser.print_help()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
