#!/usr/bin/env python3
"""Reverse DCF: solve market-implied assumptions with the forward DCF."""

from __future__ import annotations

from copy import deepcopy

from dcf import (
    integer,
    number,
    object_value,
    run_cli,
    skip_reason,
    validate_units,
    value_scenario,
)

FLAT_PRICE_REL_TOLERANCE = 1e-12


def stage_indices(scenario: dict, stage: str) -> list[int]:
    if stage not in ("growth", "transition"):
        raise ValueError("stage must be growth or transition")
    indices = [
        index for index, row in enumerate(scenario["forecast"]) if row["stage"] == stage
    ]
    if not indices:
        raise ValueError(f"No forecast rows in stage {stage}")
    return indices


def apply_variable(scenario: dict, config: dict, value: float) -> dict:
    """Apply the selected variable, preserving transition and investment rules."""
    adjusted_scenario = deepcopy(scenario)
    variable = config["variable"]
    if variable == "terminal_margin":
        adjusted_scenario["terminal_margin"] = value
        return adjusted_scenario

    if variable == "operating_margin":
        for index in stage_indices(scenario, config["stage"]):
            adjusted_scenario["forecast"][index]["ebit_margin"] = value
        return adjusted_scenario

    if variable not in ("revenue_growth", "growth_years"):
        raise ValueError(
            "variable must be terminal_margin, operating_margin, "
            "revenue_growth or growth_years"
        )
    reinvestment = object_value(config["reinvestment"], "reinvestment")
    for key in ("capex", "da"):
        if reinvestment[key] not in ("fixed", "revenue_ratio"):
            raise ValueError(f"reinvestment.{key} must be fixed or revenue_ratio")
    number(scenario["incremental_nwc_ratio"], "incremental_nwc_ratio")

    def rebuild_year(template: dict, revenue: float, year: int) -> dict:
        row = deepcopy(template)
        row.update(year=year, revenue=revenue)
        for key in ("capex", "da"):
            if reinvestment[key] == "revenue_ratio":
                if template["revenue"] <= 0:
                    raise ValueError(
                        "Revenue-ratio investment requires positive template revenue"
                    )
                row[key] = template[key] * revenue / template["revenue"]
        row.pop("delta_nwc", None)
        return row

    original_forecast = scenario["forecast"]
    if variable == "revenue_growth":
        number(value, "revenue_growth")
        if value <= -1:
            raise ValueError("Revenue growth must exceed -100%")
        selected = stage_indices(scenario, config["stage"])
        previous_revenue = scenario["base_annual_revenue"]
        for index, template in enumerate(original_forecast):
            if index in selected:
                revenue = previous_revenue * (1 + value)
            elif index > selected[-1]:
                previous_template_revenue = original_forecast[index - 1]["revenue"]
                if previous_template_revenue <= 0:
                    raise ValueError("Cannot propagate growth ratios from zero revenue")
                revenue = (
                    previous_revenue * template["revenue"] / previous_template_revenue
                )
            else:
                revenue = template["revenue"]
            adjusted_scenario["forecast"][index] = rebuild_year(
                template, revenue, template["year"]
            )
            previous_revenue = revenue
        return adjusted_scenario

    growth_years = integer(value, "growth_years")
    growth_rows = [row for row in original_forecast if row["stage"] == "growth"]
    transition_rows = [row for row in original_forecast if row["stage"] == "transition"]
    if not growth_rows:
        raise ValueError("growth_years requires a growth-stage template")
    extension_growth = 0.0
    if growth_years > len(growth_rows):
        extension_growth = number(config["extension_growth"], "extension_growth")
        if extension_growth <= -1:
            raise ValueError("extension_growth must exceed -100%")
    rebuilt = []
    previous_revenue = scenario["base_annual_revenue"]
    start_year = original_forecast[0]["year"]
    for index in range(growth_years):
        template = growth_rows[min(index, len(growth_rows) - 1)]
        if index < len(growth_rows):
            revenue = template["revenue"]
        else:
            revenue = previous_revenue * (1 + extension_growth)
        rebuilt.append(rebuild_year(template, revenue, start_year + len(rebuilt)))
        previous_revenue = revenue

    previous_template_revenue = growth_rows[-1]["revenue"]
    for template in transition_rows:
        if previous_template_revenue <= 0:
            raise ValueError(
                "Transition growth ratios require positive preceding revenue"
            )
        revenue = previous_revenue * template["revenue"] / previous_template_revenue
        rebuilt.append(rebuild_year(template, revenue, start_year + len(rebuilt)))
        previous_revenue = revenue
        previous_template_revenue = template["revenue"]
    if not rebuilt:
        raise ValueError("At least one explicit forecast year must remain")
    adjusted_scenario["forecast"] = rebuilt
    return adjusted_scenario


