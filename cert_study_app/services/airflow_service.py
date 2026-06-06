from __future__ import annotations

import os
from datetime import datetime

import requests


class AirflowTriggerError(RuntimeError):
    pass


class AirflowService:
    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ):
        self.base_url = (base_url or os.getenv("AIRFLOW_API_BASE_URL") or "http://localhost:8080").rstrip("/")
        self.username = username or os.getenv("AIRFLOW_API_USERNAME") or "admin"
        self.password = password or os.getenv("AIRFLOW_API_PASSWORD") or "admin"

    def trigger_pdf_ingestion(
        self,
        job_id: int,
        pdf_path: str,
        source_name: str,
        use_llm: bool,
        llm_model: str,
        ollama_base_url: str,
    ) -> dict:
        dag_id = "cert_study_pdf_ingestion"
        url = f"{self.base_url}/api/v1/dags/{dag_id}/dagRuns"
        run_id = f"cert_study_job_{job_id}_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}"
        payload = {
            "dag_run_id": run_id,
            "conf": {
                "job_id": job_id,
                "pdf_path": pdf_path,
                "source_name": source_name,
                "use_llm": use_llm,
                "llm_model": llm_model,
                "ollama_base_url": ollama_base_url,
            },
        }

        try:
            response = requests.post(
                url,
                json=payload,
                auth=(self.username, self.password),
                timeout=10,
            )
        except requests.RequestException as exc:
            raise AirflowTriggerError(f"Airflow API 연결 실패: {exc}") from exc

        if response.status_code >= 400:
            raise AirflowTriggerError(
                f"Airflow DAG trigger 실패 ({response.status_code}): {response.text[:500]}"
            )
        return response.json()

    def trigger_visual_analysis(
        self,
        source_name: str | None = None,
        limit: int = 20,
        model: str | None = None,
    ) -> dict:
        dag_id = "cert_study_visual_analysis"
        url = f"{self.base_url}/api/v1/dags/{dag_id}/dagRuns"
        run_id = f"cert_study_visual_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}"
        payload = {
            "dag_run_id": run_id,
            "conf": {
                "source_name": source_name or "",
                "limit": int(limit),
                "model": model or os.getenv("OLLAMA_VISUAL_MODEL", "qwen3-vl:8b-instruct-q4_K_M"),
            },
        }

        try:
            response = requests.post(
                url,
                json=payload,
                auth=(self.username, self.password),
                timeout=10,
            )
        except requests.RequestException as exc:
            raise AirflowTriggerError(f"Airflow API 연결 실패: {exc}") from exc

        if response.status_code >= 400:
            raise AirflowTriggerError(
                f"Airflow 이미지 분석 DAG trigger 실패 ({response.status_code}): {response.text[:500]}"
            )
        return response.json()

    def list_dag_runs(self, dag_id: str, limit: int = 5) -> list[dict]:
        url = f"{self.base_url}/api/v1/dags/{dag_id}/dagRuns"
        try:
            response = requests.get(
                url,
                params={"limit": max(int(limit), 50)},
                auth=(self.username, self.password),
                timeout=8,
            )
        except requests.RequestException as exc:
            raise AirflowTriggerError(f"Airflow API 연결 실패: {exc}") from exc

        if response.status_code >= 400:
            raise AirflowTriggerError(
                f"Airflow DAG 상태 조회 실패 ({response.status_code}): {response.text[:500]}"
            )
        runs = response.json().get("dag_runs", [])
        return sorted(
            runs,
            key=lambda run: run.get("logical_date") or run.get("execution_date") or run.get("start_date") or "",
            reverse=True,
        )[: int(limit)]
