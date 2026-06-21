# Cert Study Lab Architecture

이 파일은 개발 중 빠르게 보는 요약입니다. 자세한 설명은 `docs/02_architecture.md`를 기준 문서로 봅니다.

## Current Shape

```text
Streamlit UI
  -> QuizService / LearningLabService / LearningProgressService
  -> ConceptNoteService / IngestionJobService / QuestionVectorStore
  -> PostgreSQL app DB
  -> Chroma vector index
  -> data/learning_progress.json

Airflow DAGs
  -> PDF ingestion DAG
  -> visual analysis DAG
  -> PostgreSQL app DB

Ollama
  -> text/study assistant
  -> visual question parsing
```

## User-Facing Pages

Keep the first screen light. The home page is a launcher, not a dashboard.

```text
Home
Continue Study
Focus Study
Exam Study
Dashboard
Roadmap
Theory Learning
Learning Quiz
Certification Questions
Wrong/Review
Concept Notes
Processing Status
Content Management
PDF Upload
Exam Overview
AI Index
```

## Study Flow

`Continue Study` remembers the selected Track and lets the learner keep going instead of stopping at a fixed daily quota.

```text
Track
  -> Certification
  -> Roadmap / Lesson / Quiz / Practice
  -> Certification Questions
  -> Wrong Review
  -> Dashboard
```

The current active Tracks are:

- `Linux -> LFCS`
- `Azure -> AZ-104`
- `Tool Docs -> Docs Study`

Future Tracks such as Git, Python, SQL, Docker, and Kubernetes are represented in the service data but hidden until ready.

## Data Ownership

```text
PostgreSQL
  Canonical app data: questions, answers, attempts, concept notes, ingestion jobs.

Chroma
  Search index: embeddings for similar question and document retrieval.

data/learning_progress.json
  Local learner state: preferred Track, study steps, activity counts.

cert_study_app/demo_data/questions_seed.json
  Deployable seed for Hugging Face Space.
```

Do not commit runtime data such as local DB files, Chroma indexes, Airflow logs, uploaded PDFs, or private `.env` files.

## Question Statuses

```text
approved
  Stable enough for normal quiz use.

needs_visual
  Requires visual analysis or has a failed visual-analysis result.

needs_review
  Needs human definition or correction.

draft
  Waiting for processing.

rejected
  Excluded from quiz flow.
```

The quiz repository treats only `approved` as playable.

## Metadata Split

```text
question_type
  How the UI should render the answer interaction.
  Examples: mcq, multi_select, yes_no, hotspot, table_choice, ordering.

category / subcategory / concept_tags
  What the learner is studying.
  Examples: az104_networking / vnet_subnet, az104_compute / vm.
```

Weak study should prefer `subcategory` because it is more precise than broad `category`.

## Cleanup Priorities

- Move learning progress from JSON to PostgreSQL when multi-user support starts.
- Keep Streamlit page routing names aligned with user-facing labels.
- Keep long PDF/image processing in Airflow, not inside direct Streamlit requests.
- Add more tests around Track progress, question category filters, and PWA/static file behavior.
