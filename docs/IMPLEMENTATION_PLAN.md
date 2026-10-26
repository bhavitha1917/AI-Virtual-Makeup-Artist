# Implementation Plan

Order follows the dependency structure in `architecture.md §2`: lower layers first, each validated by focused tests before the next layer builds on it.

| # | Task | Depends on | Requirements | Acceptance criteria | Status |
|---|---|---|---|---|---|
| T1 | Scaffold: folders, `requirements*.txt`, `pyproject.toml`, `.gitignore`, `.streamlit/config.toml`, `packages.txt` | — | NFR-007, NFR-008 | `pip install -r requirements.txt` succeeds; `pip check` clean | Done |
| T2 | `config.py`, `core/enums.py`, `core/errors.py`, `core/features.py` | T1 | FR-011, NFR-011 | Feature invariants tested | Done |
| T3 | Catalog + rules JSON, `data/schema.py`, `data/loader.py`, `scripts/validate_data.py` | T2 | FR-014, FR-032 | Production data validates; invalid fixtures rejected with specific issues | Done |
| T4 | `vision/image_io.py` | T2 | FR-001, FR-003, NFR-003 | All image-handling tests pass | Done |
| T5 | `vision/model_asset.py`, `vision/face_landmarks.py`, `landmark_indices.py` | T2 | FR-004, FR-006, NFR-010 | Landmark validation tests; real model loads; no-face integration test | Done |
| T6 | `vision/image_quality.py` | T5 | FR-005 | Quality tests on synthetic images | Done |
| T7 | `vision/skin_analysis.py` | T6 | FR-007, FR-008 | Skin tests | Done |
| T8 | `vision/face_geometry.py`, `vision/eye_geometry.py` | T5 | FR-009, FR-010 | Geometry tests | Done |
| T9 | `vision/pipeline.py` (+ overlay) | T4–T8 | FR-004, FR-011 | Pipeline tests with fake detector; manual run on a real photo | Done |
| T10 | `recommendation/*` | T3 | FR-015…FR-023 | Recommendation tests | Done |
| T11 | `routine/*` | T3 | FR-024…FR-032 | Routine + rule tests | Done |
| T12 | `ui/theme.py`, `assets/styles.css`, `ui/components.py`, `ui/state.py`, `ui/navigation.py` | T2 | FR-033, FR-034, FR-035, NFR-005 | State tests | Done |
| T13 | Pages + `app.py` | T9–T12 | FR-002, FR-012, FR-013, FR-033 | AppTest smoke tests; app starts | Done |
| T14 | Review pass (dead code, duplication, claims, security) | T13 | all | Review notes resolved | Done |
| T15 | Full verification: pytest, ruff, compileall, data validation, clean-env install, browser checks at 3 widths | T14 | all | Results logged in `TEST_PLAN.md §5` | Done, except the separate clean-venv run (stopped by low memory; see TEST_PLAN) |
| T16 | Documentation status update | T15 | all | README/traceability reflect verified results only | Done |

**Order adjustment:** data schemas (T3) precede the vision engine because both the recommendation and routine engines and the UI depend on validated data, and the data layer has no dependency on vision. Vision geometry (T8) depends only on landmarks, so it can proceed in parallel with quality/skin work.
