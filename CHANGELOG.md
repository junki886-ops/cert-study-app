# Changelog

## 2026-07-04 (2)

- Set difficulty (easy/medium/hard) on 49 Linux quizzes that were previously unclassified.
- Added `level` (입문/중급/고급) to all 50 Azure lessons (was None for all).
- Linked `related_practices` on 20 Azure lessons to their corresponding practice task IDs.
- Added cumulative lesson/quiz/practice progress count (N/총개수) to home mode cards.
- Added overall quiz progress bar (퀴즈 N/총개수 완료) to the top of the `확인 퀴즈` screen.
- Added overall practice progress bar (실습 N/총개수 완료) to the top of the `실습하기` screen.
- Added "관련 이론 다시 보기" button on practice failure, routing to the linked lesson (reverse `related_practices` lookup).

## 2026-07-04

- Fixed AI quiz assistant crashing the page when ChromaDB collection is empty (added `min(k, count)` guard).
- Fixed Ollama streaming errors propagating to the page; errors now show as inline messages instead of breaking the UI.
- Added error handling to `StudyAssistantService` initialization and `ask_stream` in `render_quiz_assistant`.
- Wrapped `requests.post` in `concept_note_service` and `visual_question_service` with `RuntimeError` for clearer messages.
- Home Smart CTA now routes directly to `이론 학습` or `확인 퀴즈` without the intermediate landing page.
- Added a 3-step progress indicator (①개념 → ②실습 → ③복습) below the home Hero card.
- Replaced small `→` buttons on mode cards with full-width clickable buttons for easier mobile use.
- Theory card completion now shows a direct "확인 퀴즈 바로 풀기 →" button instead of a dead-end success message.
- Added inline "다음 퀴즈 →" button after quiz answer explanation so users don't have to scroll down.
- Added inline "다음 실습 →" button after practice grading; shows a completion message on the last task.

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
