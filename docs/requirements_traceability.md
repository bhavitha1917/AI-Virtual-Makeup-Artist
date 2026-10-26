# Requirements Traceability Matrix

Status values: **Planned** → **Implemented** (code exists) → **Verified** (automated test passes and/or manual check performed, as noted). Last updated 2026-10-26 after a full run (251 tests passed). "Verified" means the implementation meets its specification; it does not imply the heuristics are accurate for real users (no labelled evaluation was performed).

| ID | Summary | Implementation | Test(s) | Status |
|---|---|---|---|---|
| FR-001 | Upload JPEG/PNG/WebP ≤ 10 MB | `src/vision/image_io.py`, `src/ui/pages/face_analysis.py` | `tests/test_image_io.py` | Verified |
| FR-002 | Camera capture + upload fallback | `src/ui/pages/face_analysis.py` | `tests/test_app.py`; manual | Implemented — upload fallback verified; physical camera not exercised |
| FR-003 | Decode/pixel/dimension validation | `src/vision/image_io.py` | `tests/test_image_io.py` | Verified |
| FR-004 | Exactly one face | `src/vision/pipeline.py` | `tests/test_pipeline.py`, `tests/test_face_landmarks.py` | Verified |
| FR-005 | Quality checks | `src/vision/image_quality.py` | `tests/test_image_quality.py` | Verified |
| FR-006 | Landmark extraction + validation | `src/vision/face_landmarks.py` | `tests/test_face_landmarks.py` | Verified |
| FR-007 | Skin depth estimate | `src/vision/skin_analysis.py` | `tests/test_skin_analysis.py` | Verified |
| FR-008 | Undertone estimate | `src/vision/skin_analysis.py` | `tests/test_skin_analysis.py` | Verified |
| FR-009 | Eye shape + tilt | `src/vision/eye_geometry.py` | `tests/test_eye_geometry.py` | Verified |
| FR-010 | Face shape | `src/vision/face_geometry.py` | `tests/test_face_geometry.py` | Verified |
| FR-011 | Analysis schema with statuses | `src/core/features.py` | `tests/test_features.py`, `tests/test_pipeline.py` | Verified |
| FR-012 | User corrections | `src/ui/state.py`, `src/ui/pages/face_analysis.py` | `tests/test_state.py` | Verified |
| FR-013 | Manual profile | `src/ui/state.py`, `src/ui/components.py` | `tests/test_state.py`, `tests/test_app.py` | Verified |
| FR-014 | Catalog validation | `src/data/schema.py`, `src/data/loader.py` | `tests/test_catalog.py` | Verified |
| FR-015 | Foundation ranking | `src/recommendation/*` | `tests/test_recommendation.py` | Verified |
| FR-016 | Concealer ranking | `src/recommendation/*` | `tests/test_recommendation.py` | Verified |
| FR-017 | Color corrector ranking | `src/recommendation/*` | `tests/test_recommendation.py` | Verified |
| FR-018 | Lipstick ranking | `src/recommendation/*` | `tests/test_recommendation.py` | Verified |
| FR-019 | Blush ranking | `src/recommendation/*` | `tests/test_recommendation.py` | Verified |
| FR-020 | Eyeliner ranking + technique | `src/recommendation/*`, `data/tutorial_rules.json` | `tests/test_recommendation.py` | Verified |
| FR-021 | Explicit weighted score | `src/recommendation/ranking.py` | `tests/test_recommendation.py` | Verified |
| FR-022 | Criteria-based explanations | `src/recommendation/explanations.py` | `tests/test_recommendation.py` | Verified |
| FR-023 | Empty / uncertain handling | `src/recommendation/service.py` | `tests/test_recommendation.py` | Verified |
| FR-024 | Add catalog product | `src/routine/inventory.py`, `src/ui/pages/routine.py` | `tests/test_routine.py`, `tests/test_app.py` | Verified |
| FR-025 | Add custom product | `src/routine/inventory.py` | `tests/test_routine.py`, `tests/test_app.py` | Verified |
| FR-026 | Edit / remove items | `src/routine/inventory.py` | `tests/test_routine.py` | Verified |
| FR-027 | Look + preferences | `src/routine/routine_generator.py` | `tests/test_routine.py` | Verified |
| FR-028 | Numbered routine | `src/routine/routine_generator.py` | `tests/test_routine.py` | Verified |
| FR-029 | Dependency-aware ordering | `src/routine/application_order.py` | `tests/test_routine.py` | Verified |
| FR-030 | Missing-product handling | `src/routine/routine_generator.py` | `tests/test_routine.py` | Verified |
| FR-031 | Feature tips (usable only) | `src/routine/rule_engine.py` | `tests/test_routine.py` | Verified |
| FR-032 | Rule validation | `src/routine/rule_engine.py`, `src/data/schema.py` | `tests/test_tutorial_rules.py` | Verified |
| FR-033 | Five pages + navigation | `app.py`, `src/ui/navigation.py`, `src/ui/pages/*` | `tests/test_app.py`; manual | Verified |
| FR-034 | Session isolation, no stale results | `src/ui/state.py` | `tests/test_state.py` | Verified |
| FR-035 | Disclaimers | `src/ui/components.py`, pages | `tests/test_app.py` | Verified |
| NFR-001 | No paid API, deterministic | whole codebase | `tests/test_architecture.py`, determinism tests | Verified |
| NFR-002 | No image persistence/logging | `src/vision/*`, `src/ui/state.py` | `tests/test_architecture.py`; review | Verified |
| NFR-003 | Untrusted input safety | `src/vision/image_io.py` | `tests/test_image_io.py` | Verified |
| NFR-004 | Analysis < 5 s | `src/vision/pipeline.py` | manual timing | Verified on one sample image (758 ms) |
| NFR-005 | Accessibility (contrast, labels) | `assets/styles.css`, `.streamlit/config.toml` | contrast computed; manual | Verified |
| NFR-006 | Responsive | `assets/styles.css` | manual at 3 widths | Verified via 390/768/1366 px iframes |
| NFR-007 | Maintainability, lint | all | `ruff check .`, `tests/test_architecture.py` | Verified |
| NFR-008 | Pinned deps, Python 3.11 | `requirements.txt` | clean install + `pip check` | Verified |
| NFR-009 | Tests w/o webcam | `tests/` | `pytest` | Verified |
| NFR-010 | Graceful degradation | `src/vision/model_asset.py`, pages | `tests/test_model_asset.py`, `tests/test_app.py` | Verified |
| NFR-011 | No fabricated confidence | `src/core/features.py`, UI | review, `tests/test_recommendation.py` | Verified |
| NFR-012 | Relative paths | `src/config.py` | `tests/test_architecture.py` | Verified |
