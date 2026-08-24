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
poetry run tradenet export-neo4j --aggregate
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

Default output is `data/neo4j/`:

- `nodes_countries.csv` — `(:Country {iso3, name})`
- `nodes_categories.csv` — `(:Category {id, name})`
- `rels_trades_with.csv` — `(Country)-[:TRADES_WITH]->(Country)`

Use `--aggregate` to collapse commodity-level rows into one edge per **from country, to country, category, and year**, with `sum(tradeValueUsd)`:

```bash
poetry run tradenet export-neo4j --aggregate
```

That file has columns `fromIso`, `toIso`, `year`, `supplyCategory`, `tradeValueUsd`, `netWeightKg`, `flowCount`. Year is kept so 2022 and 2025 stay separate. Omit `--aggregate` to keep one relationship per HS chapter.

Edges point from exporter to importer. Put CSVs in `data/neo4j/` (import files). `data/neo4j-data/` is Neo4j database storage (`/data`), not the CSV folder.

### Docker

From the project root:

```bash
mkdir -p data/neo4j data/neo4j-data

docker run -d --name tradenet-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -v "$PWD/data/neo4j-data:/data" \
  -v "$PWD/data/neo4j:/var/lib/neo4j/import" \
  -e NEO4J_server_memory_heap_initial__size=2G \
  -e NEO4J_server_memory_heap_max__size=4G \
  -e NEO4J_db_memory_transaction_total_max=3G \
  neo4j:latest
```

Open [http://localhost:7474](http://localhost:7474). `max__size` uses a double underscore because the setting is `max_size`. `total_max` uses a single underscore because the setting is `total.max`.

If the container is already running without the import mount, copy the CSVs in:

```bash
docker cp data/neo4j/. tradenet-neo4j:/var/lib/neo4j/import/
```

To replace an existing container:

```bash
docker stop tradenet-neo4j
docker rm tradenet-neo4j
```

Then re-run the `docker run` command above.

### Load CSV

Clear the graph if you are re-importing:

```cypher
MATCH (n)
DETACH DELETE n;
```

Then in Browser (one statement at a time). Batch relationship import so large files do not hit `db.memory.transaction.total.max`:

```cypher
LOAD CSV WITH HEADERS FROM 'file:///nodes_countries.csv' AS row
MERGE (c:Country {iso3: row.iso3})
SET c.name = row.name;
```

```cypher
LOAD CSV WITH HEADERS FROM 'file:///nodes_categories.csv' AS row
MERGE (cat:Category {id: row.id})
SET cat.name = row.name;
```

```cypher
LOAD CSV WITH HEADERS FROM 'file:///rels_trades_with.csv' AS row
CALL {
  WITH row
  MATCH (a:Country {iso3: row.fromIso})
  MATCH (b:Country {iso3: row.toIso})
  CREATE (a)-[r:TRADES_WITH {
    year: toInteger(row.year),
    supplyCategory: row.supplyCategory,
    tradeValueUsd: toFloat(row.tradeValueUsd),
    netWeightKg: toFloat(row.netWeightKg),
    flowCount: toInteger(row.flowCount)
  }]->(b)
} IN TRANSACTIONS OF 1000 ROWS;
```

The `LOAD CSV` above matches `--aggregate` output. Without `--aggregate`, relationship columns are the older per-commodity `neo4j-admin` headers.

### Example queries

```cypher
MATCH (a:Country {iso3: "DEU"})-[r:TRADES_WITH {supplyCategory: "energy"}]->(b:Country)
RETURN a.name, b.name, r.tradeValueUsd, r.year
ORDER BY r.tradeValueUsd DESC
LIMIT 20;
```

Food exported from the USA to Türkiye (Türkiye’s food imports from the USA):

```cypher
MATCH (usa:Country {iso3: "USA"})-[r:TRADES_WITH {supplyCategory: "food"}]->(tur:Country {iso3: "TUR"})
RETURN usa.name, tur.name, r.year, r.tradeValueUsd, r.flowCount
ORDER BY r.tradeValueUsd DESC;
```



## Project layout

```
src/tradenet/
├── cli.py                 # argparse CLI
├── comtrade/              # UN Comtrade API client
├── collectors/trade.py    # fetch and store flows
└── export/neo4j.py        # CSV export for graph import
```

