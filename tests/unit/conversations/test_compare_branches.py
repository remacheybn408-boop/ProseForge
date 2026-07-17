from proseforge.application.conversations.compare_branches import compare_messages


class Item:
    def __init__(self, id): self.id = id


def test_compare_keeps_branch_candidates_separate():
    result = compare_messages([Item("a"), Item("left")], [Item("a"), Item("right")])
    assert result["common_count"] == 1
    assert result["left"][0].id == "left"
    assert result["right"][0].id == "right"
