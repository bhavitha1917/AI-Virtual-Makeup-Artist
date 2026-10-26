# Test Plan — The Beauty Studio

## 1. Strategy
- **Unit tests** (pytest) for every service module using synthetic images, synthetic landmark arrays with known geometry, a fake `LandmarkDetector`, and fictional fixture catalogs in `tests/fixtures/` (never the production catalog for logic tests).
- **Data tests** validate the production JSON files with the same validator the app uses.
- **Integration tests** run the real MediaPipe model on synthetic no-face images (skipped with an explicit reason if the model asset is absent).
- **UI smoke tests** use `streamlit.testing.v1.AppTest` to render every page and exercise key interactions.
- **Static checks**: `ruff check .`, `python -m compileall`, import check, `pip check`.
- **Manual checks**: start the app, exercise both workflows in a browser on a real face photo, inspect at ≈1366, ≈768 and ≈390 px widths.

## 2. Commands
```bash
python -m pytest -q
python -m ruff check .
python -m compileall -q app.py src scripts tests
python scripts/validate_data.py
python -m pip check
streamlit run app.py   # then manual browser checks
```

## 3. Test scenarios

| Area | Scenario | Test file |
|---|---|---|
| Image handling | valid JPEG/PNG/WebP; corrupt bytes; unsupported format (GIF/BMP); empty; oversized bytes; too many pixels; too small; EXIF rotation; alpha flattening; downscale; filename sanitization | `test_image_io.py` |
| Detection | no face, multiple faces (fake detector), no face with real model (integration) | `test_pipeline.py`, `test_face_landmarks.py` |
| Landmarks | wrong count, NaN, out of bounds, degenerate IOD | `test_face_landmarks.py` |
| Quality | blurry vs sharp synthetic, dark, bright, clipped, uneven lighting, small face, yaw | `test_image_quality.py` |
| Skin | Lab conversion against known values; ITA/hue math; depth bands and boundary uncertainty; undertone bands; region outlier exclusion; empty regions → unknown; cast → uncertain; deterministic K-Means | `test_skin_analysis.py` |
| Face geometry | synthetic prototypes per shape; division-by-zero; boundary → uncertain; unreliable → unknown | `test_face_geometry.py` |
| Eye geometry | almond/round/hooded synthetic eyes; closed eyes; left/right disagreement; tilt with roll | `test_eye_geometry.py` |
| Feature schema | invariants of `FeatureEstimate` statuses | `test_features.py` |
| Catalog | production files valid; missing field; duplicate ID; invalid category; broken shade refs; unverified price; swatch on non-demo; missing optional metadata | `test_catalog.py` |
| Recommendation | compatible vs incompatible; unknown undertone; unknown depth → needs_input; missing metadata scores 0; category-specific weights; empty candidates; explanation claims match components; no claims for unevaluated criteria; determinism | `test_recommendation.py` |
| Routine | empty inventory; custom products; optional steps; valid ordering; conditional ordering (cream vs powder blush, concealer order, glam eyes-first); transitive order with absent steps; invalid dependency; cycle; duplicate rule; contradictory rules; look filtering; no unowned references; signature changes | `test_routine.py`, `test_tutorial_rules.py` |
| Application | imports; streamlit only imported by UI; state transitions (new image clears analysis/profile; stale routine hidden); AppTest renders all pages; inventory add/remove via UI | `test_state.py`, `test_app.py`, `test_architecture.py` |

## 4. Manual verification checklist
1. A new session opens on the welcome screen (background photo, title, tagline, one button, no menu); the button opens Home.
1. Home renders hero, two feature cards, CTAs navigate correctly.
2. Face Analysis: upload a real face photo → analysis completes; overlay shown; corrections persist; clear photo clears results.
3. Face Analysis: upload a non-face image → "no face" message, no estimates.
4. Shade Finder: each category shows cards or a meaningful empty / needs-input state.
5. Routine: add catalog + custom items, edit, remove, generate for each look; changing inventory hides the old routine.
6. About renders.
7. Viewports ≈1366, ≈768, ≈390 px: no horizontal scroll, readable text.

