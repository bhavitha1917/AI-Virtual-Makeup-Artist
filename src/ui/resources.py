"""Process-wide cached resources. Only immutable data and the thread-safe detector are
shared across sessions; nothing user-specific is cached here."""

from __future__ import annotations

import streamlit as st

from src.data.loader import load_catalog
from src.data.schema import Catalog, TutorialRules
from src.routine.rule_engine import load_validated_rules
from src.vision.face_landmarks import MediaPipeFaceLandmarker
from src.vision.model_asset import ensure_model


@st.cache_resource(show_spinner=False)
def get_catalog() -> Catalog:
    return load_catalog()


@st.cache_resource(show_spinner=False)
def get_rules() -> TutorialRules:
    return load_validated_rules()


@st.cache_resource(show_spinner="Preparing the face-analysis model…")
def get_detector() -> MediaPipeFaceLandmarker:
    """Raises ``ModelUnavailableError`` (not cached, so a later call can retry)."""
    return MediaPipeFaceLandmarker(ensure_model())
