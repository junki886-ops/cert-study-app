from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task


@dag(
    dag_id="cert_study_pdf_ingestion",
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    tags=["cert-study", "langgraph", "pdf"],
)
def cert_study_pdf_ingestion():
    @task
    def ingest_pdf(
        pdf_path: str,
        source_name: str | None = None,
        use_llm: str | bool = True,
        llm_model: str = "qwen2.5:14b",
        ollama_base_url: str = "http://host.docker.internal:11434",
        job_id: str | int | None = None,
    ) -> dict:
        if job_id in (None, "", "None"):
            raise ValueError("job_id is required. Create an ingestion_jobs row before triggering this DAG.")

        from cert_study_app.jobs.run_ingestion_job import run_job

        return run_job(int(job_id))

    ingest_pdf(
        pdf_path="{{ dag_run.conf.get('pdf_path', 'data/uploads/sample.pdf') }}",
        source_name="{{ dag_run.conf.get('source_name', '') }}",
        use_llm="{{ dag_run.conf.get('use_llm', True) }}",
        llm_model="{{ dag_run.conf.get('llm_model', 'qwen2.5:14b') }}",
        ollama_base_url="{{ dag_run.conf.get('ollama_base_url', 'http://host.docker.internal:11434') }}",
        job_id="{{ dag_run.conf.get('job_id', '') }}",
    )


cert_study_pdf_ingestion()
