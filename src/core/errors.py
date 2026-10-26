"""Typed errors carrying a machine-readable code and a user-facing message."""

from __future__ import annotations


class BeautyStudioError(Exception):
    """Base class for expected, user-reportable failures."""

    default_message = "Something went wrong."

    def __init__(self, code: str, user_message: str | None = None, *, details: str = "") -> None:
        self.code = code
        self.user_message = user_message or self.default_message
        self.details = details
        super().__init__(f"{code}: {self.user_message}" + (f" ({details})" if details else ""))


class ImageValidationError(BeautyStudioError):
    default_message = "This image could not be used."


class FaceDetectionError(BeautyStudioError):
    default_message = "A single, clearly visible face is required."


class LandmarkValidationError(BeautyStudioError):
    default_message = "Facial landmarks could not be measured reliably in this photo."


class ModelUnavailableError(BeautyStudioError):
    default_message = "The face-analysis model is not available."


class CatalogError(BeautyStudioError):
    """Raised when knowledge-base files fail validation. ``issues`` lists every problem."""

    default_message = "The product knowledge base is invalid."

    def __init__(self, issues: list[str], user_message: str | None = None) -> None:
        self.issues = list(issues)
        super().__init__("catalog_invalid", user_message, details="; ".join(self.issues[:10]))


class RoutineError(BeautyStudioError):
    default_message = "A routine could not be generated."