def calculate(data: dict) -> dict:
    validate_units(data)
    config = object_value(data.get("reverse_dcf", {}), "reverse_dcf")
    reason = skip_reason(config)
    if not config or reason:
        return dict(status="not_applicable", reason=reason or "未提供反推变量与范围。")
    scenario_name = config.get("scenario", "base")
    scenarios = object_value(data["scenarios"], "scenarios")
    scenario = object_value(scenarios[scenario_name], "scenario")
    reason = skip_reason(scenario)
    if reason:
        return dict(status="not_applicable", reason=reason)

    base = value_scenario(data, scenario)
    target = number(data["market_price"], "market_price", 0)
    if target == 0:
        raise ValueError("market_price must be positive")
    lower = number(config["lower"], "reverse.lower")
    upper = number(config["upper"], "reverse.upper")
    if lower >= upper:
        raise ValueError("reverse.lower must be less than upper")
    tolerance = number(config.get("price_tolerance", 0.01), "price_tolerance", 0)
    if tolerance == 0:
        raise ValueError("price_tolerance must be positive")
    variable = config["variable"]
    if variable in ("operating_margin", "revenue_growth"):
        indices = stage_indices(scenario, config["stage"])
        scope = dict(
            stage=config["stage"],
            years=[scenario["forecast"][index]["year"] for index in indices],
        )
        if variable == "operating_margin":
            base_value = [
                scenario["forecast"][index]["ebit_margin"] for index in indices
            ]
        else:
            base_revenue = (
                scenario["base_annual_revenue"]
                if indices[0] == 0
                else scenario["forecast"][indices[0] - 1]["revenue"]
            )
            if base_revenue <= 0:
                raise ValueError("Revenue growth requires positive starting revenue")
            base_value = (
                scenario["forecast"][indices[-1]]["revenue"] / base_revenue
            ) ** (1 / len(indices)) - 1
    elif variable == "growth_years":
        base_value = sum(1 for row in scenario["forecast"] if row["stage"] == "growth")
        scope = dict(stage="growth", transition="preserve annual transition template")
    elif variable == "terminal_margin":
        base_value = scenario["terminal_margin"]
        scope = dict(stage="terminal", first_year=scenario["forecast"][-1]["year"] + 1)
    else:
        raise ValueError("Unsupported reverse variable")

    metadata = dict(
        variable=variable,
        scope=scope,
        base_value=base_value,
        market_price=target,
        market_ev=target * data["bridge"]["shares"] - base["net_financial"],
        lower=lower,
        upper=upper,
        price_tolerance=tolerance,
        fixed_parameters=dict(
            scenario=scenario_name,
            wacc=base["wacc"],
            terminal_growth=base["terminal_growth"],
            terminal_roic=base["terminal_roic"],
        ),
        reinvestment=config.get("reinvestment"),
    )

    def evaluate(value: float) -> dict:
        result = value_scenario(data, apply_variable(scenario, config, value))
        return dict(
            value=value,
            price=result["price"],
            price_error=result["price"] - target,
            valuation=result,
        )

    def finish(candidate: dict) -> dict:
        return dict(
            status="ok",
            **metadata,
            implied_value=candidate["value"],
            price=candidate["price"],
            price_error=candidate["price_error"],
            valuation=candidate["valuation"],
        )

    if variable == "growth_years":
        lower_years = integer(lower, "lower")
        upper_years = integer(upper, "upper")
        if upper_years > 100:
            raise ValueError(
                "growth_years search supports at most 100 explicit growth years"
            )
        candidates = [evaluate(years) for years in range(lower_years, upper_years + 1)]
        matches = [
            candidate
            for candidate in candidates
            if abs(candidate["price_error"]) <= tolerance
        ]
        if len(matches) == 1:
            return finish(matches[0])
        summary = [
            dict(
                years=candidate["value"],
                price=candidate["price"],
                price_error=candidate["price_error"],
            )
            for candidate in candidates
        ]
        if matches:
            return dict(
                status="multiple_solutions",
                **metadata,
                candidates=summary,
                reason="多个离散年数可在声明精度内支持现价。",
            )
        intervals = [
            [left["value"], right["value"]]
            for left, right in zip(candidates, candidates[1:])
            if left["price_error"] * right["price_error"] < 0
        ]
        return dict(
            status="bracketed" if intervals else "outside_search_range",
            **metadata,
            candidates=summary,
            year_intervals=intervals,
            reason="列出相邻年数的价格，不插造精确持续年限。"
            if intervals
            else "所列年数未能支持现价。",
        )

    search_steps = integer(config.get("search_steps", 32), "search_steps", 2)
    max_iterations = integer(config.get("max_iterations", 100), "max_iterations", 1)
    samples = [
        evaluate(lower + (upper - lower) * index / search_steps)
        for index in range(search_steps + 1)
    ]
    # A flat price function cannot identify a unique operating assumption.
    spread = max(candidate["price"] for candidate in samples) - min(
        candidate["price"] for candidate in samples
    )
    if (
        spread <= FLAT_PRICE_REL_TOLERANCE * max(1, abs(target))
        and abs(samples[0]["price_error"]) <= tolerance
    ):
        return dict(
            status="multiple_solutions",
            **metadata,
            reason="搜索范围内价格不随参数有效变化，无法识别唯一隐含值。",
        )
    # Merge adjacent in-tolerance samples into one candidate root.
    roots = []
    previous_match = False
    for candidate in samples:
        matched = abs(candidate["price_error"]) <= tolerance
        if matched and not previous_match:
            roots.append(candidate)
        elif matched and abs(candidate["price_error"]) < abs(roots[-1]["price_error"]):
            roots[-1] = candidate
        previous_match = matched
    has_unconverged_interval = False
    for left, right in zip(samples, samples[1:]):
        if (
            abs(left["price_error"]) <= tolerance
            or abs(right["price_error"]) <= tolerance
        ):
            continue
        if left["price_error"] * right["price_error"] >= 0:
            continue
        converged = False
        for _ in range(max_iterations):
            midpoint = evaluate((left["value"] + right["value"]) / 2)
            if abs(midpoint["price_error"]) <= tolerance:
                roots.append(midpoint)
                converged = True
                break
            if left["price_error"] * midpoint["price_error"] < 0:
                right = midpoint
            else:
                left = midpoint
        if not converged:
            has_unconverged_interval = True

    if len(roots) == 1 and not has_unconverged_interval:
        return finish(roots[0])
    if roots:
        return dict(
            status="multiple_solutions" if len(roots) > 1 else "not_converged",
            **metadata,
            solutions=[
                dict(
                    value=candidate["value"],
                    price=candidate["price"],
                    price_error=candidate["price_error"],
                )
                for candidate in roots
            ],
            reason="请检查多解或尚未收敛的区间，不将结果视为唯一隐含要求。",
        )
    return dict(
        status="not_converged" if has_unconverged_interval else "outside_search_range",
        **metadata,
        tested_price_range=[
            min(candidate["price"] for candidate in samples),
            max(candidate["price"] for candidate in samples),
        ],
        reason="给定搜索范围与采样精度内未得到解，不代表模型在所有范围均无解。",
    )


if __name__ == "__main__":
    run_cli(calculate, __doc__)
