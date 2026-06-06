from __future__ import annotations

from datetime import datetime

from cert_study_app.models import IngestionJob


class IngestionJobService:
    def __init__(self, db):
        self.db = db

    def create_job(
        self,
        exam_name: str,
        pdf_path: str,
        use_llm: bool,
        llm_model: str,
        ollama_base_url: str,
        auto_visual_analysis: bool = True,
        visual_batch_size: int = 5,
    ) -> IngestionJob:
        job = IngestionJob(
            exam_name=exam_name,
            pdf_path=pdf_path,
            status="queued",
            stage="queued",
            message="작업 대기 중",
            current=0,
            total=1,
            use_llm=use_llm,
            llm_model=llm_model,
            ollama_base_url=ollama_base_url,
            auto_visual_analysis=auto_visual_analysis,
            visual_batch_size=visual_batch_size,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get_job(self, job_id: int) -> IngestionJob | None:
        return self.db.query(IngestionJob).filter(IngestionJob.id == job_id).first()

    def list_jobs(self, limit: int = 20) -> list[IngestionJob]:
        return (
            self.db.query(IngestionJob)
            .order_by(IngestionJob.id.desc())
            .limit(limit)
            .all()
        )

    def start_job(self, job_id: int) -> IngestionJob | None:
        job = self.get_job(job_id)
        if not job:
            return None
        job.status = "running"
        job.stage = "start"
        job.message = "파싱 작업을 시작합니다."
        job.started_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(job)
        return job

    def update_progress(self, job_id: int, event: dict) -> None:
        job = self.get_job(job_id)
        if not job:
            return
        job.status = "running"
        job.stage = str(event.get("stage") or job.stage or "running")
        job.message = str(event.get("message") or "")
        job.current = int(event.get("current") or 0)
        job.total = max(int(event.get("total") or 1), 1)
        job.updated_at = datetime.utcnow()
        self.db.commit()

    def mark_queued(self, job_id: int, message: str = "Airflow 실행 대기 중") -> None:
        job = self.get_job(job_id)
        if not job:
            return
        job.status = "queued"
        job.stage = "airflow"
        job.message = message
        job.updated_at = datetime.utcnow()
        self.db.commit()

    def complete_job(
        self,
        job_id: int,
        inserted: int,
        output_json: str | None = None,
        quality_score: int | None = None,
        quality_status: str | None = None,
        quality_report_json: str | None = None,
        quality_gate_json: str | None = None,
        held: bool = False,
    ) -> None:
        job = self.get_job(job_id)
        if not job:
            return
        job.status = "held" if held else "success"
        job.stage = "quality_hold" if held else "done"
        job.message = "품질 게이트에서 DB 적재를 보류했습니다." if held else f"{inserted}개 문항을 적재했습니다."
        job.current = 1
        job.total = 1
        job.inserted = inserted
        job.output_json = output_json
        job.quality_score = quality_score
        job.quality_status = quality_status
        job.quality_report_json = quality_report_json
        job.quality_gate_json = quality_gate_json
        job.completed_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        self.db.commit()

    def fail_job(self, job_id: int, error: str) -> None:
        job = self.get_job(job_id)
        if not job:
            return
        job.status = "failed"
        job.stage = "failed"
        job.message = "작업 실패"
        job.error_message = error
        job.completed_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        self.db.commit()
