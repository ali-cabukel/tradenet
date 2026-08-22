from pathlib import Path

from tradenet.cli import write_countries_csv


def test_write_countries_csv_includes_every_row(tmp_path: Path) -> None:
    rows = [
        {"id": "276", "isoCode": "DEU", "isoCode2": "DE", "text": "Germany"},
        {"id": "792", "isoCode": "TUR", "isoCode2": "TR", "text": "Türkiye"},
    ]
    path = tmp_path / "nested" / "countries.csv"

    write_countries_csv(path, rows)

    content = path.read_text(encoding="utf-8")
    assert content.splitlines()[0] == "code,iso3,iso2,name"
    assert "276,DEU,DE,Germany" in content
    assert "792,TUR,TR,Türkiye" in content
