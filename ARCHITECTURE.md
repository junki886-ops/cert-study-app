# Cert Study App Architecture

## Current Shape

The app is organized around one user-facing Streamlit app and two background-processing paths.

```text
Streamlit UI
  -> QuizService / ConceptNoteService / IngestionJobService
  -> PostgreSQL app DB

Airflow DAGs
  -> PDF ingestion DAG
  -> visual analysis DAG
  -> PostgreSQL app DB

Ollama
  -> qwen2.5:14b for text/study assistant
  -> qwen3.5:9b for visual question parsing
```

## User-Facing Pages

Keep the menu small:

```text
Home
Problem solving
Weak concept study
Wrong/review
Concept notes
Processing status
PDF upload
Exam overview
AI index
```

`Processing status` is the single place for:

- Airflow parsing jobs
- question status counts
- image-analysis backlog
- concept-classification status
- manual review for unusual patterns

Avoid adding separate pages for parsing, auto-review, image analysis, or validation unless they become full workflows.

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
`needs_visual` and `needs_review` should not appear in normal quiz navigation.

## Metadata Split

Question metadata is intentionally split:

```text
question_type
  How the UI should render the answer interaction.
  Examples: mcq, multi_select, yes_no, hotspot, table_choice, ordering.

category / subcategory / concept_tags
  What the learner is studying.
  Examples: network / nsg, compute_vm / vm, identity / rbac.
```

Weak study should use `subcategory` first because it identifies the actual weak concept more precisely than broad `category`.
Fallback to `category` only when subcategory is missing.

## Background Work

PDF upload should create an `ingestion_jobs` row and trigger Airflow:

```text
cert_study_pdf_ingestion
```

Remaining image work should use:

```text
cert_study_visual_analysis
```

Streamlit should not run long image-analysis jobs directly. It should trigger Airflow and show status.

## Database

PostgreSQL is now the app DB in Docker and local `.env`:

```text
postgresql+pg8000://cert_study:cert_study@localhost:5432/cert_study
```

SQLite remains only as a fallback/default when `DATABASE_URL` is not set.

Migration helper:

```bash
.venv/bin/python scripts/migrate_sqlite_to_postgres.py --replace
```

Use this after old SQLite-based background work finishes, or when importing legacy data.

## Known Cleanup Priorities

- Move PDF ingestion and visual analysis fully to PostgreSQL-backed Airflow after rebuilding containers.
- Add explicit Airflow DAG run status display through the API instead of relying only on local job rows.
- Replace ad-hoc manual fixes with a repeatable visual validation rule set.
- Keep generated artifacts such as parsed JSON, question images, Chroma files, and DB files out of source commits unless intentionally versioned.