## 5. Results log
Results are recorded here only after they have been run.

Environment: Windows 11, Python 3.11.9, dependencies from `requirements-dev.txt`.

| Date | Check | Result |
|---|---|---|
| 2026-10-26 | `python -m pytest -q` (project venv, model present) | **251 passed**, 0 failed, 0 skipped |
| 2026-10-26 | `python -m ruff check .` | All checks passed |
| 2026-10-26 | `python -m compileall -q app.py src scripts tests` | OK |
| 2026-10-26 | `python scripts/validate_data.py` | Catalog OK (31 products, 158 shades, demonstration); rules OK (16 steps, 42 rules, 31 constraints; no contradictions or cycles in any context) |
| 2026-10-26 | `python -m pip check` | No broken requirements |
| 2026-10-26 | Mutation check (3 deliberate defects: no transitive ordering, rewarding missing undertone, no boundary uncertainty) | All 3 detected by the suite (the first only after adding a dedicated test) |
| 2026-10-26 | Real image, direct pipeline call (MediaPipe sample `portrait.jpg`, not committed) | All 9 quality checks passed; depth *light* (estimated), undertone *uncertain* cool/neutral (cast suspected), eyes *almond*/*neutral*, face *oval*; 758 ms including first inference (single measurement, NFR-004 target < 5 s) |
| 2026-10-26 | `streamlit run app.py` + Chrome | App starts; Home renders with theme fonts loaded; upload → Analyze → results + overlay → Confirm → Shade Finder cards with reasons; catalog + custom item → Glam routine; custom name containing HTML rendered literally (escaped); no console errors |
| 2026-10-26 | Responsive check (same-origin iframes at 390, 768, 1366 px — window resizing was not possible in the test browser) | All five pages: no horizontal overflow, no error states |
| 2026-10-26 | Re-run of pytest, ruff, compileall, `validate_data.py`, `pip check` | 251 passed (71 s); all others clean, same output as above |
| 2026-10-26 | Headless startup (`streamlit run app.py --server.headless=true --server.port=8599`) | `/_stcore/health` returned `ok` within ~1 s; `/` returned HTTP 200; server stopped afterwards |
| 2026-10-26 | Welcome screen: `pytest -q`, `ruff`, `compileall` | **254 passed**; ruff clean; compile OK |
| 2026-10-26 | Welcome screen in Chrome (desktop 1536 px, plus same-origin iframes at 390 and 768 px) | Opens on welcome (only title, tagline, button; no nav links); centred, no horizontal or vertical scroll; Playfair title, Inter mauve button. Button → Home at `/` with menu; all five pages via menu and back to Home work; a new session opened at `/routine` also shows welcome and enters to Home; no console errors |
| 2026-10-26 | Welcome photo background: `pytest -q`, `ruff`, `compileall` | **254 passed**; ruff clean; compile OK |
| 2026-10-26 | Welcome photo in Chrome (1536×730 window; same-origin iframes at 390×844, 768×1024, 1024×768) | Photo fills the viewport without distortion; frosted panel hides the copy painted into the photo (landscape); face visible and copy on a bottom fade (portrait); no overflow or scrolling, no menu. *Get Started →* opens the unchanged Home (no photo, ivory background); all five pages reachable via the menu with no exceptions |
| — | Physical camera capture | **Not exercised** (no camera used during verification); widget renders and upload fallback is always shown |
| 2026-10-26 | Clean-environment install (fresh venv from `requirements-dev.txt`, then pytest) | **Not completed** — the run was stopped by the host because the machine ran low on memory. The project venv was itself created from scratch with the same pinned versions, and `pip check` passes there, but a separate clean-venv run is still outstanding. |
