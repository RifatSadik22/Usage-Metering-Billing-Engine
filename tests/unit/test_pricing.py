from app.core.pricing import calculate_cost, format_usd


def test_worked_example() -> None:
    cost = calculate_cost(
        fresh_input_tokens=1000,
        cached_input_tokens=500,
        output_tokens=200,
        reasoning_tokens=100,
    )
    assert cost.total_micro_usd == 3325
    assert cost.cached_input_micro_usd == 125
    assert format_usd(cost.total_micro_usd) == "$0.003325"


def test_zero_and_rounding_boundaries() -> None:
    assert calculate_cost(0, 0, 0, 0, 0).total_micro_usd == 0
    assert calculate_cost(0, 1, 0, 0, 0).cached_input_micro_usd == 0
    assert calculate_cost(0, 2, 0, 0, 0).cached_input_micro_usd == 1
    assert calculate_cost(0, 3, 0, 0, 0).cached_input_micro_usd == 1
    assert calculate_cost(0, 4, 0, 0, 0).cached_input_micro_usd == 1
