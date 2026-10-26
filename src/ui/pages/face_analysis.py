"""Face Analysis page: capture/upload, analyse, review and correct."""

from __future__ import annotations

import logging

import streamlit as st

from src.core.errors import (
    FaceDetectionError,
    ImageValidationError,
    LandmarkValidationError,
    ModelUnavailableError,
)
from src.ui import navigation as nav
from src.ui import state
from src.ui.components import (
    ESTIMATE_NOTICE,
    e,
    error_card,
    feature_cards,
    html,
    notice,
    page_header,
    profile_editor,
    quality_checks,
    section_title,
)
from src.ui.resources import get_detector
from src.vision.image_io import fingerprint_bytes
from src.vision.pipeline import analyze_image

logger = logging.getLogger(__name__)

UPLOAD, CAMERA = "Upload a photo", "Use my camera"
GUIDANCE = """<strong>For the most reliable estimates</strong><ul>
<li>Face a window or soft, even light — avoid coloured or harsh overhead light.</li>
<li>Look straight at the camera with a neutral expression and eyes open.</li>
<li>Remove glasses and keep hair away from your forehead and cheeks.</li>
<li>Bare skin or light makeup gives the most representative colour.</li>
<li>Only one face in the frame. JPEG, PNG or WebP, up to 10 MB.</li></ul>"""


def _photo_input(ss) -> bytes | None:
    source = st.segmented_control("Photo source", [UPLOAD, CAMERA], default=UPLOAD,
                                  key="bs_photo_source", label_visibility="collapsed")
    if source == CAMERA:
        shot = st.camera_input("Take a photo", key=state.uploader_key(ss, "bs_camera"),
                               help="Your browser will ask for camera permission.")
        st.caption("No camera, or permission denied? Switch to “Upload a photo” — it always "
                   "works.")
        return shot.getvalue() if shot is not None else None
    upload = st.file_uploader("Upload a photo", type=["jpg", "jpeg", "png", "webp"],
                              key=state.uploader_key(ss, "bs_upload"),
                              help="Processed in memory only; never saved.")
    return upload.getvalue() if upload is not None else None


def _run_analysis(ss, data: bytes, fingerprint: str) -> None:
    try:
        detector = get_detector()
    except ModelUnavailableError as exc:
        state.set_analysis_error(ss, fingerprint, exc.code, exc.user_message)
        return
    with st.status("Analyzing your photo…", expanded=False) as status:
        try:
            status.update(label="Checking the image and finding your face…")
            result = analyze_image(data, detector)
        except (ImageValidationError, FaceDetectionError, LandmarkValidationError) as exc:
            status.update(label="The photo could not be analysed", state="error")
            state.set_analysis_error(ss, fingerprint, exc.code, exc.user_message)
            return
        status.update(label="Analysis complete", state="complete")
    state.set_analysis(ss, result)
    state.flash(ss, "Analysis complete. Review the estimates below.")
    st.rerun()


def _results(ss) -> None:
    analysis = state.get_analysis(ss)
    profile = state.get_profile(ss)
    section_title("Your estimates", kicker="Results")
    notice(ESTIMATE_NOTICE)

    left, right = st.columns([1, 2], gap="large")
    with left:
        if analysis.overlay_jpeg:
            st.image(analysis.overlay_jpeg, width="stretch",
                     caption="Rose circles: skin areas sampled. Grey circles: areas ignored "
                             "(covered, shadowed or too small).")
    with right:
        feature_cards(profile)
        for warning in analysis.warnings:
            notice(e(warning), kind="warn")

    with st.expander("Photo quality checks", expanded=bool(analysis.unreliable_features)):
        quality_checks(analysis.quality_checks)

    section_title("Review and correct", kicker="Your profile",
                  subtitle="Keep what looks right, change what doesn't. Confirmed values are "
                           "used for your shade and routine recommendations.")
    with st.container(key="bs-card-correct"):
        selections = profile_editor(profile, key="bs_correct_form",
                                    submit_label="Confirm my profile")
    if selections is not None:
        state.confirm_features(ss, selections)
        state.flash(ss, "Profile saved. Your choices are marked as confirmed.")
        st.rerun()

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("See my shades", type="primary", width="stretch"):
            st.switch_page(nav.page(nav.SHADES))
    with c2:
        if st.button("Build my routine", width="stretch"):
            st.switch_page(nav.page(nav.ROUTINE))
    with c3:
        if st.button("Start over with a new photo", width="stretch"):
            state.clear_analysis(ss)
            st.rerun()


def render() -> None:
    ss = st.session_state
    page_header("Workflow one · Discover my shades", "Face Analysis",
                "Upload a clear, front-facing photo or use your camera. Nothing is stored.")
    if msg := state.flash(ss):
        st.success(msg)

    col_in, col_preview = st.columns([1.1, 1], gap="large")
    with col_in, st.container(key="bs-card-input"):
        data = _photo_input(ss)
        notice(GUIDANCE)
    fingerprint = fingerprint_bytes(data) if data else None
    if state.note_image(ss, fingerprint):
        st.info("A new photo was selected, so the previous results were cleared.")

    with col_preview:
        if data:
            st.image(data, caption="Preview", width="stretch")
            if st.button("Analyze my photo", type="primary", width="stretch"):
                _run_analysis(ss, data, fingerprint)
        else:
            html('<div class="bs-empty"><h3 class="bs-h3">No photo yet</h3><p>Choose a photo or '
                 'take one with your camera to begin. You can also skip this step and set your '
                 'profile by hand on the Shade Finder page.</p></div>')
            st.page_link(nav.page(nav.SHADES), label="Set my profile manually")

    err = state.get_analysis_error(ss, fingerprint)
    if err:
        error_card("We couldn't analyse this photo", err["message"],
                   "Try another photo following the tips above, or set your profile manually.")
        if st.button("Try a different photo"):
            state.clear_analysis(ss)
            st.rerun()

    if state.get_analysis(ss) is not None:
        if data is None:
            st.caption("Showing results for the photo you analysed earlier. Upload a new photo to "
                       "replace them.")
        _results(ss)
