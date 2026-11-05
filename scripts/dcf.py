#!/usr/bin/env python3
"""FCFF DCF: explicit annual forecasts, optional stub, terminal value and bridge."""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

UNITS = {"money": "亿元", "shares": "亿股", "price": "元/股", "eps": "元/股"}


def object_value(value: object, name: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{name}: expected a JSON object")
    return value


def array_value(value: object, name: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{name}: expected a JSON array")
    return value


def skip_reason(config: dict) -> str | None:
    reason = config.get("not_applicable_reason")
    if reason is not None and (not isinstance(reason, str) or not reason.strip()):
        raise ValueError("not_applicable_reason must be a non-empty string")
    return reason


def number(
    value: object,
    name: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError(f"{name}: expected a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name}: must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name}: must be <= {maximum}")
    return value


def integer(value: object, name: str, minimum: int = 0) -> int:
    number(value, name, minimum)
    if int(value) != value:
        raise ValueError(f"{name}: expected an integer")
    return int(value)


def validate_units(data: dict) -> None:
    object_value(data, "input")
    if data.get("currency") != "CNY" or data.get("units") != UNITS:
        raise ValueError(f"Use currency=CNY and units={UNITS}")


def check_period(period: dict, name: str) -> None:
    object_value(period, name)
    for key in ("revenue", "da", "capex"):
        number(period[key], f"{name}.{key}", 0)
    number(period["ebit_margin"], f"{name}.ebit_margin")
    number(period["tax_rate"], f"{name}.tax_rate", 0, 1)
    if "delta_nwc" in period:
        number(period["delta_nwc"], f"{name}.delta_nwc")


def value_scenario(
    data: dict,
    scenario: dict,
    *,
    wacc: float | None = None,
    terminal_growth: float | None = None,
    terminal_margin: float | None = None,
    capex_multiplier: float = 1.0,
) -> dict:
    """Discount future FCFF on ACT/365 dates and bridge EV to equity."""
    validate_units(data)
    object_value(scenario, "scenario")
    wacc = number(scenario["wacc"] if wacc is None else wacc, "wacc", 0)
    terminal_growth = number(
        scenario["terminal_growth"] if terminal_growth is None else terminal_growth,
        "terminal_growth",
        0,
    )
    terminal_margin = number(
        scenario["terminal_margin"] if terminal_margin is None else terminal_margin,
        "terminal_margin",
    )
    terminal_roic = number(scenario["terminal_roic"], "terminal_roic", 0)
    terminal_tax_rate = number(scenario["terminal_tax_rate"], "terminal_tax_rate", 0, 1)
    number(capex_multiplier, "capex_multiplier", 0)
    if terminal_growth >= wacc or terminal_roic <= terminal_growth:
        raise ValueError("Require 0 <= g < WACC and terminal ROIC > g")

    valuation_date = date.fromisoformat(data["valuation_date"])
    balance_date = date.fromisoformat(data["balance_date"])
    if balance_date > valuation_date:
        raise ValueError("balance_date must not follow valuation_date")

    bridge = object_value(data["bridge"], "bridge")
    shares = number(bridge["shares"], "bridge.shares", 0)
    if shares == 0:
        raise ValueError("bridge.shares must be positive")
    for key in (
        "cash_equivalents",
        "operating_cash",
        "nonoperating_financial_assets",
        "other_claims",
    ):
        number(bridge[key], f"bridge.{key}", 0)
    debt_components = object_value(bridge["debt_components"], "bridge.debt_components")
    debt = math.fsum(
        number(amount, f"debt.{name}", 0) for name, amount in debt_components.items()
    )
    net_financial_anchor = (
        bridge["cash_equivalents"]
        - bridge["operating_cash"]
        + bridge["nonoperating_financial_assets"]
        - debt
        - bridge["other_claims"]
    )

    adjustments = array_value(data.get("bridge_adjustments", []), "bridge_adjustments")
    for item in adjustments:
        object_value(item, "bridge_adjustment")
        if not item.get("reason"):
            raise ValueError("Every bridge adjustment needs a reason")
    bridge_roll = math.fsum(
        number(adjustment["amount"], "bridge_adjustment.amount")
        for adjustment in adjustments
    )
    rows = []

    def append_cash_flow(
        period: str,
        end_date: date,
        revenue: float,
        ebit_margin: float,
        tax_rate: float,
        da: float,
        capex: float,
        delta_nwc: float,
        fraction: float = 1.0,
        stage: str | None = None,
    ) -> None:
        nopat = revenue * ebit_margin * (1 - tax_rate)
        fcff = nopat + da - capex - delta_nwc
        discount_years = (end_date - valuation_date).days / 365.0
        if discount_years <= 0:
            raise ValueError("Only cash flows after valuation_date may enter EV")
        discount_factor = (1 + wacc) ** -discount_years
        rows.append(
            dict(
                period=period,
                end=end_date.isoformat(),
                stage=stage,
                revenue=revenue,
                ebit_margin=ebit_margin,
                tax_rate=tax_rate,
                nopat=nopat,
                da=da,
                capex=capex,
                delta_nwc=delta_nwc,
                fcff=fcff,
                years=discount_years,
                discount_factor=discount_factor,
                pv=fcff * discount_factor,
                period_fraction=fraction,
            )
        )

    stub = scenario.get("stub")
    full_stub_fcff = None
    if stub is not None:
        check_period(stub, "stub")
        number(stub["delta_nwc"], "stub.delta_nwc")
        stub_end_date = date.fromisoformat(stub["end"])
        if stub_end_date != date(valuation_date.year, 12, 31):
            raise ValueError("stub.end must be the valuation year's December 31")
        allocation = stub["allocation"]
        if allocation == "uniform_days":
            total_days = (stub_end_date - balance_date).days
            if total_days <= 0 or not balance_date <= valuation_date <= stub_end_date:
                raise ValueError("Invalid stub dates")
            elapsed_fraction = (valuation_date - balance_date).days / total_days
        elif allocation == "remaining":
            elapsed_fraction = 0.0
        else:
            raise ValueError("stub.allocation must be uniform_days or remaining")
        full_stub_fcff = (
            stub["revenue"] * stub["ebit_margin"] * (1 - stub["tax_rate"])
            + stub["da"]
            - stub["capex"]
            - stub["delta_nwc"]
        )
        bridge_mode = stub["bridge_roll"]
        if bridge_mode == "uniform_fcff":
            if allocation != "uniform_days" or adjustments:
                raise ValueError(
                    "uniform_fcff requires uniform_days "
                    "and no explicit bridge adjustments"
                )
            after_tax_interest = number(
                stub["after_tax_interest"], "stub.after_tax_interest", 0
            )
            bridge_roll += (full_stub_fcff - after_tax_interest) * elapsed_fraction
        elif bridge_mode != "explicit":
            raise ValueError("stub.bridge_roll must be uniform_fcff or explicit")
        elif balance_date != valuation_date and "bridge_adjustments" not in data:
            raise ValueError(
                "Supply bridge_adjustments for the balance-to-valuation period"
            )
        remaining_fraction = 1 - elapsed_fraction
        if valuation_date < stub_end_date:
            append_cash_flow(
                f"{valuation_date + timedelta(days=1)}/{stub_end_date}",
                stub_end_date,
                stub["revenue"] * remaining_fraction,
                stub["ebit_margin"],
                stub["tax_rate"],
                stub["da"] * remaining_fraction,
                stub["capex"] * remaining_fraction * capex_multiplier,
                stub["delta_nwc"] * remaining_fraction,
                fraction=remaining_fraction,
                stage="stub",
            )
    else:
        if valuation_date != date(valuation_date.year, 12, 31):
            raise ValueError(
                "A mid-year valuation requires an explicit remaining-year stub"
            )
        if balance_date != valuation_date and "bridge_adjustments" not in data:
            raise ValueError("Supply bridge_adjustments when balance_date differs")

    forecast = array_value(scenario["forecast"], "forecast")
    if not forecast:
        raise ValueError("Supply at least one explicit forecast year")
    previous_revenue = number(scenario["base_annual_revenue"], "base_annual_revenue", 0)
    incremental_nwc_ratio = scenario.get("incremental_nwc_ratio")
    if incremental_nwc_ratio is not None:
        number(incremental_nwc_ratio, "incremental_nwc_ratio")
    previous_stage = "growth"
    for index, period in enumerate(forecast):
        object_value(period, "forecast year")
        current_year = integer(period["year"], "forecast.year", 1)
        if current_year != valuation_date.year + 1 + index:
            raise ValueError(
                "Forecast years must be consecutive, starting after the valuation year"
            )
        check_period(period, str(current_year))
        stage = period["stage"]
        if stage not in ("growth", "transition") or (
            previous_stage == "transition" and stage == "growth"
        ):
            raise ValueError("Forecast stages must progress from growth to transition")
        if "delta_nwc" in period:
            delta_nwc = period["delta_nwc"]
        elif incremental_nwc_ratio is not None:
            delta_nwc = (period["revenue"] - previous_revenue) * incremental_nwc_ratio
        else:
            raise ValueError("Supply delta_nwc or incremental_nwc_ratio")
        append_cash_flow(
            str(current_year),
            date(current_year, 12, 31),
            period["revenue"],
            period["ebit_margin"],
            period["tax_rate"],
            period["da"],
            period["capex"] * capex_multiplier,
            delta_nwc,
            stage=stage,
        )
        previous_revenue = period["revenue"]
        previous_stage = stage

    terminal_revenue = previous_revenue * (1 + terminal_growth)
    terminal_nopat = terminal_revenue * terminal_margin * (1 - terminal_tax_rate)
    terminal_reinvestment = terminal_nopat * terminal_growth / terminal_roic
    terminal_fcff = terminal_nopat - terminal_reinvestment
    terminal_value = terminal_fcff / (wacc - terminal_growth)
    terminal_pv = terminal_value * rows[-1]["discount_factor"]
    explicit_pv = math.fsum(row["pv"] for row in rows)
    ev = explicit_pv + terminal_pv
    net_financial = net_financial_anchor + bridge_roll
    equity = ev + net_financial
    return dict(
        rows=rows,
        wacc=wacc,
        terminal_growth=terminal_growth,
        terminal_roic=terminal_roic,
        terminal_margin=terminal_margin,
        terminal_revenue=terminal_revenue,
        terminal_nopat=terminal_nopat,
        terminal_reinvestment=terminal_reinvestment,
        terminal_fcff=terminal_fcff,
        terminal_value=terminal_value,
        terminal_pv=terminal_pv,
        terminal_share=terminal_pv / ev if ev else None,
        explicit_pv=explicit_pv,
        ev=ev,
        net_financial_anchor=net_financial_anchor,
        bridge_roll=bridge_roll,
        net_financial=net_financial,
        debt=debt,
        equity=equity,
        price=equity / shares,
        full_stub_fcff=full_stub_fcff,
    )


def calculate(data: dict) -> dict:
    validate_units(data)
    scenarios = object_value(data["scenarios"], "scenarios")
    if not {"bear", "base", "bull"} <= scenarios.keys():
        raise ValueError("Supply bear, base and bull scenarios")
    result = {}
    for name, scenario in scenarios.items():
        object_value(scenario, f"scenarios.{name}")
        reason = skip_reason(scenario)
        if reason:
            result[name] = dict(status="not_applicable", reason=reason)
            continue
        result[name] = dict(status="ok", **value_scenario(data, scenario))

    sensitivity = dict(wacc_growth=[], capex=[])
    if result["base"]["status"] == "ok":
        base_scenario = scenarios["base"]
        config = object_value(data.get("sensitivity", {}), "sensitivity")
        for wacc in array_value(config.get("wacc", []), "sensitivity.wacc"):
            for terminal_growth in array_value(
                config.get("growth", []), "sensitivity.growth"
            ):
                valuation = value_scenario(
                    data, base_scenario, wacc=wacc, terminal_growth=terminal_growth
                )
                sensitivity["wacc_growth"].append(
                    dict(
                        wacc=wacc,
                        growth=terminal_growth,
                        price=valuation["price"],
                    )
                )
        for multiplier in array_value(
            config.get("capex_multipliers", []), "sensitivity.capex_multipliers"
        ):
            valuation = value_scenario(data, base_scenario, capex_multiplier=multiplier)
            sensitivity["capex"].append(
                dict(
                    multiplier=multiplier,
                    scope="future_explicit_capex_cost_only",
                    price=valuation["price"],
                )
            )
    has_valuation = any(
        scenario_result["status"] == "ok" for scenario_result in result.values()
    )
    return dict(
        status="ok" if has_valuation else "not_applicable",
        valuation_date=data["valuation_date"],
        units=UNITS,
        scenarios=result,
        sensitivity=sensitivity,
    )


def run_cli(calculator: Callable[[dict], dict], description: str) -> None:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.input.resolve() == args.output.resolve() or (
            args.output.exists() and args.input.samefile(args.output)
        ):
            raise ValueError("Input and output must be different files")

        def reject_constant(value: str) -> None:
            raise ValueError(f"Non-finite JSON number: {value}")

        data = json.loads(
            args.input.read_text(encoding="utf-8"), parse_constant=reject_constant
        )
        if not isinstance(data, dict):
            raise ValueError("Input JSON must be an object")
        result = calculator(data)
        text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        args.output.write_text(text, encoding="utf-8")
    except (ValueError, KeyError, TypeError, OSError, OverflowError) as exc:
        parser.error(str(exc))
    print(f"{result['status']}: {args.output}")


if __name__ == "__main__":
    run_cli(calculate, __doc__)
