from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TypedDict

from cert_study_app.config import PARSED_DIR, ensure_runtime_dirs
from cert_study_app.agents.pdf_agents import (
    ClassifierAgent,
    CoordinatorAgent,
    IngestionAgent,
    ParseQualityAgent,
    QualityGateAgent,
    TextParserAgent,
    ValidatorAgent,
    VisualAgent,
    append_agent_result,
)
from cert_study_app.agents.base import AgentResult
from cert_study_app.db import SessionLocal


class PdfIngestionState(TypedDict, total=False):
    pdf_path: str
    source_name: str
    output_json: str
    use_llm: bool
    llm_provider: str
    llm_model: str
    ollama_base_url: str
    lang: str
    dpi: int
    progress_callback: object
    parsed_count: int
    expected_question_count: int
    quality_report_json: str
    parse_quality: dict
    quality_gate_json: str
    quality_gate: dict
    skip_ingestion: bool
    inserted: int
    visual_batch_size: int
    visual_model: str
    classification_summary: dict
    visual_summary: dict
    validation_summary: dict
    automation_summary: dict
    agent_results: list


def _default_output_path() -> str:
    ensure_runtime_dirs()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(PARSED_DIR / f"parsed_{ts}.json")


def parse_pdf_node(state: PdfIngestionState) -> PdfIngestionState:
    output_json = state.get("output_json") or _default_output_path()
    next_state, result = TextParserAgent().run({**state, "output_json": output_json})
    return append_agent_result(next_state, result)


def ingest_questions_node(state: PdfIngestionState) -> PdfIngestionState:
    next_state, result = IngestionAgent().run(state)
    return append_agent_result(next_state, result)


def parse_quality_node(state: PdfIngestionState) -> PdfIngestionState:
    next_state, result = ParseQualityAgent().run(state)
    return append_agent_result(next_state, result)


def quality_gate_node(state: PdfIngestionState) -> PdfIngestionState:
    next_state, result = QualityGateAgent().run(state)
    return append_agent_result(next_state, result)


def coordinator_start_node(state: PdfIngestionState) -> PdfIngestionState:
    result = CoordinatorAgent().start(state.get("progress_callback"))
    return append_agent_result(state, result)


def classify_questions_node(state: PdfIngestionState) -> PdfIngestionState:
    next_state, result = ClassifierAgent().run(state)
    return append_agent_result(next_state, result)


def visual_questions_node(state: PdfIngestionState) -> PdfIngestionState:
    next_state, result = VisualAgent().run(state)
    return append_agent_result(next_state, result)


def validate_questions_node(state: PdfIngestionState) -> PdfIngestionState:
    next_state, result = ValidatorAgent().run(state)
    return append_agent_result(next_state, result)


def coordinator_finish_node(state: PdfIngestionState) -> PdfIngestionState:
    if state.get("skip_ingestion"):
        gate = state.get("quality_gate") or {}
        result = AgentResult(
            "coordinator",
            status="held",
            message=gate.get("reason") or "quality gate held ingestion",
            metrics=gate,
        )
        return append_agent_result(state, result)
    db = SessionLocal()
    try:
        result = CoordinatorAgent().finish(db, state.get("source_name"), state.get("progress_callback"))
    finally:
        db.close()
    return append_agent_result(state, result)


def build_pdf_ingestion_graph():
    from langgraph.graph import END, StateGraph

    graph = StateGraph(PdfIngestionState)
    graph.add_node("coordinator_start", coordinator_start_node)
    graph.add_node("parse_pdf", parse_pdf_node)
    graph.add_node("parse_quality", parse_quality_node)
    graph.add_node("quality_gate", quality_gate_node)
    graph.add_node("ingest_questions", ingest_questions_node)
    graph.add_node("classify_questions", classify_questions_node)
    graph.add_node("visual_questions", visual_questions_node)
    graph.add_node("validate_questions", validate_questions_node)
    graph.add_node("coordinator_finish", coordinator_finish_node)
    graph.set_entry_point("coordinator_start")
    graph.add_edge("coordinator_start", "parse_pdf")
    graph.add_edge("parse_pdf", "parse_quality")
    graph.add_edge("parse_quality", "quality_gate")
    graph.add_edge("quality_gate", "ingest_questions")
    graph.add_edge("ingest_questions", "classify_questions")
    graph.add_edge("classify_questions", "visual_questions")
    graph.add_edge("visual_questions", "validate_questions")
    graph.add_edge("validate_questions", "coordinator_finish")
    graph.add_edge("coordinator_finish", END)
    return graph.compile()


def run_pdf_ingestion(**kwargs) -> PdfIngestionState:
    if kwargs.get("progress_callback"):
        state = coordinator_start_node(kwargs)
        state = parse_pdf_node(state)
        state = parse_quality_node(state)
        state = quality_gate_node(state)
        state = ingest_questions_node(state)
        state = classify_questions_node(state)
        state = visual_questions_node(state)
        state = validate_questions_node(state)
        return coordinator_finish_node(state)
    try:
        graph = build_pdf_ingestion_graph()
        return graph.invoke(kwargs)
    except ImportError:
        state = parse_pdf_node(kwargs)
        state = parse_quality_node(state)
        state = quality_gate_node(state)
        return ingest_questions_node(state)
