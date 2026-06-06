from __future__ import annotations

import argparse
import os
import traceback

from cert_study_app.db import SessionLocal, init_db
from cert_study_app.graphs.pdf_ingestion_graph import run_pdf_ingestion
from cert_study_app.services.ingestion_job_service import IngestionJobService


def run_job(job_id: int) -> dict:
    init_db(verbose=False)
    db = SessionLocal()
    service = IngestionJobService(db)
    try:
        job = service.start_job(job_id)
        if not job:
            raise RuntimeError(f"job {job_id} not found")

        def progress_callback(event: dict) -> None:
            progress_db = SessionLocal()
            try:
                IngestionJobService(progress_db).update_progress(job_id, event)
            finally:
                progress_db.close()

        result = run_pdf_ingestion(
            pdf_path=job.pdf_path,
            source_name=job.exam_name,
            use_llm=bool(job.use_llm),
            llm_provider="ollama",
            llm_model=job.llm_model,
            ollama_base_url=job.ollama_base_url,
            lang="korean",
            dpi=200,
            visual_batch_size=(int(job.visual_batch_size or 5) if job.auto_visual_analysis else 0),
            visual_model=os.getenv("OLLAMA_VISUAL_MODEL", "qwen3-vl:8b-instruct-q4_K_M"),
            progress_callback=progress_callback,
        )
        service.complete_job(
            job_id,
            inserted=int(result.get("inserted") or 0),
            output_json=result.get("output_json"),
            quality_score=(result.get("parse_quality") or {}).get("score"),
            quality_status=(result.get("quality_gate") or {}).get("status"),
            quality_report_json=result.get("quality_report_json"),
            quality_gate_json=result.get("quality_gate_json"),
            held=bool(result.get("skip_ingestion")),
        )
        return {
            "job_id": job_id,
            "pdf_path": result.get("pdf_path"),
            "source_name": result.get("source_name"),
            "output_json": result.get("output_json"),
            "quality_report_json": result.get("quality_report_json"),
            "quality_gate_json": result.get("quality_gate_json"),
            "parse_quality": result.get("parse_quality"),
            "quality_gate": result.get("quality_gate"),
            "held": bool(result.get("skip_ingestion")),
            "parsed_count": int(result.get("parsed_count") or 0),
            "inserted": int(result.get("inserted") or 0),
        }
    except Exception as exc:
        service.fail_job(job_id, f"{exc}\n{traceback.format_exc()}")
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("job_id", type=int)
    args = parser.parse_args()
    run_job(args.job_id)


if __name__ == "__main__":
    main()
