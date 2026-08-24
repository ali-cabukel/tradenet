"""Export collected trade flows for Neo4j bulk import."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

from rich.console import Console

from tradenet.collectors.trade import load_trade_flows
from tradenet.models import TradeFlow

console = Console()


class AggregatedTrade(NamedTuple):
    start_iso: str
    end_iso: str
    year: int
    supply_category: str
    trade_value_usd: float
    net_weight_kg: float
    flow_count: int


def export_neo4j(
    *,
    input_path: Path,
    output_dir: Path,
    aggregate: bool = False,
) -> Path:
    """Write country nodes and TRADES_WITH relationships as CSV files."""

    flows = load_trade_flows(input_path)
    if not flows:
        raise ValueError(f"No trade flows found in {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    countries_path = output_dir / "nodes_countries.csv"
    categories_path = output_dir / "nodes_categories.csv"
    flows_path = output_dir / "rels_trades_with.csv"

    countries = _collect_countries(flows)
    categories = _collect_categories(flows)

    _write_countries(countries_path, countries)
    _write_categories(categories_path, categories)
    if aggregate:
        aggregated = aggregate_relationships(flows)
        _write_aggregated_relationships(flows_path, aggregated)
        console.print(
            f"[green]Aggregated {len(flows)} flows into {len(aggregated)} relationships "
            "(from, to, category, year).[/green]"
        )
    else:
        _write_relationships(flows_path, flows)

    console.print(
        "[green]Neo4j import files written:[/green]\n"
        f"  countries: {countries_path}\n"
        f"  categories: {categories_path}\n"
        f"  relationships: {flows_path}"
    )
    return output_dir


def _collect_countries(flows: list[TradeFlow]) -> dict[str, str | None]:
    countries: dict[str, str | None] = {}
    for flow in flows:
        countries.setdefault(flow.reporter_iso, flow.reporter_name)
        countries.setdefault(flow.partner_iso, flow.partner_name)
    return countries


def _collect_categories(flows: list[TradeFlow]) -> dict[str, str]:
    return {flow.supply_category: flow.supply_category.replace("_", " ").title() for flow in flows}


def _write_countries(path: Path, countries: dict[str, str | None]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["countryId:ID(Country)", "iso3", "name"])
        for iso3, name in sorted(countries.items()):
            writer.writerow([iso3, iso3, name or iso3])


def _write_categories(path: Path, categories: dict[str, str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["categoryId:ID(Category)", "id", "name"])
        for category_id, name in sorted(categories.items()):
            writer.writerow([category_id, category_id, name])


def aggregate_relationships(flows: list[TradeFlow]) -> list[AggregatedTrade]:
    """Collapse commodity-level flows into from/to/category/year sums."""

    totals: dict[tuple[str, str, int, str], list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    for flow in flows:
        start_id, end_id = _relationship_endpoints(flow)
        key = (start_id, end_id, flow.year, flow.supply_category)
        bucket = totals[key]
        bucket[0] += flow.trade_value_usd or 0.0
        bucket[1] += flow.net_weight_kg or 0.0
        bucket[2] += 1

    return [
        AggregatedTrade(
            start_iso=start_iso,
            end_iso=end_iso,
            year=year,
            supply_category=category,
            trade_value_usd=value,
            net_weight_kg=weight,
            flow_count=int(count),
        )
        for (start_iso, end_iso, year, category), (value, weight, count) in sorted(
            totals.items()
        )
    ]


def _write_aggregated_relationships(path: Path, rows: list[AggregatedTrade]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "fromIso",
                "toIso",
                "year",
                "supplyCategory",
                "tradeValueUsd",
                "netWeightKg",
                "flowCount",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.start_iso,
                    row.end_iso,
                    row.year,
                    row.supply_category,
                    row.trade_value_usd,
                    row.net_weight_kg,
                    row.flow_count,
                ]
            )


def _write_relationships(path: Path, flows: list[TradeFlow]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                ":START_ID(Country)",
                ":END_ID(Country)",
                ":TYPE",
                "flowId",
                "year",
                "flow",
                "supplyCategory",
                "commodityCode",
                "commodityDescription",
                "tradeValueUsd",
                "netWeightKg",
                "quantity",
                "quantityUnit",
            ]
        )
        for flow in flows:
            start_id, end_id = _relationship_endpoints(flow)
            writer.writerow(
                [
                    start_id,
                    end_id,
                    "TRADES_WITH",
                    flow.flow_id,
                    flow.year,
                    flow.flow,
                    flow.supply_category,
                    flow.commodity_code,
                    flow.commodity_description or "",
                    flow.trade_value_usd if flow.trade_value_usd is not None else "",
                    flow.net_weight_kg if flow.net_weight_kg is not None else "",
                    flow.quantity if flow.quantity is not None else "",
                    flow.quantity_unit or "",
                ]
            )


def _relationship_endpoints(flow: TradeFlow) -> tuple[str, str]:
    if flow.flow == "export":
        return flow.reporter_iso, flow.partner_iso
    return flow.partner_iso, flow.reporter_iso
