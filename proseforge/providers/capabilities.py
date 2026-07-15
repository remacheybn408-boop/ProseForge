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
    supported_modalities = set(caps.get("input_modalities", ("text",)))
    for block in (*request.system_blocks, *request.input_blocks):
        modality = str(block.get("modality", block.get("type", "text")))
        if modality in {"text", "message"}:
            modality = "text"
        if modality not in supported_modalities:
            missing.append(f"input_modality:{modality}")
            break
    if request.response_schema is not None and not caps.get("structured_output", False):
        missing.append("structured_output")
    if request.reasoning is not None and not caps.get("reasoning", False):
        missing.append("reasoning")
    if request.provider_options.get("tools") and not caps.get("tools", False):
        missing.append("tools")
    if request.max_output_tokens and model.max_output_tokens and request.max_output_tokens > model.max_output_tokens:
        missing.append("max_output_tokens")
    if model.context_window is not None:
        estimated_input = sum(len(str(block)) for block in (*request.system_blocks, *request.input_blocks)) // 4
        requested = estimated_input + (request.max_output_tokens or 0)
        if requested > model.context_window:
            missing.append("context_window")
    if missing:
        raise ModelCapabilityError(tuple(missing))
