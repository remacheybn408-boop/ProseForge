from proseforge.application.writing.planning_service import ChapterPlanInput, PlanningService


def validate_novel_plan(plans: list[ChapterPlanInput], **kwargs) -> tuple[ChapterPlanInput, ...]:
    return PlanningService().validate(plans, **kwargs)
