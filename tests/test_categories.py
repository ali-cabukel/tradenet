from tradenet.comtrade.categories import comtrade_cmd_code, resolve_categories
from tradenet.export.neo4j import _relationship_endpoints, aggregate_relationships
from tradenet.models import TradeFlow


def test_resolve_categories_defaults_exclude_all():
    categories = resolve_categories(None)
    ids = {category.id for category in categories}
    assert "energy" in ids
    assert "all" not in ids


def test_comtrade_cmd_code_joins_chapters():
    categories = resolve_categories(["food"])
    assert comtrade_cmd_code(categories[0]).startswith("01,")


def test_relationship_endpoints_follow_flow_direction():
    export_flow = TradeFlow(
        year=2022,
        flow="export",
        supply_category="energy",
        commodity_code="27",
        reporter_iso="DEU",
        partner_iso="USA",
    )
    import_flow = export_flow.model_copy(update={"flow": "import"})

    assert _relationship_endpoints(export_flow) == ("DEU", "USA")
    assert _relationship_endpoints(import_flow) == ("USA", "DEU")


def test_aggregate_relationships_sums_value_by_route_and_category():
    food_export = TradeFlow(
        year=2025,
        flow="export",
        supply_category="food",
        commodity_code="01",
        reporter_iso="USA",
        partner_iso="TUR",
        trade_value_usd=10.0,
        net_weight_kg=1.0,
    )
    flows = [
        food_export,
        food_export.model_copy(
            update={"commodity_code": "02", "trade_value_usd": 15.0, "net_weight_kg": 2.0}
        ),
        food_export.model_copy(
            update={
                "supply_category": "energy",
                "commodity_code": "27",
                "trade_value_usd": 100.0,
                "net_weight_kg": 5.0,
            }
        ),
        food_export.model_copy(
            update={
                "flow": "import",
                "commodity_code": "04",
                "trade_value_usd": 7.0,
                "net_weight_kg": 0.5,
            }
        ),
    ]

    rows = aggregate_relationships(flows)

    by_key = {(row.start_iso, row.end_iso, row.supply_category): row for row in rows}
    assert len(rows) == 3
    assert by_key[("USA", "TUR", "food")].trade_value_usd == 25.0
    assert by_key[("USA", "TUR", "food")].flow_count == 2
    assert by_key[("USA", "TUR", "energy")].trade_value_usd == 100.0
    assert by_key[("TUR", "USA", "food")].trade_value_usd == 7.0
