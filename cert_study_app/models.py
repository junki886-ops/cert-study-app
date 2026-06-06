import json
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from cert_study_app.db import Base


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stem = Column(Text, nullable=False)
    answer = Column(Text)
    explanation = Column(Text)
    question_type = Column(String(50), default="MCQ")
    question_number = Column(Integer)
    group_id = Column(String(100))
    parent_stem = Column(Text)
    parent_image_paths = Column(Text)
    page = Column(Integer)
    category = Column(String(100))
    subcategory = Column(String(100))
    concept_tags = Column(Text)
    code = Column(Text)
    source = Column(String(255))
    image_path = Column(String(500))
    raw_text = Column(Text)
    structured_data_json = Column(Text)
    parse_status = Column(String(30), default="draft")
    quality_score = Column(Integer)
    quality_status = Column(String(50))
    quality_issues = Column(Text)
    chunk_key = Column(String(80))
    chunk_index = Column(Integer)
    parser_version = Column(String(50))
    review_note = Column(Text)
    review_score = Column(Integer)
    review_issues = Column(Text)
    visual_analysis_json = Column(Text)
    visual_reviewed_at = Column(DateTime)
    reviewed_at = Column(DateTime)
    auto_reviewed_at = Column(DateTime)
    options_json = Column(Text)
    pairs = Column(Text)
    sequence = Column(Text)

    def set_options(self, options):
        try:
            self.options_json = (
                json.dumps(options, ensure_ascii=False)
                if isinstance(options, (list, dict))
                else options
            )
        except Exception:
            self.options_json = "[]"

    def get_options(self):
        try:
            return json.loads(self.options_json) if self.options_json else []
        except Exception:
            return []

    def get_pairs(self):
        try:
            return json.loads(self.pairs) if self.pairs else {}
        except Exception:
            return {}

    def get_sequence(self):
        try:
            return json.loads(self.sequence) if self.sequence else []
        except Exception:
            return []

    def set_concept_tags(self, tags):
        try:
            self.concept_tags = json.dumps(tags or [], ensure_ascii=False)
        except Exception:
            self.concept_tags = "[]"

    def get_concept_tags(self):
        try:
            parsed = json.loads(self.concept_tags) if self.concept_tags else []
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []

    def __repr__(self):
        return f"<Question id={self.id} type={self.question_type}>"


class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, default="guest")
    question_id = Column(Integer, ForeignKey("questions.id"))
    chosen = Column(String(10))
    correct = Column(Boolean, default=False)
    note_type = Column(String(20), default="wrong")

    question = relationship("Question", backref="attempts")

    def __repr__(self):
        return f"<Attempt q={self.question_id}, user={self.user_id}, correct={self.correct}>"


class ConceptNote(Base):
    __tablename__ = "concept_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    concept_name = Column(String(255), nullable=False)
    summary = Column(Text)
    exam_point = Column(Text)
    trap_point = Column(Text)
    keywords = Column(Text)
    source = Column(String(255))
    source_question_id = Column(Integer, ForeignKey("questions.id"))
    user_id = Column(String(100), nullable=False, default="guest")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    question = relationship("Question", backref="concept_notes")

    def keyword_list(self) -> list[str]:
        try:
            parsed = json.loads(self.keywords) if self.keywords else []
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []

    def set_keywords(self, keywords):
        try:
            self.keywords = json.dumps(keywords or [], ensure_ascii=False)
        except Exception:
            self.keywords = "[]"

    def __repr__(self):
        return f"<ConceptNote id={self.id} name={self.concept_name}>"


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    exam_name = Column(String(255), nullable=False)
    pdf_path = Column(String(500), nullable=False)
    output_json = Column(String(500))
    status = Column(String(30), default="queued")
    stage = Column(String(50), default="queued")
    message = Column(Text)
    current = Column(Integer, default=0)
    total = Column(Integer, default=1)
    inserted = Column(Integer, default=0)
    quality_score = Column(Integer)
    quality_status = Column(String(50))
    quality_report_json = Column(String(500))
    quality_gate_json = Column(String(500))
    use_llm = Column(Boolean, default=True)
    llm_model = Column(String(100), default="qwen2.5:14b")
    ollama_base_url = Column(String(255), default="http://localhost:11434")
    auto_visual_analysis = Column(Boolean, default=True)
    visual_batch_size = Column(Integer, default=5)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    def __repr__(self):
        return f"<IngestionJob id={self.id} status={self.status}>"


class AzureDocsSync(Base):
    __tablename__ = "azure_docs_syncs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    embedding_model = Column(String(255), nullable=False)
    status = Column(String(30), default="queued")
    message = Column(Text)
    urls_checked = Column(Integer, default=0)
    documents_indexed = Column(Integer, default=0)
    chunks_indexed = Column(Integer, default=0)
    error_message = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AzureDocsSync id={self.id} status={self.status}>"
