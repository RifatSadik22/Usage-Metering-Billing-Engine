from pydantic import BaseModel, ConfigDict, Field


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int = Field(ge=0, le=10_000_000)
    cached_input_tokens: int = Field(ge=0, le=10_000_000)
    output_tokens: int = Field(ge=0, le=10_000_000)
    reasoning_tokens: int = Field(ge=0, le=10_000_000)
