"""All session-state keys and transitions.

Functions take any ``MutableMapping`` (``st.session_state`` in the app, a ``dict`` in tests),
so per-user state never lives in module globals and transitions are unit-testable.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from src.core.features import (
    FEATURE_NAMES,
    FEATURE_VALUES,
    AnalysisResult,
    FeatureEstimate,
    UserProfile,
)
from src.routine.inventory import InventoryItem
from src.routine.routine_generator import Routine

ANALYSIS = "bs_analysis"
ANALYSIS_ERROR = "bs_analysis_error"
IMAGE_FP = "bs_image_fp"
PROFILE = "bs_profile"
INVENTORY = "bs_inventory"
ROUTINE = "bs_routine"
UPLOADER_NONCE = "bs_uploader_nonce"
FLASH = "bs_flash"
ENTERED = "bs_entered"

State = MutableMapping[str, Any]


def init_state(ss: State) -> None:
    ss.setdefault(ANALYSIS, None)
    ss.setdefault(ANALYSIS_ERROR, None)
    ss.setdefault(IMAGE_FP, None)
    ss.setdefault(PROFILE, UserProfile())
    ss.setdefault(INVENTORY, ())
    ss.setdefault(ROUTINE, None)
    ss.setdefault(UPLOADER_NONCE, 0)
    ss.setdefault(FLASH, None)
    ss.setdefault(ENTERED, False)


# --------------------------------------------------------------------------- welcome
def has_entered(ss: State) -> bool:
    """False until the visitor leaves the welcome screen; lasts for the browser session."""
    return bool(ss.get(ENTERED, False))


def enter_studio(ss: State) -> None:
    ss[ENTERED] = True


# --------------------------------------------------------------------------- analysis
def get_analysis(ss: State) -> AnalysisResult | None:
    return ss.get(ANALYSIS)


def get_profile(ss: State) -> UserProfile:
    return ss.get(PROFILE) or UserProfile()


def note_image(ss: State, fingerprint: str | None) -> bool:
    """Record the image currently selected. A *different* image invalidates the previous
    analysis, its error and the profile derived from it. Returns True if anything was cleared.

    An empty widget (``None``) does not clear results: Streamlit drops widget values when the
    user navigates between pages, and the stored results still describe the photo they came
    from. Explicit clearing goes through ``clear_analysis``.
    """
    if fingerprint is None or fingerprint == ss.get(IMAGE_FP):
        return False
    had_results = ss.get(ANALYSIS) is not None or ss.get(ANALYSIS_ERROR) is not None
    ss[IMAGE_FP] = fingerprint
    analysis = ss.get(ANALYSIS)
    if analysis is not None and analysis.image_fingerprint != fingerprint:
        clear_analysis(ss, reset_widgets=False)
    ss[ANALYSIS_ERROR] = None
    return had_results


def set_analysis(ss: State, result: AnalysisResult) -> None:
    ss[ANALYSIS] = result
    ss[ANALYSIS_ERROR] = None
    ss[IMAGE_FP] = result.image_fingerprint
    ss[PROFILE] = UserProfile.from_analysis(result)


def set_analysis_error(ss: State, fingerprint: str, code: str, message: str) -> None:
    ss[ANALYSIS] = None
    if get_profile(ss).source == "analysis":
        ss[PROFILE] = UserProfile()
    ss[ANALYSIS_ERROR] = {"fingerprint": fingerprint, "code": code, "message": message}


def get_analysis_error(ss: State, fingerprint: str | None) -> Mapping[str, str] | None:
    err = ss.get(ANALYSIS_ERROR)
    if err and fingerprint and err["fingerprint"] == fingerprint:
        return err
    return None


def clear_analysis(ss: State, reset_widgets: bool = True) -> None:
    """Forget the analysis (including its overlay image) and any profile derived from it."""
    ss[ANALYSIS] = None
    ss[ANALYSIS_ERROR] = None
    if get_profile(ss).source == "analysis":
        ss[PROFILE] = UserProfile()
    if reset_widgets:
        ss[IMAGE_FP] = None
        ss[UPLOADER_NONCE] = ss.get(UPLOADER_NONCE, 0) + 1


def uploader_key(ss: State, name: str) -> str:
    return f"{name}_{ss.get(UPLOADER_NONCE, 0)}"


def confirm_features(ss: State, selections: Mapping[str, str | None]) -> UserProfile:
    """Apply the user's choices: a value becomes ``user_confirmed``.

    ``None`` ("Not set") clears a previously usable value, but leaves an uncertain or
    unknown estimate untouched so its candidates and reasons are not lost.
    """
    profile = get_profile(ss)
    for name, value in selections.items():
        if name not in FEATURE_NAMES:
            raise ValueError(f"Unknown feature {name!r}")
        current = profile.get(name)
        if value is None:
            if not current.usable:
                continue
            est = FeatureEstimate.unknown(name, "Not set.")
        elif value not in FEATURE_VALUES[name]:
            raise ValueError(f"Invalid value {value!r} for {name}")
        else:
            est = current.confirmed(value)
        profile = profile.with_feature(est)
    ss[PROFILE] = profile
    return profile


# --------------------------------------------------------------------------- inventory / routine
def get_inventory(ss: State) -> tuple[InventoryItem, ...]:
    return tuple(ss.get(INVENTORY, ()))


def set_inventory(ss: State, inventory: tuple[InventoryItem, ...]) -> None:
    ss[INVENTORY] = tuple(inventory)


def store_routine(ss: State, routine: Routine) -> None:
    ss[ROUTINE] = routine


def current_routine(ss: State, signature: str) -> Routine | None:
    """The stored routine only if it was generated from exactly the current inputs."""
    routine = ss.get(ROUTINE)
    return routine if routine is not None and routine.signature == signature else None


def routine_is_stale(ss: State, signature: str) -> bool:
    routine = ss.get(ROUTINE)
    return routine is not None and routine.signature != signature


def clear_routine(ss: State) -> None:
    ss[ROUTINE] = None


def flash(ss: State, message: str | None = None) -> str | None:
    """Set a one-shot message (with ``message``) or pop it (without)."""
    if message is not None:
        ss[FLASH] = message
        return None
    msg, ss[FLASH] = ss.get(FLASH), None
    return msg
