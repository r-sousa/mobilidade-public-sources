#!/usr/bin/env python3
"""MN-GEO-RAIL-001 / W3 — bounded, sourced Spanish regional MDT sample transect.

Five named locations, two WCS resolutions each, one 1 km² window per request.
Exploratory samples only; no route, continuous coverage, native release or Fxx.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode

from pyproj import Transformer
from geo_rail_es_wcs_sample import download_bounded, inspect

WCS = "https://servicios.idee.es/wcs-inspire/mdt"
# Places and central points from the Spanish Ministry of Culture's PARES gazetteer
# (based on INE nomenclator or government local-entity register).
SITES = (
    ("Zamora", -5.746992, 41.503780, "https://pares.cultura.gob.es/ParesBusquedas20/catalogo/autoridad/82338"),
    ("Alcanices", -6.346470, 41.699400, "https://pares.cultura.gob.es/ParesBusquedas20/catalogo/autoridad/86457"),
    ("San_Vicente_de_la_Cabeza", -6.2523947, 41.805374, "https://pares.cultura.gob.es/ParesBusquedas20/catalogo/autoridad/74631"),
    ("Vinas", -6.471160, 41.773300, "https://pares.cultura.gob.es/ParesBusquedas20/catalogo/autoridad/76577"),
    ("Puebla_de_Sanabria", -6.633500, 42.054010, "https://pares.cultura.gob.es/ParesBusquedas20/catalogo/autoridad/73858"),
)
RESOLUTIONS = (25, 5)
CRS = "EPSG:25830"


def tile_bbox_from_longlat(lon: float, lat: float, transformer) -> list[int]:
    if not (-7.1 <= lon <= -5.4 and 41.1 <= lat <= 42.3):
        raise ValueError("sample centre outside pre-approved Zamora-region safety limits")
    x, y = transformer.transform(lon, lat)
    if not all(math.isfinite(v) for v in (x, y)):
        raise ValueError("projection returned invalid coordinate")
    cx, cy = (int(round(v / 25) * 25) for v in (x, y))
    return [cx - 500, cy - 500, cx + 500, cy + 500]


def build_coverage_url(resolution: int, bbox: list[int]) -> str:
    if resolution not in RESOLUTIONS or len(bbox) != 4:
        raise ValueError("resolution/bbox not approved")
    x0, y0, x1, y1 = bbox
    if x1 - x0 != 1000 or y1 - y0 != 1000:
        raise ValueError("request must be precisely 1 km²")
    if not (150000 <= x0 <= 330000 and 4550000 <= y0 <= 4680000):
        raise ValueError("UTM bbox outside reviewed area")
    params = [
        ("service", "WCS"), ("request", "GetCoverage"), ("version", "2.0.1"),
        ("coverageId", f"Elevacion25830_{resolution}"), ("format", "image/tiff"),
        ("subset", f"x({x0},{x1})"), ("subset", f"y({y0},{y1})"),
    ]
    return WCS + "?" + urlencode(params)


def probe_sites(sites=SITES, resolutions=RESOLUTIONS) -> dict:
    transformer = Transformer.from_crs(4326, 25830, always_xy=True)
    results = []
    for name, lon, lat, reference in sites:
        bbox = tile_bbox_from_longlat(lon, lat, transformer)
        site = {
            "site_id": name, "site_lonlat": [lon, lat], "point_reference_url": reference,
            "area_bbox_epsg25830": bbox, "requested_km2_per_product": 1,
            "is_alignment_or_corridor_selection": False, "products": [],
        }
        for resolution in resolutions:
            url = build_coverage_url(resolution, bbox)
            sample = {
                "resolution_m": resolution, "coverage_id": f"Elevacion25830_{resolution}",
                "request_url": url, "status": "unverified",
                "raster_bytes_preserved": False, "canonical_acceptance": False,
            }
            try:
                with TemporaryDirectory(prefix="mn-w3-transect-") as workspace:
                    path = Path(workspace) / "native-wcs-response.bin"
                    size, digest, ctype = download_bounded(url, path)
                    raster = inspect(path)
                    expected_count = (1000 // resolution) ** 2
                    if raster["width_px"] != 1000 // resolution or raster["height_px"] != 1000 // resolution:
                        raise ValueError("WCS output differs from native requested resolution")
                    if raster["valid_cells"] != expected_count:
                        raise ValueError("NoData within sample: classify as partial, not full coverage")
                    if any(abs(a - b) > 0.01 for a, b in zip(raster["bounds_utm30"], bbox)):
                        raise ValueError("GeoTIFF extent differs from requested geographical window")
                    sample.update({"status": "validated_one_km2_sample", "response_bytes": size,
                                   "sha256_native_bytes": digest, "content_type": ctype,
                                   "raster": raster})
            except Exception as exc:
                sample.update({"status": "unverified_or_incomplete",
                               "error_class": type(exc).__name__,
                               "error_excerpt": str(exc)[:200]})
            site["products"].append(sample)
        results.append(site)
    passed = sum(p["status"] == "validated_one_km2_sample"
                 for s in results for p in s["products"])
    return {
        "mission": "MN-GEO-RAIL-001", "stage": "W3_es_five_sample_points_two_resolutions",
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "producer": "IGN/CNIG, WCS terrain data, ETRS89 UTM30",
        "method": "Five independently sourced points, 1km2 square each, MDT25 and MDT05",
        "not_spatially_contiguous": True,
        "site_count": len(results),
        "product_sample_count": sum(len(s["products"]) for s in results),
        "validated_sample_count": passed,
        "source_geography_coverage_verified_for_entire_corridor": False,
        "vertical_datum_crossborder_verified": False,
        "native_rasters_retained": 0,
        "canonical_identity_assigned": False,
        "canonical_acceptance": False,
        "approved_for_rail_alignment": False,
        "sites": results,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    receipt = probe_sites()
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    print(json.dumps({k: receipt[k] for k in ("stage", "site_count", "product_sample_count",
                      "validated_sample_count", "canonical_acceptance")}, ensure_ascii=False))
    if receipt["validated_sample_count"] != receipt["product_sample_count"]:
        raise SystemExit("Sample failures/coverage gaps recorded; review receipt.")


if __name__ == "__main__":
    main()
