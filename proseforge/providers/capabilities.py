from proseforge.domain.common.errors import ValidationError
from proseforge.domain.ports.model_provider import GenerationRequest, ProviderModel


class ModelCapabilityError(ValidationError):
    code = "MODEL_CAPABILITY_ERROR"

    def __init__(self, missing: tuple[str, ...]):
        self.missing = missing
        super().__init__(f"missing model capabilities: {', '.join(missing)}")


def validate_request(model: ProviderModel, request: GenerationRequest) -> None:
    missing: list[str] = []
    caps = model.capabilities
    if request.response_schema is not None and not caps.get("structured_output", False):
        missing.append("structured_output")
    if request.reasoning is not None and not caps.get("reasoning", False):
        missing.append("reasoning")
    if request.provider_options.get("tools") and not caps.get("tools", False):
        missing.append("tools")
    if request.max_output_tokens and model.max_output_tokens and request.max_output_tokens > model.max_output_tokens:
        missing.append("max_output_tokens")
    if missing:
        raise ModelCapabilityError(tuple(missing))
