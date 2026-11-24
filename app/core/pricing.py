from dataclasses import dataclass

PRICING_VERSION = "demo-2026-01"
MICRO_USD_PER_USD = 1_000_000

API_CALL_MICRO_USD = 1_000
FRESH_INPUT_MICRO_USD_PER_TOKEN = 1
CACHED_INPUT_MICRO_USD_PER_TOKEN = 1 / 4
OUTPUT_MICRO_USD_PER_TOKEN = 4
REASONING_MICRO_USD_PER_TOKEN = 4


@dataclass(frozen=True)
class CostBreakdown:
    api_calls: int
    fresh_input: int
    cached_input: int
    output: int
    reasoning: int
    api_call_micro_usd: int
    fresh_input_micro_usd: int
    cached_input_micro_usd: int
    output_micro_usd: int
    reasoning_micro_usd: int
    total_micro_usd: int


def calculate_cost(
    fresh_input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    reasoning_tokens: int,
    api_calls: int = 1,
) -> CostBreakdown:
    api_cost = api_calls * API_CALL_MICRO_USD
    fresh_cost = fresh_input_tokens * FRESH_INPUT_MICRO_USD_PER_TOKEN
    # Round each category to the nearest micro-USD, with .5 rounded up.
    cached_cost = (cached_input_tokens + 2) // 4
    output_cost = output_tokens * OUTPUT_MICRO_USD_PER_TOKEN
    reasoning_cost = reasoning_tokens * REASONING_MICRO_USD_PER_TOKEN
    return CostBreakdown(
        api_calls=api_calls,
        fresh_input=fresh_input_tokens,
        cached_input=cached_input_tokens,
        output=output_tokens,
        reasoning=reasoning_tokens,
        api_call_micro_usd=api_cost,
        fresh_input_micro_usd=fresh_cost,
        cached_input_micro_usd=cached_cost,
        output_micro_usd=output_cost,
        reasoning_micro_usd=reasoning_cost,
        total_micro_usd=api_cost + fresh_cost + cached_cost + output_cost + reasoning_cost,
    )


def format_usd(micro_usd: int) -> str:
    dollars, remainder = divmod(micro_usd, MICRO_USD_PER_USD)
    return f"${dollars}.{remainder:06d}"
