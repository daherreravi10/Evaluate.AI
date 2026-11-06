"""Places parser (bus routes per stop, kinds) and the neighbourhood helpers used by the app."""
import json

import pandas as pd

from src import neighbourhood as nb
from src.exo import places


def test_places_parse_routes_and_kinds(tmp_path, monkeypatch):
    monkeypatch.setattr(places, "RAW_POI", tmp_path / "p.json")
    monkeypatch.setattr(places, "RAW_BUS", tmp_path / "b.json")
    monkeypatch.setattr(places, "OUT", tmp_path / "places.parquet")
    monkeypatch.setattr("src.exo.places.ensure", lambda: None)
    (tmp_path / "p.json").write_text(json.dumps({"elements": [
        {"type": "node", "id": 1, "lat": -33.88, "lon": 151.2, "tags": {"railway": "station", "train": "yes", "name": "Central"}},
        {"type": "way", "id": 2, "center": {"lat": -33.88, "lon": 151.2}, "tags": {"railway": "station", "name": "Central"}},
        {"type": "way", "id": 3, "center": {"lat": -33.89, "lon": 151.21}, "tags": {"amenity": "hospital", "name": "RPA"}},
        {"type": "way", "id": 4, "center": {"lat": -33.89, "lon": 151.21}, "tags": {"building": "construction", "construction": "apartments"}},
        {"type": "node", "id": 5, "lat": -33.87, "lon": 151.2, "tags": {"railway": "tram_stop", "name": "Haymarket"}}]}))
    (tmp_path / "b.json").write_text(json.dumps({"elements": [
        {"type": "relation", "id": 9, "tags": {"route": "bus", "ref": "370"}, "members": [{"type": "node", "ref": 100}]},
        {"type": "relation", "id": 8, "tags": {"route": "bus", "ref": "M50"}, "members": [{"type": "node", "ref": 100}]},
        {"type": "node", "id": 100, "lat": -33.881, "lon": 151.201, "tags": {"highway": "bus_stop", "name": "Stop A"}}]}))
    df = places.parse()
    assert (df.kind == "train").sum() == 1                    # node + area of one station kept once
    assert set(df.kind) == {"train", "hospital", "construction", "light_rail", "bus"}
    assert df[df.kind == "bus"].routes.iloc[0] == "370, M50"
    assert df[df.kind == "construction"].detail.iloc[0] == "new apartments"


def test_neighbourhood_helpers():
    pl = pd.DataFrame({"kind": ["train", "bus", "bus", "supermarket"], "name": ["Central", "A", "B", "Shop"],
                       "lat": [-33.8830, -33.8805, -33.9000, -33.8810], "lon": [151.2060, 151.2000, 151.2000, 151.2010],
                       "routes": ["", "370, M50", "999", ""], "detail": [""] * 4})
    near = nb.nearby(-33.8800, 151.2000, pl)
    n, routes = nb.bus_routes(near)
    assert n == 1 and routes == ["370", "M50"]                # the far stop is outside 400 m
    t = nb.nearest(pl, -33.8800, 151.2000, ("train",))
    assert t["name"] == "Central" and 0.6 < t["dist_km"] < 0.75 and isinstance(t["walk"], int)
    trips = nb.travel(-33.8800, 151.2000)
    assert list(trips.place)[0].startswith("Sydney CBD") and (trips.drive > 0).all()
    assert trips.transit_link.str.startswith("https://www.google.com/maps/dir/").all()
    assert nb.api_transport("G1") is None or isinstance(nb.api_transport("G1"), dict)
