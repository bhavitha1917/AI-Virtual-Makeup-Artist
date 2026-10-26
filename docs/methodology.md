# Methodology — The Beauty Studio

All thresholds below live in `src/config.py`. **They are provisional engineering heuristics, chosen from published category definitions where they exist (ITA) and otherwise from inspection of a small number of sample images during development. They have not been validated on a labelled dataset; no accuracy is claimed.**

## 1. Image ingestion

| Step | Rule |
|---|---|
| Size | 1 B ≤ bytes ≤ 10 MB |
| Format | Detected from content by Pillow: JPEG, PNG or WebP only (filename ignored) |
| Pixels | width × height ≤ 40 MP (checked from header before decoding; Pillow's `MAX_IMAGE_PIXELS` also set) |
| Decode | `Image.verify()` then re-open and `load()`; any exception → `decode_failed` |
| Orientation | EXIF transpose |
| Color | Alpha composited on white; converted to 8-bit RGB |
| Dimensions | shorter side ≥ 256 px |
| Normalization | long side downscaled to ≤ 1280 px (Lanczos) |
| Fingerprint | SHA-256 of original bytes (used only to detect a changed image) |

## 2. Landmarks

MediaPipe Face Landmarker (`float16/1` model, IMAGE mode, `num_faces = 2`, blendshapes on, default 0.5 detection/presence thresholds). Requesting two faces allows multi-face rejection. Normalized coordinates are scaled by image width/height to pixels.

Validation before any measurement: ≥ 468 points; all finite; all required points within the image expanded by 5 %; and inter-ocular distance (IOD) ≥ 10 px. MediaPipe 1.1.1 does not populate per-landmark visibility for the face mesh, so occlusion is inferred from color consistency (§4.4).

Derived pose: **roll** = angle of the line between the two eye centres; **yaw asymmetry** = max(r, 1/r) where r = |nose tip(1) − right edge(234)| / |nose tip(1) − left edge(454)|.

## 3. Quality checks

Computed on the face-oval convex hull ("face mask") unless noted.

| Check | Measure | Warning | Fail |
|---|---|---|---|
| `face_size` | cheek width 234↔454 (px) | < 180 | < 120 |
| `sharpness` | variance of Laplacian of the grayscale face bounding box resized to 256 px wide | < 50 | < 20 |
| `exposure` | median L\* in face mask | < 35 or > 82 | < 25 or > 90 |
| `highlights` | fraction of face pixels with max(R,G,B) ≥ 250 | > 0.05 | > 0.15 |
| `shadows` | fraction of face pixels with max(R,G,B) ≤ 10 | > 0.05 | > 0.15 |
| `lighting_balance` | |median L\* left cheek − right cheek| | > 10 | > 18 |
| `head_yaw` | yaw asymmetry | > 1.30 | > 1.60 |
| `head_roll` | |roll| degrees | > 20 | > 40 |
| `eyes_open` | max(`eyeBlinkLeft`, `eyeBlinkRight`) blendshape | > 0.5 | — |

Effects: **skin** features are `unknown` if any of face_size, sharpness, exposure, highlights, shadows or lighting_balance fails; any warning among those makes undertone `uncertain`. **Geometry** features are `unknown` if face_size, head_yaw or head_roll fails. **Eye** features are additionally `unknown` if `eyes_open` warns or sharpness fails.

## 4. Skin-color estimation

### 4.1 Regions
Discs anchored to landmarks, radius proportional to IOD:
- right cheek: centre landmark 50, r = 0.20·IOD
- left cheek: centre landmark 280, r = 0.20·IOD
- forehead: centre landmark 151, r = 0.18·IOD

Each disc is intersected with the face mask; excluded are convex hulls of each eye contour, each eyebrow and the outer lip contour, dilated by 0.05·IOD.

### 4.2 Pixel filtering
Remove pixels with max channel ≥ 250 or ≤ 10. Convert to CIELAB (OpenCV, float32 sRGB in [0,1], D65 → L\* ∈ [0,100]). In each region keep pixels with L\* between the region's 10th and 90th percentiles. A region with < 150 remaining pixels is dropped (`insufficient_pixels`).

### 4.3 Region statistics
Per-region median (L\*, a\*, b\*). Reference = element-wise median of region medians.

### 4.4 Obstruction screening
A region whose median is more than ΔE\*ab (CIE76) = 15 from the reference is excluded as possibly obstructed (hair, glasses, hand, heavy shadow). At least **two** regions must remain, otherwise skin features are `unknown`.

### 4.5 Pooled estimate
Pixels from kept regions are pooled; pooled median (L\*, a\*, b\*) is used for classification.

### 4.6 K-Means diagnostic
K-Means (k = 3, `n_init = 4`, `random_state = 0`) on up to 3 000 pooled pixels (seeded subsample). If the largest cluster centre differs from the pooled median by ΔE > 8, a *heterogeneous samples* warning is added. **K-Means does not determine any category.**

### 4.7 Depth (ITA)
ITA° = atan2(L\* − 50, b\*) · 180/π (equivalent to arctan((L\*−50)/b\*) for b\* > 0). If b\* ≤ 0 → `unknown` (implausible skin chroma; probable color cast).

| ITA° | > 55 | 41–55 | 28–41 | 10–28 | −30–10 | < −30 |
|---|---|---|---|---|---|---|
| Depth | fair | light | medium | tan | deep | rich |

These bands follow the ITA skin-color categories (very light, light, intermediate, tan, brown, dark) of Chardon et al., 1991 and Del Bino et al., 2006, renamed for cosmetic use. Status: `uncertain` with both neighbours if within 3° of a boundary, or with the spanned categories if per-region ITA spread > 15°; otherwise `estimated`.

### 4.8 Undertone (hue angle)
h° = atan2(b\*, a\*) · 180/π. Bands: h < 52 → cool, 52 ≤ h ≤ 60 → neutral, h > 60 → warm. `uncertain` (candidates = band + nearest neighbouring band) if: within 2° of a boundary; per-region hue spread > 8°; any skin-relevant quality warning; or a color cast is suspected. **Cast check:** if pixels outside the face mask cover ≥ 10 % of the image and their mean |a\*| > 10 or mean |b\*| > 15, a cast is suspected (gray-world assumption; colored backgrounds cause false alarms, which only makes the result more conservative).

## 5. Face geometry

Measurements (pixels, roll-invariant distances): length L = |10−152|, forehead F = |54−284|, cheekbones C = |234−454|, jaw J = |172−397|, chin angle A = ∠(172, 152, 397). If C < 1 px → `unknown`. Ratios: ℓ = L/C, f = F/C, j = J/C, Δ = f − j.

Trapezoidal membership trap(x; a, b, c, d) = 0 outside [a, d], 1 on [b, c], linear between. Shape score = mean of its criteria:

| Shape | Criteria |
|---|---|
| oval | trap(ℓ; 1.18, 1.25, 1.38, 1.45), trap(j; 0.70, 0.74, 0.84, 0.88), trap(A; 95, 100, 115, 120) |
| round | trap(ℓ; 0.90, 0.95, 1.15, 1.22), trap(j; 0.76, 0.80, 0.90, 0.94), trap(A; 108, 115, 140, 150) |
| square | trap(ℓ; 0.90, 0.95, 1.20, 1.27), trap(j; 0.84, 0.88, 1.05, 1.10), trap(A; 105, 112, 140, 150) |
| heart | trap(Δ; 0.06, 0.10, 0.40, 0.50), trap(A; 80, 85, 102, 108), trap(ℓ; 1.10, 1.18, 1.42, 1.50) |
| oblong | trap(ℓ; 1.38, 1.45, 2.00, 2.10), trap(j; 0.70, 0.75, 0.95, 1.00) |

Best score < 0.5 → `uncertain` (top-2 candidates); best − second < 0.15 → `uncertain` (top-2); else `estimated`. Scores are internal and never shown as confidence.

## 6. Eye geometry

Points are rotated by −roll about the face centre before angular measures. Per eye (subject's right: outer 33, inner 133, upper 160/159/158, lower 144/145/153, brow 52; left: outer 263, inner 362, upper 387/386/385, lower 373/374/380, brow 282):
- width W = |outer − inner|
- openings oᵢ = |upperᵢ − lowerᵢ| / W (three positions); mean opening ō
- taper τ = (o₁ + o₃) / (2·o₂) (lower = more tapered ends)
- tilt θ = atan2(y_inner − y_outer, |x_outer − x_inner|) in degrees (positive = outer corner higher)
- lid space s = |upper-centre − brow| / W (weak proxy; the mesh has no crease)

Per-eye shape: ō < 0.10 → closed (no label); **hooded** if s ≤ 0.33 and ō < 0.27; **round** if ō ≥ 0.33 and τ ≥ 0.85; **almond** if 0.16 ≤ ō < 0.31 and τ ≤ 0.93 and s > 0.36; otherwise ambiguous. Both eyes same label → `estimated`; otherwise `uncertain` with the labels found (if none, `uncertain` with no candidates). *monolid* is never auto-assigned.

Tilt: mean θ of both eyes; |θ_R − θ_L| > 5° → `uncertain`. θ > 4 upturned; θ < −4 downturned; |θ| ≤ 2.5 neutral; in-between bands → `uncertain` with the two neighbours.

## 7. Recommendation scoring

### 7.1 Candidates and hard filters
Candidates are (product, shade) pairs of the requested category (shadeless products are candidates with `shade = None` only for categories that do not require shades — none of the six recommendable categories). Shades with `verification_status = unverified` are excluded from **complexion** matching (foundation, concealer, corrector) because their metadata is not confirmed.

| Category | Hard filters |
|---|---|
| foundation | user depth available (estimated, confirmed, or uncertain-with-candidates) else `needs_input`; shade depth not null; min depth distance over user depth candidates ≤ 1; excluded if the shade's listed undertone is the opposite (cool↔warm) of **every** possible user undertone (the usable value, or all uncertain candidates) |
| concealer | as foundation, but for purpose *brightening* the shade must be the same depth or one level lighter; for *spot*, within 1 level |
| color corrector | `correction_target` set in preferences else `needs_input`; shade target equals it |
| lipstick / blush / eyeliner | none (all ranking is soft) |

### 7.2 Components (each in [0, 1])
- **depth** (foundation/spot concealer): distance 0 → 1.0, 1 → 0.4. Brightening concealer: one lighter → 1.0, same → 0.8.
- **undertone**: user unknown → 0.5 (non-discriminating); shade undertone missing → 0.0; equal → 1.0; neutral vs cool/warm → 0.5. Uncertain user undertone uses the best candidate and notes it.
- **finish**: preference unset → 0.5; equal → 1.0; related (natural~satin, dewy~radiant, gloss~shimmer) → 0.5; missing on item → 0.0; else 0.0.
- **coverage**: unset → 0.5; missing → 0.0; else 1 − |Δlevel|/3 over sheer < light < medium < full.
- **purpose** (concealer): product `intended_use` contains the purpose → 1.0 else 0.0.
- **look**: unset → 0.5; shade `suitable_looks` contains it → 1.0; else 0.0.
- **color family**: unset → 0.5; equal → 1.0; related (nude~brown, nude~peach, pink~rose, rose~berry, red~berry, berry~plum, coral~peach, coral~orange, peach~terracotta, terracotta~bronze, brown~bronze) → 0.5; missing → 0.0; else 0.0.
- **intensity**: unset → 0.5; missing → 0.0; else 1 − |Δ|/2 over soft < medium < bold.
- **formulation / liner type**: unset → 0.5; equal → 1.0; missing or different → 0.0.
- **depth suitability** (corrector): user depth unusable → 0.5; in `suitable_depths` → 1.0; else 0.0.
- **target** (corrector): 1.0 (guaranteed by filter; kept for transparency).

### 7.3 Weights
foundation: depth .45, undertone .30, finish .15, coverage .10 · concealer: depth .45, undertone .25, purpose .20, finish .10 · corrector: target .60, depth suitability .40 · lipstick: look .35, color .30, intensity .20, finish .15 · blush: look .35, color .30, intensity .20, formulation .15 · eyeliner: look .40, color .35, liner type .25.

Score = Σ wᵢsᵢ, rounded to 3 decimals. Label: ≥ 0.75 *Strong fit*, ≥ 0.55 *Good fit*, else *Partial fit*. Sort by (−score, product_id, shade_id). Default limit 6.

### 7.4 Explanations
Each component maps to exactly one sentence describing what was compared (e.g. "Listed depth *tan* is one level from your *medium* depth"). Components scored 0.5 because a preference is unset produce "No *finish* preference set — finish did not affect ranking" only in the breakdown, not as a reason. Caveats are appended when: the depth/undertone used was uncertain or estimated rather than confirmed; the user's undertone is not set (so it did not affect ranking); the item is demo data; and (foundation/concealer) the standard shade-verification disclaimer.

## 8. Routine generation

1. **Validate**: inventory non-empty; look valid; items valid.
2. **Group** inventory by category → step; the first-added item is primary, others are listed as alternatives.
3. **Look applicability**: steps not listed for the look are skipped with a reason; steps in `optional_in_looks` are marked *optional*.
4. **Context**: look, preferences (coverage, intensity, concealer_order), usable features (estimated/confirmed only), formulation of each primary item.
5. **Ordering**: evaluate `when` of every constraint against the context (formulation conditions on absent steps are false). Build the graph over all defined steps, detect cycles (→ `RoutineError(ordering_cycle)`), compute reachability, and add edge u→v for present steps whenever v is reachable from u — so absent intermediate steps do not drop transitive order. Kahn's algorithm with a min-heap keyed by (`sequence`, `step_id`) gives a deterministic order.
6. **Instructions**: technique = `techniques[formulation]` if the item's formulation is known and present, else `techniques.default` plus the note "Formulation not specified; general technique shown." for items with unknown formulation. Rules are selected when look, conditions and `requires_steps` all match; within an `exclusive_group` the highest priority wins. Feature rules only use usable features.
7. **Compatibility notes** only when both items carry `base` metadata matching a `compatibility` entry.
8. **Suggestions** for steps of the look that are absent from the inventory are listed separately and labelled optional; they never become numbered steps.
9. **Signature**: SHA-256 over inventory, look, preferences and features; the UI shows a stored routine only while the signature matches.

## 9. Evaluation approach

Because no labelled dataset is available, evaluation is limited to: deterministic unit tests on synthetic images and synthetic landmark sets with known geometry; property checks (boundaries, monotonicity, division-by-zero); manual qualitative checks on sample photos; and end-to-end UI checks. These verify that the implementation follows this specification — not that the heuristics are accurate for real users.

## References
- Chardon A., Cretois I., Hourseau C. (1991). Skin colour typology and suntanning pathways. *Int. J. Cosmetic Science* 13(4):191–208.
- Del Bino S., et al. (2006). Relationship between skin response to ultraviolet exposure and skin color type. *Pigment Cell Research* 19(6):606–614.
- Google AI Edge. MediaPipe Face Landmarker documentation and model card.
