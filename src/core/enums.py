"""Enumerations shared across the vision, data, recommendation and routine layers."""

from __future__ import annotations

from enum import Enum
from enum import StrEnum as _StdStrEnum


class StrEnum(_StdStrEnum):
    """String-valued enum (``str()`` is its value) with a display label."""

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").capitalize()


class Category(StrEnum):
    SKIN_PREP = "skin_prep"
    PRIMER = "primer"
    COLOR_CORRECTOR = "color_corrector"
    FOUNDATION = "foundation"
    CONCEALER = "concealer"
    POWDER = "powder"
    BRONZER = "bronzer"
    BLUSH = "blush"
    HIGHLIGHTER = "highlighter"
    EYEBROW = "eyebrow"
    EYESHADOW = "eyeshadow"
    EYELINER = "eyeliner"
    MASCARA = "mascara"
    LIP_LINER = "lip_liner"
    LIPSTICK = "lipstick"
    SETTING_SPRAY = "setting_spray"


CATEGORY_LABELS: dict[Category, str] = {
    Category.SKIN_PREP: "Skin prep",
    Category.PRIMER: "Primer",
    Category.COLOR_CORRECTOR: "Color corrector",
    Category.FOUNDATION: "Foundation",
    Category.CONCEALER: "Concealer",
    Category.POWDER: "Powder",
    Category.BRONZER: "Bronzer",
    Category.BLUSH: "Blush",
    Category.HIGHLIGHTER: "Highlighter",
    Category.EYEBROW: "Eyebrow",
    Category.EYESHADOW: "Eyeshadow",
    Category.EYELINER: "Eyeliner",
    Category.MASCARA: "Mascara",
    Category.LIP_LINER: "Lip liner",
    Category.LIPSTICK: "Lipstick",
    Category.SETTING_SPRAY: "Setting spray",
}

RECOMMENDABLE_CATEGORIES: tuple[Category, ...] = (
    Category.FOUNDATION,
    Category.CONCEALER,
    Category.COLOR_CORRECTOR,
    Category.LIPSTICK,
    Category.BLUSH,
    Category.EYELINER,
)

COMPLEXION_CATEGORIES: frozenset[Category] = frozenset(
    {Category.FOUNDATION, Category.CONCEALER, Category.COLOR_CORRECTOR}
)


class Depth(StrEnum):
    """Visible skin depth, ordered from lightest to deepest."""

    FAIR = "fair"
    LIGHT = "light"
    MEDIUM = "medium"
    TAN = "tan"
    DEEP = "deep"
    RICH = "rich"

    @property
    def index(self) -> int:
        return DEPTH_ORDER.index(self)


DEPTH_ORDER: tuple[Depth, ...] = tuple(Depth)


class Undertone(StrEnum):
    COOL = "cool"
    NEUTRAL = "neutral"
    WARM = "warm"


class EyeShape(StrEnum):
    ALMOND = "almond"
    ROUND = "round"
    HOODED = "hooded"
    MONOLID = "monolid"  # user-selectable only; never auto-assigned


class EyeTilt(StrEnum):
    UPTURNED = "upturned"
    NEUTRAL = "neutral"
    DOWNTURNED = "downturned"


class FaceShape(StrEnum):
    OVAL = "oval"
    ROUND = "round"
    SQUARE = "square"
    HEART = "heart"
    OBLONG = "oblong"


class Look(StrEnum):
    EVERYDAY = "everyday"
    OFFICE = "office"
    FESTIVE = "festive"
    GLAM = "glam"


class Finish(StrEnum):
    MATTE = "matte"
    NATURAL = "natural"
    SATIN = "satin"
    DEWY = "dewy"
    RADIANT = "radiant"
    GLOSS = "gloss"
    SHIMMER = "shimmer"
    METALLIC = "metallic"


class Coverage(StrEnum):
    SHEER = "sheer"
    LIGHT = "light"
    MEDIUM = "medium"
    FULL = "full"

    @property
    def index(self) -> int:
        return tuple(Coverage).index(self)


class Intensity(StrEnum):
    SOFT = "soft"
    MEDIUM = "medium"
    BOLD = "bold"

    @property
    def index(self) -> int:
        return tuple(Intensity).index(self)


class Formulation(StrEnum):
    LIQUID = "liquid"
    CREAM = "cream"
    POWDER = "powder"
    GEL = "gel"
    STICK = "stick"
    PENCIL = "pencil"
    BALM = "balm"
    SPRAY = "spray"


class Base(StrEnum):
    WATER = "water"
    SILICONE = "silicone"
    OIL = "oil"


class ColorFamily(StrEnum):
    NUDE = "nude"
    PINK = "pink"
    ROSE = "rose"
    CORAL = "coral"
    RED = "red"
    BERRY = "berry"
    PLUM = "plum"
    BROWN = "brown"
    PEACH = "peach"
    TERRACOTTA = "terracotta"
    BLACK = "black"
    NAVY = "navy"
    GREEN = "green"
    BRONZE = "bronze"
    LAVENDER = "lavender"
    ORANGE = "orange"


class CorrectionTarget(StrEnum):
    DARK_CIRCLES = "dark_circles"
    REDNESS = "redness"
    DULLNESS = "dullness"


class ConcealerPurpose(StrEnum):
    BRIGHTENING = "brightening"
    SPOT = "spot"


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    DEMO = "demo"


class ConcealerOrder(StrEnum):
    AFTER_FOUNDATION = "after_foundation"
    BEFORE_FOUNDATION = "before_foundation"


def enum_values(enum_cls: type[Enum]) -> tuple[str, ...]:
    """Return the string values of an enum class, in definition order."""
    return tuple(member.value for member in enum_cls)
