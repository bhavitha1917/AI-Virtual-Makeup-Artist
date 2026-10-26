# Project Specification — The Beauty Studio (Release 1.0)

This document defines the exact scope, contracts and acceptance criteria of the first release. Requirement IDs (FR-xxx, NFR-xxx) are defined in `README.md §6–7`.

## 1. Scope of release 1.0

**In scope**
- Single-photo face analysis (upload or camera) producing status-tagged estimates of skin depth, undertone, eye shape, eye tilt and face shape (FR-001…FR-013).
- Validated JSON knowledge base: products, shades, tutorial rules (FR-014, FR-032).
- Ranked, explained recommendations for six categories: foundation, concealer, color corrector, lipstick, blush, eyeliner (FR-015…FR-023).
- Inventory management and deterministic routine generation for four looks (FR-024…FR-031).
- Five-page Streamlit website with the Beauty Studio design system (FR-033…FR-035).

**Explicitly excluded** (see §10): model training, virtual try-on/rendering, generative editing, identity recognition or storage, medical/dermatological claims, guaranteed shade matching, purchasing, accounts, database servers, LLM/paid APIs.

## 2. User stories and acceptance criteria

| ID | Story | Acceptance criteria |
|---|---|---|
| US-01 | As a user I can upload a selfie and get estimates of my features. | Valid single-face JPEG/PNG/WebP ≤ 10 MB yields an `AnalysisResult` with five features, each with a status; quality checks are listed. |
| US-02 | As a user without a working camera I can still analyze a photo. | Upload is always visible; camera failure does not block upload. |
| US-03 | As a user with an unsuitable photo I am told why and what to change. | Corrupt/unsupported/oversized/tiny images, no-face, multi-face, blurry, too-dark/bright and turned-head photos produce specific messages; no fabricated estimates are shown. |
| US-04 | As a user I can correct estimates I disagree with. | Every feature has a correction control; confirmed values show status `user_confirmed` and are used downstream. |
| US-05 | As a user without a photo I can enter my profile manually. | Shade Finder and Routine pages accept manual values; recommendations work without analysis. |
| US-06 | As a user I see ranked shades with reasons. | Each card shows brand, product, shade, finish, coverage (when known), provenance badge, fit label, explanation bullets that reference only evaluated criteria, and an expandable score breakdown. |
| US-07 | As a user I am told when nothing suitable exists. | Empty state explains the failing filter(s) and suggests adjustments; no product is invented; essential filters are not relaxed. |
| US-08 | As a user I can record products I own, including ones not in the catalog. | Add from catalog (with shade), add custom, edit, remove; validation errors are shown inline. |
| US-09 | As a user I get a numbered routine for a chosen look using only my products. | Every numbered step references an inventory item; order respects constraints; optional steps are labelled; unowned-product suggestions are separate and labelled optional. |
| US-10 | As a user, changing my photo never shows me old results as current. | New/cleared image clears analysis-derived profile and invalidates analysis results; routine regenerates when inventory/look/preferences change. |
| US-11 | As an evaluator I can understand the method and its limits. | About page summarises architecture, pipeline, ranking, rules, tests, limitations, privacy and version. |

## 3. Inputs and outputs per feature

| Feature | Input | Output |
|---|---|---|
| Image ingestion (`vision.image_io.load_image`) | `bytes` (untrusted) | `DecodedImage(rgb: uint8[H,W,3], fingerprint: str, original_size: (w,h), format: str)` or `ImageValidationError` |
| Landmark detection (`vision.face_landmarks`) | RGB array | `list[FaceLandmarks]` (pixel points `float[478,2]`, `z`, blendshapes `dict[str,float]`) |
| Quality (`vision.image_quality.assess_quality`) | RGB, `FaceLandmarks` | `QualityReport(checks, skin_reliable, geometry_reliable)` |
| Skin (`vision.skin_analysis.analyze_skin`) | RGB, landmarks, `QualityReport` | `SkinAnalysis(depth, undertone: FeatureEstimate, measurements, warnings)` |
| Face geometry (`vision.face_geometry.estimate_face_shape`) | landmarks, reliability flag | `FeatureEstimate(face_shape)` |
| Eye geometry (`vision.eye_geometry.estimate_eyes`) | landmarks, reliability flag | `(FeatureEstimate(eye_shape), FeatureEstimate(eye_tilt))` |
| Pipeline (`vision.pipeline.analyze_image`) | `bytes`, `LandmarkDetector` | `AnalysisResult` or typed error |
| Recommendation (`recommendation.service.recommend`) | `Category`, `UserProfile`, `RecommendationPreferences`, `Catalog`, `limit` | `RecommendationResult(status ∈ {ok, empty, needs_input}, items, message, notes)` |
| Routine (`routine.routine_generator.generate_routine`) | `RoutineRequest(inventory, look, preferences, features)`, `TutorialRules` | `Routine(steps, skipped, suggestions, notes, signature)` or `RoutineError` |

