from proseforge.application.outlines.intake_service import OutlineIntakeService, OutlineSpec


def intake_outline(payload: dict[str, object]) -> tuple[OutlineSpec, tuple[str, ...]]:
    service = OutlineIntakeService()
    spec = service.parse(payload)
    return spec, service.clarification_questions(spec)
