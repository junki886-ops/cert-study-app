from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task


@dag(
    dag_id="cert_study_visual_analysis",
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    tags=["cert-study", "qwen", "visual"],
)
def cert_study_visual_analysis():
    @task
    def analyze_visual_questions(
        source_name: str | None = None,
        limit: str | int = 10,
        model: str = "qwen3.5:9b",
    ) -> dict:
        from cert_study_app.db import SessionLocal, init_db
        from cert_study_app.services.visual_question_service import run_visual_analysis

        init_db(verbose=False)
        db = SessionLocal()
        try:
            return run_visual_analysis(
                db,
                source=source_name or None,
                limit=int(limit or 10),
                model=model,
            )
        finally:
            db.close()

    analyze_visual_questions(
        source_name="{{ dag_run.conf.get('source_name', '') }}",
        limit="{{ dag_run.conf.get('limit', 10) }}",
        model="{{ dag_run.conf.get('model', 'qwen3.5:9b') }}",
    )


cert_study_visual_analysis()