## 4. Data schemas

### 4.1 Feature estimate (`src/core/features.py`)
```
FeatureEstimate:
  name: one of skin_depth | undertone | eye_shape | eye_tilt | face_shape
  status: unknown | uncertain | estimated | user_confirmed
  value: str | None        # required iff status ∈ {estimated, user_confirmed}; must be an allowed value
  candidates: tuple[str]   # only for uncertain; subset of allowed values
  reasons: tuple[str]      # human-readable notes, warnings or why unknown
  measurements: dict[str, float]
```
Allowed values: skin_depth ∈ {fair, light, medium, tan, deep, rich} (ordered); undertone ∈ {cool, neutral, warm}; eye_shape ∈ {almond, round, hooded, monolid}; eye_tilt ∈ {upturned, neutral, downturned}; face_shape ∈ {oval, round, square, heart, oblong}. *monolid* is user-selectable only.

### 4.2 Analysis result
```
QualityCheck: check_id, severity ∈ {ok, warning, fail}, message, value: float | None
AnalysisResult:
  image_fingerprint: sha256 hex of uploaded bytes
  image_size: (w, h) after normalization
  quality_checks: tuple[QualityCheck]
  features: {name: FeatureEstimate} for all five names
  warnings: tuple[str]
  overlay_jpeg: bytes | None  (≤ 480 px, sampling regions drawn; session-only)
UserProfile: features {name: FeatureEstimate}, source ∈ {analysis, manual}
```

### 4.3 Catalog (`data/products.json`, `data/shades.json`)
Top level: `{"schema_version": "1.0", "catalog_type": "demonstration" | "verified", "notice": str, "products"|"shades": [...]}`.

Product (required unless marked optional):
| Field | Type / allowed values |
|---|---|
| product_id | `^[a-z0-9][a-z0-9-]{2,63}$`, unique |
| brand, product_name | non-empty str ≤ 80 |
| category | Category enum (16 values, see §4.5) |
| finish | Finish enum or null |
| coverage | sheer \| light \| medium \| full \| null |
| formulation | liquid \| cream \| powder \| gel \| stick \| pencil \| balm \| spray \| null |
| base | water \| silicone \| oil \| null |
| intended_use | list[str] (e.g. `brightening`, `spot` for concealer) |
| price, currency, product_url | null unless `verification_status = verified` |
| source | non-empty provenance description |
| verification_status | verified \| unverified \| demo |
| shade_ids | list of shade IDs (may be empty for shadeless products) |

Shade:
| Field | Type / allowed values |
|---|---|
| shade_id | unique, same pattern; `product_id` must exist and list it |
| shade_name | non-empty str |
| depth | Depth enum or null |
| undertone | Undertone enum or null |
| color_family | ColorFamily enum or null |
| intensity | soft \| medium \| bold \| null |
| finish | Finish enum or null (overrides product finish) |
| correction_target | dark_circles \| redness \| dullness \| null (color correctors) |
| suitable_depths | list[Depth] |
| suitable_looks | list[Look] |
| illustrative_swatch_hex | `#RRGGBB` or null; **only allowed when verification_status = demo** |
| source, verification_status | as product |

Validation rules: unique IDs; known enums; bidirectional product↔shade references; complexion shades (foundation, concealer) of `verified`/`demo` status must have `depth`; color-corrector shades must have `correction_target`; price/URL forbidden unless verified; swatch forbidden unless demo.

