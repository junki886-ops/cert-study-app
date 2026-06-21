# Changelog

## 2026-06-21

- Expanded the app from quiz-only flow into Cert Study Lab study flows.
- Added Track-based study structure for Linux/LFCS, Azure/AZ-104, and Tool Docs.
- Separated the home launcher from the dashboard so the first screen stays lighter.
- Replaced the fixed daily-study framing with a continue-study flow that supports longer study sessions.
- Added local learning progress tracking for preferred Track, study steps, activity counts, streaks, and study units.
- Added theory cards, learning quizzes, roadmap, focus study, exam study, and dashboard screens.
- Added AZ-104 skill area and subcategory filters for repeated weak-concept practice.
- Moved AZ-104 classification review under content management.
- Improved theory card explanations with more context, exam points, and common mistakes.
- Updated architecture and publishing docs to explain current data ownership and version management.

## 2026-06-07

- Added deployable Hugging Face seed data and static question assets.
- Restored common passages and parent images for case-study questions.
- Improved seed refresh so deployed databases can receive updated questions.
- Added Yes/No matrix handling for true/false hotspot questions.
- Added grouped row selection for `1-A / 1-B / 2-A / 2-B` style questions.
- Added centralized answer normalization for single choice, multi-select, ordered answers, and Yes/No matrices.
- Added centralized question type normalization for aliases such as `Hotspot (True/False)` and `Hotspot (Drag and Drop)`.
- Reduced mobile home screen noise by prioritizing study actions and grouping upload/admin actions.
- Added lightweight tests for answer normalization, question type aliases, and seed export reports.
- Added GitHub Actions quality check workflow.
- Added `.env.example` and Docker Compose environment variable defaults.
- Updated README and docs for the current deployment and troubleshooting flow.
