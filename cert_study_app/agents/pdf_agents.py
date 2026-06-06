from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

from cert_study_app.agents.base import AgentResult
from cert_study_app.config import PARSED_DIR, ensure_runtime_dirs
from cert_study_app.db import SessionLocal
from cert_study_app.models import Question
from cert_study_app.services.ingestion_service import ingest_questions
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
from cert_study_app.services.question_review_service import run_auto_review
from cert_study_app.services.question_type_metadata_service import automation_summary
from cert_study_app.services.visual_question_service import run_visual_analysis


ProgressCallback = Optional[Callable[[dict], None]]


def emit(callback: ProgressCallback, stage: str, message: str, current: int = 0, total: int = 1) -> None:
    if callback:
        callback({"stage": stage, "message": message, "current": current, "total": total})


def skipped_agent_result(agent_name: str, state: dict, summary_key: str, summary: dict | None = None) -> tuple[dict, AgentResult]:
    payload = summary or {"checked": 0, "skipped": True}
    return {**state, summary_key: payload}, AgentResult(
        agent_name,
        status="skipped",
        message="quality gate held ingestion",
        metrics=payload,
    )


class CoordinatorAgent:
    name = "coordinator"

    def start(self, callback: ProgressCallback = None) -> AgentResult:
        emit(callback, "coordinator", "자동 정리 파이프라인을 시작합니다.", 0, 1)
        return AgentResult(self.name, message="started")

    def finish(self, db, source: str | None = None, callback: ProgressCallback = None) -> AgentResult:
        summary = automation_summary(db, source)
        emit(
            callback,
            "done",
            f"자동 정리 완료: 풀이 가능 {summary['playable']}개, 이미지 분석 대기 {summary['image_needed']}개",
            summary["playable"],
            max(summary["total"], 1),
        )
        return AgentResult(self.name, message="finished", metrics=summary)


class TextParserAgent:
    name = "text_parser"

    def run(self, state: dict) -> tuple[dict, AgentResult]:
        from pdf_parser_adaptive import parse_pdf

        ensure_runtime_dirs()
        output_json = state.get("output_json") or str(PARSED_DIR / "parsed_agent_output.json")
        results = parse_pdf(
            state["pdf_path"],
            output_json,
            use_llm=state.get("use_llm", True),
            lang=state.get("lang", "korean"),
            dpi=state.get("dpi", 200),
            llm_provider=state.get("llm_provider"),
            llm_model=state.get("llm_model"),
            ollama_base_url=state.get("ollama_base_url"),
            progress_callback=state.get("progress_callback"),
        )
        next_state = {**state, "output_json": output_json, "parsed_count": len(results or [])}
        return next_state, AgentResult(self.name, message="parsed", metrics={"parsed_count": len(results or [])}, artifacts={"output_json": output_json})


class IngestionAgent:
    name = "ingestion"

    def run(self, state: dict) -> tuple[dict, AgentResult]:
        if state.get("skip_ingestion"):
            callback = state.get("progress_callback")
            emit(callback, "db", "품질 게이트 보류로 DB 적재를 건너뜁니다.", 1, 1)
            return {**state, "inserted": 0}, AgentResult(
                self.name,
                status="skipped",
                message="quality gate held ingestion",
                metrics={"inserted": 0},
            )
        callback = state.get("progress_callback")
        emit(callback, "db", "파싱 결과를 DB에 적재합니다.", 0, 1)
        inserted = ingest_questions(
            state["output_json"],
            source_name=state.get("source_name") or Path(state["pdf_path"]).name,
        )
        emit(callback, "db", f"{inserted}개 문항을 DB에 적재했습니다.", 1, 1)
        return {**state, "inserted": inserted}, AgentResult(self.name, message="ingested", metrics={"inserted": inserted})


