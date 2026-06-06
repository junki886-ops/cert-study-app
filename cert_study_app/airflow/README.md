# Airflow entrypoint

Airflow should load DAGs from the repository-level `dags/` directory.

Run the PDF ingestion workflow with a DAG run config like:

```json
{
  "pdf_path": "data/uploads/sample.pdf",
  "source_name": "sample.pdf"
}
```

The DAG delegates the actual work to `cert_study_app.graphs.pdf_ingestion_graph`,
so local Flask uploads and scheduled Airflow runs share the same LangGraph workflow.