### 4.4 Tutorial rules (`data/tutorial_rules.json`)
```
schema_version, notice: str, general_cautions: [str]
looks: {look_id: {label, description}}
steps: [{step_id, category, title, purpose, sequence:int, looks:[Look], optional_in_looks:[Look],
         techniques:{default: str, <formulation>: str}, cautions:[str]}]
rules: [{rule_id, step_id, kind ∈ {look, feature, preference}, looks:[Look]|null,
         conditions:{face_shape|eye_shape|eye_tilt|formulation|coverage|intensity|concealer_order: [values]},
         requires_steps:[step_id], instruction, priority:int, exclusive_group:str|null,
         optional:bool, cautions:[str], rationale}]
ordering: [{constraint_id, before, after, when:{look:[...]}|{formulation:{step_id:[...]}}|{concealer_order:[...]}|null, rationale}]
compatibility: [{compat_id, steps:[a,b], bases:[base_a, base_b], note}]
suggestions: [{suggestion_id, step_id, looks:[Look], text}]
```
Validation: unique step/rule/constraint IDs; every referenced step exists; enums valid; techniques include `default`; no cycle among unconditional constraints; no two rules in the same `exclusive_group` with equal priority whose looks and conditions can co-apply (contradiction).

### 4.5 Enumerations
Category: skin_prep, primer, color_corrector, foundation, concealer, powder, bronzer, blush, highlighter, eyebrow, eyeshadow, eyeliner, mascara, lip_liner, lipstick, setting_spray.
Finish: matte, natural, satin, dewy, radiant, gloss, shimmer, metallic. Look: everyday, office, festive, glam. Intensity: soft, medium, bold. ColorFamily: nude, pink, rose, coral, red, berry, plum, brown, peach, terracotta, black, navy, green, bronze, lavender, orange.

### 4.6 Inventory item
```
InventoryItem: item_id (uuid4 hex), category, product_name (1–80 chars), brand (0–60), shade_name (0–60 | None),
               finish | None, formulation | None, base | None, source ∈ {catalog, custom},
               catalog_product_id | None, catalog_shade_id | None
```

## 5. Component responsibilities and contracts

| Module | Responsibility | Key contract |
|---|---|---|
| `src/config.py` | All limits, thresholds, paths, env settings | Immutable dataclasses; no business logic |
| `src/core/enums.py` | Enumerations | `str` Enums; ordered Depth/Coverage/Intensity helpers |
| `src/core/features.py` | Feature/analysis/profile schema | Validates invariants in `__post_init__` |
| `src/core/errors.py` | Typed errors with `code` and `user_message` | All expected failures raise subclasses of `BeautyStudioError` |
| `src/data/schema.py` | Parse + validate raw JSON | Collect *all* issues, raise one `CatalogError` |
| `src/data/loader.py` | Read files, build `Catalog`, `TutorialRules` | Relative paths from `config.DATA_DIR` |
| `src/vision/image_io.py` | Byte → validated RGB | Never writes to disk |
| `src/vision/model_asset.py` | Locate/download/verify model | SHA-256 pinned; atomic write; `ModelUnavailableError` |
| `src/vision/face_landmarks.py` | MediaPipe wrapper + landmark validation | `LandmarkDetector` protocol for mocking; lock for thread-safety |
| `src/vision/image_quality.py` | Quality checks | Pure function of image + landmarks |
| `src/vision/skin_analysis.py` | Skin sampling and color heuristics | Returns `unknown` rather than guessing |
| `src/vision/face_geometry.py` / `eye_geometry.py` | Geometry + classification | Guards division by zero; uncertain on low margin |
| `src/vision/regions.py` | Face mask, sampling discs, exclusion masks, Lab conversion | Shared by quality and skin modules |
| `src/vision/pipeline.py` | Orchestration, overlay | Single entry point `analyze_image` |
| `src/recommendation/*` | Filters, scores, explanations, service | Deterministic; hard filters separate from scores |
| `src/routine/*` | Inventory ops, rule selection, ordering, generation | Deterministic; never references unowned items |
| `src/ui/state.py` | Session-state transitions | Operates on any `MutableMapping` (testable) |
| `src/ui/components.py`, `theme.py` | Shared presentation, page error boundary | Escapes all user/catalog text |
| `src/ui/resources.py`, `navigation.py` | Cached immutable resources; page registry | No per-user data in process-wide caches |
| `src/ui/pages/*` | Page layout + widget wiring | Call services only |