class ParseQualityAgent:
    name = "parse_quality"

    def run(self, state: dict) -> tuple[dict, AgentResult]:
        callback = state.get("progress_callback")
        output_json = state["output_json"]
        report_path = state.get("quality_report_json") or default_quality_report_path(output_json)
        emit(callback, "parse_quality", "파싱/청킹 품질 리포트를 생성합니다.", 0, 1)
        report = build_parse_quality_report(
            output_json,
            output_path=report_path,
            expected_count=state.get("expected_question_count"),
        )
        summary = summarize_quality_report(report)
        emit(callback, "parse_quality", summary, 1, 1)
        metrics = {
            "score": report["score"],
            "status": report["status"],
            "question_count": report["question_count"],
            "issue_counts": report["issue_counts"],
        }
        return (
            {**state, "quality_report_json": report_path, "parse_quality": report},
            AgentResult(self.name, message=summary, metrics=metrics, artifacts={"quality_report_json": report_path}),
        )


class QualityGateAgent:
    name = "quality_gate"

    def run(self, state: dict) -> tuple[dict, AgentResult]:
        callback = state.get("progress_callback")
        output_json = state["output_json"]
        report = state.get("parse_quality")
        if not report:
            report = build_parse_quality_report(output_json)
        gate_path = state.get("quality_gate_json") or default_gate_report_path(output_json)
        emit(callback, "quality_gate", "품질 게이트를 적용합니다.", 0, 1)
        gate = apply_quality_gate(
            output_json,
            report,
            gate_report_path=gate_path,
            pass_score=int(state.get("quality_pass_score") or 85),
            warn_score=int(state.get("quality_warn_score") or 70),
        )
        summary = summarize_quality_gate(gate)
        emit(callback, "quality_gate", summary, 1, 1)
        skip_ingestion = gate["action"] == "hold"
        return (
            {
                **state,
                "quality_gate": gate,
                "quality_gate_json": gate_path,
                "skip_ingestion": skip_ingestion,
            },
            AgentResult(self.name, message=summary, metrics=gate, artifacts={"quality_gate_json": gate_path}),
        )


class ClassifierAgent:
    name = "classifier"

    def run(self, state: dict) -> tuple[dict, AgentResult]:
        if state.get("skip_ingestion"):
            return skipped_agent_result(self.name, state, "classification_summary")
        db = SessionLocal()
        try:
            summary = run_auto_review(db, source=state.get("source_name"), limit=1000, approve=True)
        finally:
            db.close()
        return {**state, "classification_summary": summary}, AgentResult(self.name, message="classified", metrics=summary)


class VisualAgent:
    name = "visual"

    def run(self, state: dict) -> tuple[dict, AgentResult]:
        if state.get("skip_ingestion"):
            return skipped_agent_result(
                self.name,
                state,
                "visual_summary",
                {"checked": 0, "approved": 0, "needs_visual": 0, "failed": 0, "skipped": True},
            )
        batch = int(state.get("visual_batch_size") or 0)
        if batch <= 0:
            return {**state, "visual_summary": {"checked": 0, "approved": 0, "needs_visual": 0, "failed": 0}}, AgentResult(
                self.name,
                message="skipped",
            )

        db = SessionLocal()
        try:
            summary = run_visual_analysis(
                db,
                source=state.get("source_name"),
                limit=batch,
                model=state.get("visual_model") or os.getenv("OLLAMA_VISUAL_MODEL", "qwen3-vl:8b-instruct-q4_K_M"),
            )
        finally:
            db.close()
        return {**state, "visual_summary": summary}, AgentResult(self.name, message="visual_analyzed", metrics=summary)


class ValidatorAgent:
    name = "validator"

    def run(self, state: dict) -> tuple[dict, AgentResult]:
        if state.get("skip_ingestion"):
            next_state, result = skipped_agent_result(self.name, state, "validation_summary")
            return {**next_state, "automation_summary": {}}, result
        db = SessionLocal()
        try:
            summary = run_auto_review(db, source=state.get("source_name"), limit=1000, approve=True)
            final = automation_summary(db, state.get("source_name"))
        finally:
            db.close()
        return {**state, "validation_summary": summary, "automation_summary": final}, AgentResult(
            self.name,
            message="validated",
            metrics={"review": summary, "automation": final},
        )


def append_agent_result(state: dict, result: AgentResult) -> dict:
    return {**state, "agent_results": [*(state.get("agent_results") or []), result.to_dict()]}
