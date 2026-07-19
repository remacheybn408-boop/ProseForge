from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from proseforge.domain.common.ids import new_id


VALID_KINDS = {"character", "relationship", "location", "timeline_event", "world_rule", "plot_thread", "style_rule", "promise"}
PROMISE_STATES = frozenset({"open", "developing", "resolved", "abandoned"})
PROMISE_TRANSITIONS = {
    "open": ("developing",),
    "developing": ("resolved", "abandoned"),
    "resolved": (),
    "abandoned": (),
}
_VOICE_FIELDS = frozenset({"sentence_len", "connectors", "banned_words", "emotion_baseline", "register"})


class StoryFactValidationError(ValueError):
    """Raised when a structured Story Bible fact does not meet its contract."""


def _non_empty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StoryFactValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _string_list(value: object, field: str) -> list[str]:
    if not isinstance(value, list):
        raise StoryFactValidationError(f"{field} must be a list of strings")
    items = [_non_empty_string(item, f"{field}[]") for item in value]
    return list(dict.fromkeys(items))


def _validate_voice(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise StoryFactValidationError("voice must be an object")
    missing = _VOICE_FIELDS - set(value)
    unknown = set(value) - _VOICE_FIELDS
    if missing:
        raise StoryFactValidationError(f"voice is missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise StoryFactValidationError(f"voice has unsupported fields: {', '.join(sorted(unknown))}")

    sentence_len = value["sentence_len"]
    if not isinstance(sentence_len, list) or len(sentence_len) != 2 or any(type(item) is not int for item in sentence_len):
        raise StoryFactValidationError("voice.sentence_len must be [min, max] integers")
    minimum, maximum = sentence_len
    if minimum < 1 or maximum < minimum:
        raise StoryFactValidationError("voice.sentence_len must satisfy 1 <= min <= max")

    return {
        "sentence_len": [minimum, maximum],
        "connectors": _string_list(value["connectors"], "voice.connectors"),
        "banned_words": _string_list(value["banned_words"], "voice.banned_words"),
        "emotion_baseline": _non_empty_string(value["emotion_baseline"], "voice.emotion_baseline"),
        "register": _non_empty_string(value["register"], "voice.register"),
    }


def validate_fact_value(kind: str, key: str, value: Mapping[str, object]) -> dict[str, object]:
    """Return the normalized, JSON-safe structured portion of a Story Bible fact."""
    if not isinstance(value, Mapping):
        raise StoryFactValidationError("value must be an object")

    normalized: dict[str, object] = dict(value)
    triggers = normalized.get("triggers", [key])
    normalized["triggers"] = _string_list(triggers, "triggers")

    budget_tokens = normalized.get("budget_tokens", 256)
    if type(budget_tokens) is not int or not 1 <= budget_tokens <= 200_000:
        raise StoryFactValidationError("budget_tokens must be an integer between 1 and 200000")
    normalized["budget_tokens"] = budget_tokens

    if kind == "character" and "voice" in normalized:
        normalized["voice"] = _validate_voice(normalized["voice"])
    return normalized


@dataclass(frozen=True)
class StoryFact:
    project_id: str
    kind: str
    key: str
    value: dict[str, object]
    pinned: bool = False
    status: str = ""
    id: str = ""
    version: int = 1
    confidence: float = 1.0
    source: str = "user"

    def __post_init__(self) -> None:
        if not isinstance(self.project_id, str) or not self.project_id:
            raise StoryFactValidationError("project_id must be a non-empty string")
        if self.kind not in VALID_KINDS:
            raise StoryFactValidationError("unsupported story bible kind")
        key = _non_empty_string(self.key, "key")
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "value", validate_fact_value(self.kind, key, self.value))
        if type(self.pinned) is not bool:
            raise StoryFactValidationError("pinned must be a boolean")
        if type(self.version) is not int or self.version < 1:
            raise StoryFactValidationError("version must be a positive integer")
        if not isinstance(self.confidence, (int, float)) or not 0 <= float(self.confidence) <= 1:
            raise StoryFactValidationError("confidence must be between 0 and 1")
        if not isinstance(self.source, str) or not self.source.strip():
            raise StoryFactValidationError("source must be a non-empty string")

        if self.kind == "promise":
            status = self.status or "open"
            if status not in PROMISE_STATES:
                raise StoryFactValidationError("unsupported promise status")
        else:
            if self.status not in {"", "active"}:
                raise StoryFactValidationError("only promise facts may have a non-active status")
            status = "active"
        object.__setattr__(self, "status", status)

    @classmethod
    def create(
        cls,
        project_id: str,
        kind: str,
        key: str,
        value: dict[str, object],
        *,
        pinned: bool = False,
        status: str = "",
        confidence: float = 1.0,
        source: str = "user",
    ) -> "StoryFact":
        return cls(project_id, kind, key, value, pinned=pinned, status=status, id=new_id(), confidence=confidence, source=source)
