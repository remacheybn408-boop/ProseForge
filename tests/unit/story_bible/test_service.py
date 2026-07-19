from __future__ import annotations

import pytest

from proseforge.application.story_bible.service import StoryBibleService, StoryBibleStatusTransitionError
from proseforge.domain.story_bible.entities import StoryFact


def _promise(status: str = "open") -> StoryFact:
    return StoryFact.create("project", "promise", "the letter", {"triggers": ["letter"], "budget_tokens": 20}, status=status)


def test_match_triggers_keeps_pins_and_only_matching_entries():
    seed = StoryFact.create("project", "location", "harbor", {"triggers": ["harbor"], "budget_tokens": 20})
    pinned = StoryFact(**{**seed.__dict__, "pinned": True})
    triggered = StoryFact.create("project", "character", "Mira", {"triggers": ["Mira"], "budget_tokens": 20})
    unmatched = StoryFact.create("project", "character", "Ilan", {"triggers": ["Ilan"], "budget_tokens": 20})

    matches = StoryBibleService.match_triggers([pinned, triggered, unmatched], "Mira enters the room")

    assert [(match.fact.id, match.reason) for match in matches] == [(pinned.id, "pinned"), (triggered.id, "trigger:Mira")]


def test_promise_rejects_terminal_state_transition_with_allowed_values():
    with pytest.raises(StoryBibleStatusTransitionError) as error:
        StoryBibleService.validate_status_transition(_promise("resolved"), "open")

    assert error.value.allowed == ()
