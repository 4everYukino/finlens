#!/usr/bin/env python3
"""Forward P/E divided by subsequent forecast EPS CAGR, expressed in percent."""

from __future__ import annotations

from datetime import date

from dcf import integer, number, object_value, run_cli, skip_reason, validate_units


def calculate(data: dict) -> dict:
    validate_units(data)
    valuation_date = date.fromisoformat(data["valuation_date"])
    config = object_value(data.get("fpeg", {}), "fpeg")
    reason = skip_reason(config)
    if reason:
        return dict(status="not_applicable", reason=reason)

    required = ("base_year", "end_year", "base_eps", "end_eps")
    if any(key not in config for key in required):
        return dict(
            status="not_applicable",
            reason="缺少预测 EPS 或预测年份，不能以 NOPAT 代替归母 EPS。",
        )

    market_price = number(data["market_price"], "market_price", 0)
    if market_price == 0:
        raise ValueError("market_price must be positive")
    base_year = integer(config["base_year"], "fpeg.base_year", 1)
    end_year = integer(config["end_year"], "fpeg.end_year", 1)
    if end_year <= base_year:
        raise ValueError("fpeg.end_year must follow base_year")
    if base_year < valuation_date.year:
        raise ValueError(
            "FPEG base_year must be a forecast year, not a past financial year"
        )

    base_eps = number(config["base_eps"], "fpeg.base_eps")
    end_eps = number(config["end_eps"], "fpeg.end_eps")
    if base_eps <= 0 or end_eps <= 0:
        return dict(status="not_applicable", reason="预测基期及期末 EPS 必须为正。")
    eps_growth = (end_eps / base_eps) ** (1 / (end_year - base_year)) - 1
    if eps_growth <= 0:
        return dict(status="not_applicable", reason="预测 EPS 增速非正，FPEG 不适用。")

    forward_pe = market_price / base_eps
    return dict(
        status="ok",
        valuation_date=valuation_date.isoformat(),
        market_price=market_price,
        base_year=base_year,
        end_year=end_year,
        base_eps=base_eps,
        end_eps=end_eps,
        eps_cagr=eps_growth,
        forward_pe=forward_pe,
        fpeg=forward_pe / (100 * eps_growth),
    )


if __name__ == "__main__":
    run_cli(calculate, __doc__)