## 6. Failure cases and expected behavior

| Case | Detection | Behavior |
|---|---|---|
| Empty / > 10 MB file | byte length | `ImageValidationError(file_empty / file_too_large)` |
| Unsupported/corrupt | Pillow identify/verify | `unsupported_format` / `decode_failed` |
| > 40 MP or decompression bomb | size header / Pillow guard | `too_many_pixels` |
| Shorter side < 256 px | dimensions | `too_small` |
| No face / multiple faces | detector count | `FaceDetectionError(no_face / multiple_faces)` |
| Invalid landmarks | validation | `LandmarkValidationError` → shown as analysis failure |
| Model missing, download disabled/failed | `model_asset` | `ModelUnavailableError`, page shows setup instructions; Shade Finder/Routine still usable |
| Blurry / dark / bright / clipped / uneven light | quality checks | skin features `unknown` (fail) or undertone `uncertain` (warning) with reasons |
| Face too small / turned | quality checks | all features `unknown` (fail) |
| Eyes closed | blendshape / opening | eye features `unknown` |
| Obstructed region | ΔE outlier | region excluded; < 2 regions → skin `unknown` |
| Near category boundary | margin | `uncertain` + candidates |
| Catalog invalid | startup validation | App shows a catalog error panel; Face Analysis still works |
| Foundation with unknown depth | service | `needs_input` asking the user to set depth |
| No candidate passes filters | service | `empty` with reasons and suggestions |
| Empty inventory / invalid look / no applicable steps | generator | `RoutineError` with actionable message |
| Ordering cycle | generator | `RoutineError(ordering_cycle)` |
| Unexpected exception | page boundary | Logged (no image data); generic message |

## 7. UI states

| Page | Empty | Loading | Success | Error |
|---|---|---|---|---|
| Face Analysis | Instructions + upload/camera, no results | `st.status` "Analyzing…" | Quality checks, feature cards, overlay, correction form | Specific error card + "Try another photo" |
| Shade Finder | Profile prompt when no profile; category empty state | — (instant) | Product card grid | Catalog error panel; `needs_input` / `empty` cards |
| My Routine | Inventory empty state with guidance | spinner on generate | Numbered steps, skipped, suggestions | Inline validation errors; routine error card; stale notice |
| Home / About | — | — | Static content | — |

## 8. Testing requirements

All categories of `TEST_PLAN.md` must exist and pass: image handling, vision engine, catalog, recommendation, routine, application (imports, state, AppTest smoke). Tests must not need a webcam; model-dependent tests skip with an explicit reason if the model is absent.

## 9. Acceptance criteria for release 1.0

1. README, specification, architecture and code agree (manual review).
2. `python -m pytest -q` passes; `ruff check .` clean; `compileall` OK; `scripts/validate_data.py` OK.
3. `streamlit run app.py` starts and all five pages render without exceptions (AppTest + browser).
4. Face analysis handles a real face photo and every invalid-input class in §6.
5. Recommendations use only validated catalog data, show explanations, and handle empty/needs-input.
6. Users can add catalog and custom products, edit and remove them.
7. Routines contain only owned products and satisfy every active ordering constraint.
8. Design system applied consistently; checked at ≈1366, ≈768 and ≈390 px.
9. No secrets in repository; model and venv git-ignored.
10. Limitations and unverified items listed.

## 10. Explicitly excluded functionality

Training models; photorealistic or AR try-on; generative face editing; facial identity recognition or storage; medical/dermatological diagnosis; guaranteed foundation matching; checkout/purchasing; mandatory accounts; database servers; LLM or paid API dependencies; automatic olive-undertone or monolid detection; multi-face analysis; video analysis.
