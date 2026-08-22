# tradenet

Collect bilateral import/export trade data between countries, grouped by supply type (energy, food, metals, etc.), and export it for Neo4j network visualisation.

Data is sourced from the [UN Comtrade API](https://comtradeplus.un.org/).

## Setup

```bash
cd tradenet
poetry install
cp .env.template .env
```

Register for a free API key at [UN Comtrade Developer Portal](https://comtradedeveloper.un.org) and add it to `.env`:

```env
COMTRADE_SUBSCRIPTION_KEY=your_key_here
```

Preview mode works without a key but is limited to 500 records per request.

## CLI

```bash
poetry run tradenet categories
poetry run tradenet countries --search germany
poetry run tradenet countries --csv
poetry run tradenet countries --csv data/reporters.csv

# Collect energy and food trade for Germany in 2022 (preview mode)
poetry run tradenet collect \
  --reporter DEU \
  --year 2022 \
  --category energy \
  --category food \
  --flow both \
  --preview

# Full collection with partners and Neo4j export
poetry run tradenet collect \
  --reporter USA \
  --partner DEU \
  --partner CHN \
  --year 2022 \
  --category energy \
  --flow export

poetry run tradenet export-neo4j
```



## Supply categories


| ID          | Description                                 |
| ----------- | ------------------------------------------- |
| `energy`    | Mineral fuels and oils (HS 27)              |
| `food`      | Agricultural products and food (HS 01–24)   |
| `metals`    | Base metals (HS 72–83)                      |
| `chemicals` | Chemicals, plastics, rubber (HS 28–39)      |
| `textiles`  | Textiles and apparel (HS 50–67)             |
| `machinery` | Machinery and electronics (HS 84–85, 90–92) |
| `transport` | Vehicles and transport equipment (HS 86–89) |
| `wood`      | Wood and paper products (HS 44–49)          |
| `minerals`  | Ores and mineral products (HS 25–26)        |
| `all`       | All commodities (`TOTAL`)                   |




## Neo4j import

`export-neo4j` writes CSV files. It does **not** load them into a running Neo4j instance. Restarting Neo4j will not make the data appear in Browser.

After collection it writes three files under `data/neo4j/`:

- `nodes_countries.csv` — `(:Country {iso3, name})`
- `nodes_categories.csv` — `(:Category {id, name})`
- `rels_trades_with.csv` — `(Country)-[:TRADES_WITH]->(Country)` with value, weight, year, flow, and supply category

The CSVs use `neo4j-admin` bulk-import headers. For a running Docker container, copy them into Neo4j’s import directory, then `LOAD CSV` in Browser.

```bash
docker cp data/neo4j/. <container>:/var/lib/neo4j/import/
```

If the container mounts `data/neo4j-data` as `/data`, that is database storage, not the CSV folder. Copy (or bind-mount) `data/neo4j` to `/var/lib/neo4j/import`.

```cypher
LOAD CSV WITH HEADERS FROM 'file:///nodes_countries.csv' AS row
MERGE (c:Country {iso3: row.iso3})
SET c.name = row.name;

LOAD CSV WITH HEADERS FROM 'file:///nodes_categories.csv' AS row
MERGE (cat:Category {id: row.id})
SET cat.name = row.name;

LOAD CSV FROM 'file:///rels_trades_with.csv' AS row
WITH row WHERE row[0] <> ':START_ID(Country)'
MATCH (a:Country {iso3: row[0]})
MATCH (b:Country {iso3: row[1]})
CREATE (a)-[r:TRADES_WITH {
  flowId: row[3],
  year: toInteger(row[4]),
  flow: row[5],
  supplyCategory: row[6],
  commodityCode: row[7],
  commodityDescription: row[8],
  tradeValueUsd: toFloat(row[9]),
  netWeightKg: toFloat(row[10])
}]->(b);
```

Example query after import:

```cypher
MATCH (a:Country {iso3: "DEU"})-[r:TRADES_WITH {supplyCategory: "energy"}]->(b:Country)
RETURN a.name, b.name, r.tradeValueUsd, r.year
ORDER BY r.tradeValueUsd DESC
LIMIT 20;
```



## Project layout

```
src/tradenet/
├── cli.py                 # argparse CLI
├── comtrade/              # UN Comtrade API client
├── collectors/trade.py    # fetch and store flows
└── export/neo4j.py        # CSV export for graph import
```

