# Known Limitations — The Beauty Studio

## 1. Measurement validity
- **Uncalibrated images.** Phone/webcam photos go through auto white balance, exposure, tone mapping and beauty filters. CIELAB values derived from them are not colorimetric measurements of skin. The ITA metric was defined for calibrated instruments.
- **Undertone heuristic.** The hue-angle bands (52°/60°) are engineering heuristics. Undertone is a cosmetic concept without a single agreed measurable definition; the app reports it as a *possible* undertone and frequently returns `uncertain`.
- **No olive detection.** Olive undertones are not modelled; users can only express them through the nearest available option.
- **Thresholds not validated.** All quality, depth, undertone, face and eye thresholds are provisional and have not been tuned or evaluated on a labelled, demographically diverse dataset. **No accuracy figure exists and none is claimed.**
- **Possible bias.** Lighting and camera pipelines can affect deeper and lighter skin differently; MediaPipe's own model card reports fairness evaluation of the landmark model, not of this project's heuristics.

## 2. Geometry
- MediaPipe landmark 10 lies below the hairline, so "face length" is a relative measure.
- The mesh has no eyelid-crease landmarks: *hooded* is a weak proxy based on brow-to-lid distance and *monolid* is never auto-detected.
- Expressions, glasses, hair and non-frontal pose distort ratios; the yaw/roll checks catch only large deviations; pitch is not checked.
- Face-shape categories are fuzzy cosmetic conventions; many faces genuinely sit between them.

## 3. Product data
- **The bundled catalog is fictional demonstration data** (brands *Atelier Demo* and *Lumen Demo*). During development, official brand pages that were checked did not expose verifiable per-shade depth/undertone metadata in a fetchable form, and inferring such data would be fabrication. Demo items carry no prices or links and are badged in the UI.
- Swatch colors shown for demo shades are illustrative only.
- Adding real products requires a person to verify each field from an authoritative source and record provenance (`verification_status: "verified"`).

## 4. Recommendations and routines
- Fit scores rank catalog items against the selected profile; they are not probabilities and do not guarantee a match. Foundation shades should always be tested on the jawline in daylight.
- Routine instructions are general cosmetic guidance; preferences in makeup are subjective. Custom products with unknown formulation receive general technique only.
- The system is not a medical device and makes no dermatological claims; allergies and sensitivities are not assessed beyond generic patch-test cautions.

## 5. Platform
- Single face, single still image; no video or multi-face analysis.
- Streamlit layout constraints: columns stack on narrow screens; custom styling is limited to documented theming options and key-based container classes.
- Camera capture requires browser permission and HTTPS (or localhost).
- The model asset (~3.7 MB) is downloaded on first analysis if absent; offline deployments must provide it via `scripts/download_model.py`.
- Session state is lost on browser refresh or server restart (by design: no persistence).
