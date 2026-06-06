from __future__ import annotations

import argparse
import json

from cert_study_app.services.parse_quality_service import (
    build_parse_quality_report,
    default_quality_report_path,
    summarize_quality_report,
)
from cert_study_app.services.quality_gate_service import (
    apply_quality_gate,
    default_gate_report_path,
    summarize_quality_gate,
)


def inspect_parse_quality(
    json_path: str,
    output_path: str | None = None,
    expected_count: int | None = None,
    apply_gate: bool = False,
) -> dict:
    report_path = output_path or default_quality_report_path(json_path)
    report = build_parse_quality_report(json_path, output_path=report_path, expected_count=expected_count)
    print(summarize_quality_report(report))
    print(f"report: {report_path}")
    if apply_gate:
        gate_path = default_gate_report_path(json_path)
        gate = apply_quality_gate(json_path, report, gate_report_path=gate_path)
        print(summarize_quality_gate(gate))
        print(f"gate: {gate_path}")
    if report.get("samples"):
        print("\npriority samples:")
        for sample in report["samples"][:10]:
            issue_codes = ", ".join(issue["code"] for issue in sample.get("issues", []))
            number = sample.get("number") or sample.get("index")
            page = sample.get("page") or "-"
            preview = sample.get("stem_preview") or sample.get("raw_preview") or ""
            print(f"- q{number} p{page}: {issue_codes} :: {preview[:120]}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect parsed question JSON quality.")
    parser.add_argument("json_path")
    parser.add_argument("--out", default=None)
    parser.add_argument("--expected-count", type=int, default=None)
    parser.add_argument("--apply-gate", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    args = parser.parse_args()
    report = inspect_parse_quality(args.json_path, args.out, args.expected_count, args.apply_gate)
    if args.print_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
