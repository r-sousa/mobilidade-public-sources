#!/usr/bin/env python3
"""MN-GEO-RAIL-001 W3: non-destructive CNIG/IGN WCS capability probe.

Requests only OGC WCS GetCapabilities and records a compact, source-hashed
metadata receipt. Does not download coverage rasters or allocate any Fxx.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

ENDPOINT = "https://servicios.idee.es/wcs-inspire/mdt"
PARAMS = {"service": "WCS", "request": "GetCapabilities", "version": "2.0.1"}
MAX_XML_BYTES = 8_000_000
TIMEOUT = 35


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_wcs_capabilities(xml_bytes: bytes) -> dict:
    root = ET.fromstring(xml_bytes)
    local_root = local_name(root.tag)
    if local_root != "Capabilities":
        raise ValueError(f"unexpected OGC XML root {local_root}")
    coverage_ids = []
    for summary in root.iter():
        if local_name(summary.tag) != "CoverageSummary":
            continue
        for element in summary:
            if local_name(element.tag) in ("CoverageId", "Identifier"):
                if element.text and element.text.strip():
                    coverage_ids.append(element.text.strip())
                break
    titles = [element.text.strip() for element in root.iter()
              if local_name(element.tag) == "Title" and element.text and element.text.strip()]
    return {
        "xml_root": root.tag,
        "service_title": titles[0] if titles else None,
        "coverage_summary_count": len(coverage_ids),
        "coverage_ids": coverage_ids[:100],
        "coverage_ids_truncated": len(coverage_ids) > 100,
    }


DESCRIBE_IDS = ("Elevacion25830_25", "Elevacion25830_5")


def describe_coverage(coverage_id: str, urlopen_func=urlopen) -> dict:
    """Read <=2 MiB of WCS DescribeCoverage XML; never invoke GetCoverage."""
    if coverage_id not in DESCRIBE_IDS:
        raise ValueError("coverage not in reviewed allowlist")
    query = dict(PARAMS, request="DescribeCoverage", coverageId=coverage_id)
    url = ENDPOINT + "?" + urlencode(query)
    result = {"coverage_id": coverage_id, "describe_url": url,
              "status": "unverified", "http_status": None}
    try:
        with urlopen_func(Request(url, headers={
                "User-Agent": "MN-GEO-RAIL-001-wcs-describe/1.0"}), timeout=TIMEOUT) as response:
            result["http_status"] = response.status
            data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError("DescribeCoverage XML over byte budget")
        result["response_bytes"] = len(data)
        result["response_sha256"] = hashlib.sha256(data).hexdigest()
        root = ET.fromstring(data)
        if local_name(root.tag) != "CoverageDescriptions":
            raise ValueError(f"unexpected DescribeCoverage root {local_name(root.tag)}")
        result["status"] = "description_parsed"
        result["envelopes"] = []
        for envelope in root.iter():
            if local_name(envelope.tag) not in ("Envelope", "EnvelopeWithTimePeriod"):
                continue
            info = {"srsName": envelope.attrib.get("srsName"),
                    "axisLabels": envelope.attrib.get("axisLabels"),
                    "lowerCorner": None, "upperCorner": None}
            for child in envelope:
                if local_name(child.tag) in ("lowerCorner", "upperCorner"):
                    info[local_name(child.tag)] = (child.text or "").strip()
            result["envelopes"].append(info)
        result["grid_limits"] = []
        for item in root.iter():
            if local_name(item.tag) == "GridEnvelope":
                result["grid_limits"].append({
                    local_name(ch.tag): (ch.text or "").strip()
                    for ch in item if local_name(ch.tag) in ("low", "high")})
    except Exception as exc:
        result["status"] = "description_unverified_error"
        result["error_type"] = type(exc).__name__
        result["error_excerpt"] = str(exc)[:240]
    return result


def probe(urlopen_func=urlopen, include_descriptions=False) -> dict:
    url = ENDPOINT + "?" + urlencode(PARAMS)
    receipt = {
        "mission": "MN-GEO-RAIL-001", "worker": "W3", "stage": "ES_WCS_capabilities_only",
        "producer": "IGN/CNIG — Spain", "service_url": url,
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "status": "unverified", "http_status": None,
        "native_raster_acquired": False,
        "coverage_by_MTN_sheet_verified": False, "zamora_coverage_verified": False,
        "canonical_identity_assigned": False, "canonical_acceptance": False,
        "public_redistribution_authorized": False,
        "note": "WCS service capabilities do not by themselves validate raster footprints or available sheets.",
    }
    try:
        req = Request(url, headers={"User-Agent": "MN-GEO-RAIL-001-wcs-discovery/1.0"})
        with urlopen_func(req, timeout=TIMEOUT) as response:
            receipt["http_status"] = response.status
            receipt["content_type"] = response.headers.get("Content-Type")
            data = response.read(MAX_XML_BYTES + 1)
        receipt["response_bytes"] = len(data)
        if len(data) > MAX_XML_BYTES:
            raise ValueError("Capabilities XML exceeds maximum byte budget")
        receipt["response_sha256"] = hashlib.sha256(data).hexdigest()
        info = parse_wcs_capabilities(data)
        receipt.update(info)
        receipt["status"] = "capabilities_parsed"
        if include_descriptions:
            receipt["described_coverages"] = [describe_coverage(x) for x in DESCRIBE_IDS]
    except Exception as error:
        receipt["status"] = "capabilities_unverified_error"
        receipt["error_type"] = type(error).__name__
        receipt["error_excerpt"] = str(error)[:240]
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--describe", action="store_true", help="Read selected WCS DescribeCoverage XMLs")
    args = parser.parse_args()
    receipt = probe(include_descriptions=args.describe)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({k:receipt.get(k) for k in
                      ("status","http_status","coverage_summary_count","response_sha256","error_excerpt")}))
    if receipt["status"] != "capabilities_parsed":
        raise SystemExit("WCS_DISCOVERY_UNVERIFIED; consult persisted receipt")


if __name__ == "__main__":
    main()
