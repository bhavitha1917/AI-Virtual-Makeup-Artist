"""Validated schema for facial-feature estimates, analysis results and user profiles.

Every feature carries an explicit status so the UI and downstream engines can
distinguish *unknown*, *uncertain*, *estimated* and *user-confirmed* values.
No confidence percentages are represented anywhere in this schema.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from types import MappingProxyType

from src.core.enums import Depth, EyeShape, EyeTilt, FaceShape, Undertone, enum_values


class FeatureStatus(StrEnum):
    UNKNOWN = "unknown"
    UNCERTAIN = "uncertain"
    ESTIMATED = "estimated"
    USER_CONFIRMED = "user_confirmed"


SKIN_DEPTH = "skin_depth"
UNDERTONE = "undertone"
EYE_SHAPE = "eye_shape"
EYE_TILT = "eye_tilt"
FACE_SHAPE = "face_shape"

FEATURE_VALUES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        SKIN_DEPTH: enum_values(Depth),
        UNDERTONE: enum_values(Undertone),
        EYE_SHAPE: enum_values(EyeShape),
        EYE_TILT: enum_values(EyeTilt),
        FACE_SHAPE: enum_values(FaceShape),
    }
)
FEATURE_NAMES: tuple[str, ...] = tuple(FEATURE_VALUES)

FEATURE_LABELS: Mapping[str, str] = MappingProxyType(
    {
        SKIN_DEPTH: "Skin depth",
        UNDERTONE: "Undertone",
        EYE_SHAPE: "Eye shape",
        EYE_TILT: "Eye tilt",
        FACE_SHAPE: "Face shape",
    }
)


@dataclass(frozen=True)
class FeatureEstimate:
    """One estimated facial feature.

    Invariants (enforced on construction):
    - ``estimated`` / ``user_confirmed`` require an allowed ``value`` and no candidates.
    - ``uncertain`` has ``value=None``; candidates are allowed values.
    - ``unknown`` has ``value=None`` and no candidates.
    """

    name: str
    status: FeatureStatus
    value: str | None = None
    candidates: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    measurements: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.name not in FEATURE_VALUES:
            raise ValueError(f"Unknown feature name: {self.name!r}")
        allowed = FEATURE_VALUES[self.name]
        status = FeatureStatus(self.status)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "candidates", tuple(dict.fromkeys(self.candidates)))
        object.__setattr__(self, "reasons", tuple(self.reasons))
        measurements = {k: float(v) for k, v in self.measurements.items()}
        object.__setattr__(self, "measurements", MappingProxyType(measurements))
        if status in (FeatureStatus.ESTIMATED, FeatureStatus.USER_CONFIRMED):
            if self.value not in allowed:
                raise ValueError(f"{self.name}: value {self.value!r} not in {allowed}")
            if self.candidates:
                raise ValueError(f"{self.name}: {status.value} estimates must not list candidates")
        else:
            if self.value is not None:
                raise ValueError(f"{self.name}: {status.value} estimates must not carry a value")
            if status is FeatureStatus.UNKNOWN and self.candidates:
                raise ValueError(f"{self.name}: unknown estimates must not list candidates")
        bad = [c for c in self.candidates if c not in allowed]
        if bad:
            raise ValueError(f"{self.name}: invalid candidates {bad}")

    @property
    def usable(self) -> bool:
        """True if the value may drive recommendations and tips."""
        return self.status in (FeatureStatus.ESTIMATED, FeatureStatus.USER_CONFIRMED)

    @property
    def possible_values(self) -> tuple[str, ...]:
        """Values to consider downstream: the value if usable, else uncertain candidates."""
        if self.usable:
            return (self.value,)  # type: ignore[return-value]
        return self.candidates

    def confirmed(self, value: str) -> FeatureEstimate:
        """Return a user-confirmed copy (keeps measurements for transparency)."""
        return replace(
            self, status=FeatureStatus.USER_CONFIRMED, value=value, candidates=(), reasons=()
        )

    @classmethod
    def unknown(cls, name: str, *reasons: str) -> FeatureEstimate:
        return cls(name=name, status=FeatureStatus.UNKNOWN, reasons=tuple(reasons))

    @classmethod
    def user_set(cls, name: str, value: str) -> FeatureEstimate:
        return cls(name=name, status=FeatureStatus.USER_CONFIRMED, value=value)


class Severity(StrEnum):
    OK = "ok"
    WARNING = "warning"
    FAIL = "fail"


@dataclass(frozen=True)
class QualityCheck:
    check_id: str
    severity: Severity
    message: str
    value: float | None = None

    @property
    def label(self) -> str:
        return {"ok": "Passed", "warning": "Warning", "fail": "Failed"}[self.severity.value]


@dataclass(frozen=True)
class AnalysisResult:
    """Structured output of a face analysis. Holds no original image pixels."""

    image_fingerprint: str
    image_size: tuple[int, int]
    quality_checks: tuple[QualityCheck, ...]
    features: Mapping[str, FeatureEstimate]
    warnings: tuple[str, ...] = ()
    overlay_jpeg: bytes | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        missing = set(FEATURE_NAMES) - set(self.features)
        if missing:
            raise ValueError(f"AnalysisResult missing features: {sorted(missing)}")
        object.__setattr__(self, "features", MappingProxyType(dict(self.features)))

    @property
    def unreliable_features(self) -> tuple[str, ...]:
        return tuple(n for n in FEATURE_NAMES if not self.features[n].usable)


@dataclass(frozen=True)
class UserProfile:
    """Features used by the recommendation and routine engines."""

    features: Mapping[str, FeatureEstimate] = field(default_factory=dict)
    source: str = "manual"  # "analysis" | "manual"

    def __post_init__(self) -> None:
        if self.source not in ("analysis", "manual"):
            raise ValueError(f"Invalid profile source {self.source!r}")
        full = {n: self.features.get(n) or FeatureEstimate.unknown(n) for n in FEATURE_NAMES}
        object.__setattr__(self, "features", MappingProxyType(full))

    def get(self, name: str) -> FeatureEstimate:
        return self.features[name]

    def with_feature(self, estimate: FeatureEstimate) -> UserProfile:
        updated = dict(self.features)
        updated[estimate.name] = estimate
        return UserProfile(features=updated, source=self.source)

    @property
    def is_empty(self) -> bool:
        return all(f.status is FeatureStatus.UNKNOWN for f in self.features.values())

    @classmethod
    def from_analysis(cls, result: AnalysisResult) -> UserProfile:
        return cls(features=dict(result.features), source="analysis")
