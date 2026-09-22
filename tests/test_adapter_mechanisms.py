import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from mn_public_acquisition import adapters


class FakeResponse:
    def __init__(self, *, url, obj=None, content=None, headers=None):
        self.url = url
        self._obj = obj
        self.content = (
            content
            if content is not None
            else json.dumps(obj, ensure_ascii=False).encode("utf-8")
        )
        self.headers = headers or {"content-type": "application/json"}
        self.encoding = "utf-8"

    def raise_for_status(self):
        return None

    def json(self):
        if self._obj is not None:
            return self._obj
        return json.loads(self.content.decode("utf-8"))

    def iter_content(self, size):
        yield self.content

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class SequenceSession:
    def __init__(self, responses):
        self.responses = list(responses)

    def get(self, url, **kwargs):
        if not self.responses:
            raise AssertionError("unexpected GET " + url)
        response = self.responses.pop(0)
        return response

    def post(self, url, **kwargs):
        if not self.responses:
            raise AssertionError("unexpected POST " + url)
        response = self.responses.pop(0)
        return response


class AdapterMechanismTests(unittest.TestCase):
    def _spec(self, adapter, parameters):
        return {
            "schema_version": "1.0.0",
            "source_set_id": "F999",
            "title": "test",
            "producer": "test producer",
            "product_key": "test::product",
            "adapter": adapter,
            "access": "public",
            "sink": "private",
            "cadence": "edition",
            "expected_format": "test",
            "source": {"landing_url": "https://example.test/"},
            "raw_native": {"geography": "test", "classification": "test"},
            "reuse": {
                "status": "not_verified",
                "public_redistribution_gate": "not_cleared",
            },
            "parameters": parameters,
        }

    def test_registry_exposes_new_mechanisms(self):
        for name in (
            "rest_json",
            "ckan_resource",
            "ogc_api_features",
            "atom_feed",
            "bpstat_jsonstat",
            "wfs",
            "sdmx_rest",
            "sparql_json",
            "html_table",
            "easychart_html",
            "rest_xml",
        ):
            self.assertIn(name, adapters.ADAPTERS)

    def test_legacy_xls_signature_validation(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "legacy.xls"
            p.write_bytes(bytes.fromhex("D0CF11E0A1B11AE1") + b"payload")
            adapters.validate_xls(p)

    def test_ods_structural_validation(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "table.ods"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr(
                    "mimetype",
                    "application/vnd.oasis.opendocument.spreadsheet",
                    compress_type=zipfile.ZIP_STORED,
                )
                z.writestr("content.xml", "<office:document-content/>")
            adapters.validate_ods(p)

    def test_html_table_extracts_declared_table(self):
        html = b"""<html><body><table>
        <tr><th>Municipio</th><th>Estado</th></tr>
        <tr><td>Porto</td><td>Instalado</td></tr>
        <tr><td>Braga</td><td>Planeado</td></tr>
        </table></body></html>"""
        response = FakeResponse(
            url="https://tables.example.test/list",
            content=html,
            headers={"content-type": "text/html"},
        )
        with tempfile.TemporaryDirectory() as td, patch.object(
            adapters, "session", return_value=SequenceSession([response])
        ):
            work = Path(td)
            out = adapters.html_table(
                self._spec(
                    "html_table",
                    {
                        "url": "https://tables.example.test/list",
                        "required_headers": ["Municipio", "Estado"],
                        "min_rows": 2,
                    },
                ),
                work,
            )
            payload = json.loads(
                (work / "recomposed/tables.json").read_text(encoding="utf-8")
            )
        self.assertEqual(out["validation_result"], "PASS_HTML_TABLE_EXTRACTED")
        self.assertEqual(payload["table_count"], 1)
        self.assertEqual(payload["tables"][0]["rows"][0][0], "Porto")


    def test_easychart_html_extracts_embedded_chart_payloads(self):
        html = b"""<html><body>
        <div id="easychart-chart-1"></div>
        <script>
        var container = document.getElementById('easychart-chart-1');
        window.easychart.setConfigStringified('{"chart":{"type":"column"},"title":{"text":"Taxa"}}');
        window.easychart.setData([[null,"PT","UE-27"],["2023","550","570"]]);
        </script>
        <div id="easychart-chart-2"></div>
        <script>
        var container = document.getElementById("easychart-chart-2");
        window.easychart.setConfig({"chart":{"type":"pie"}});
        window.easychart.setData([["Gasolina","100"],["Eletrico","20"]]);
        </script>
        </body></html>"""
        response = FakeResponse(
            url="https://charts.example.test/page",
            content=html,
            headers={"content-type": "text/html"},
        )
        with tempfile.TemporaryDirectory() as td, patch.object(
            adapters, "session", return_value=SequenceSession([response])
        ):
            work = Path(td)
            out = adapters.easychart_html(
                self._spec(
                    "easychart_html",
                    {
                        "url": "https://charts.example.test/page",
                        "min_charts": 2,
                        "max_charts": 2,
                    },
                ),
                work,
            )
            payload = json.loads(
                (work / "recomposed/easychart-charts.json").read_text(
                    encoding="utf-8"
                )
            )
            csv_text = (
                work / "recomposed/easychart-chart-1.csv"
            ).read_text(encoding="utf-8")

        self.assertEqual(
            out["validation_result"],
            "PASS_EASYCHART_HTML_EXTRACTED",
        )
        self.assertEqual(payload["chart_count"], 2)
        self.assertEqual(
            payload["charts"][0]["data"][1],
            ["2023", "550", "570"],
        )
        self.assertEqual(
            payload["charts"][1]["config"]["chart"]["type"],
            "pie",
        )
        self.assertIn(",PT,UE-27", csv_text)
        self.assertIn("2023,550,570", csv_text)

    def test_easychart_html_rejects_missing_inline_data_by_default(self):
        html = b"""<html><body>
        <div id="easychart-chart-1"></div>
        <script>
        var container = document.getElementById('easychart-chart-1');
        window.easychart.setConfigStringified('{"chart":{"type":"column"}}');
        window.easychart.setDataUrl('https://data.example.test/chart.csv');
        </script>
        </body></html>"""
        response = FakeResponse(
            url="https://charts.example.test/page",
            content=html,
            headers={"content-type": "text/html"},
        )
        with tempfile.TemporaryDirectory() as td, patch.object(
            adapters, "session", return_value=SequenceSession([response])
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "no embedded setData payload",
            ):
                adapters.easychart_html(
                    self._spec(
                        "easychart_html",
                        {"url": "https://charts.example.test/page"},
                    ),
                    Path(td),
                )

    def test_rest_xml_validates_root_and_namespace(self):
        xml = b"""<?xml version="1.0"?>
        <D2LogicalModel xmlns="http://datex2.eu/schema/3/common">
          <exchange/>
        </D2LogicalModel>"""
        response = FakeResponse(
            url="https://xml.example.test/datex",
            content=xml,
            headers={"content-type": "application/xml"},
        )
        with tempfile.TemporaryDirectory() as td, patch.object(
            adapters, "session", return_value=SequenceSession([response])
        ):
            out = adapters.rest_xml(
                self._spec(
                    "rest_xml",
                    {
                        "url": "https://xml.example.test/datex",
                        "expected_root": "D2LogicalModel",
                        "namespace_contains": "datex2.eu",
                    },
                ),
                Path(td),
            )
        self.assertEqual(out["validation_result"], "PASS_BOUNDED_REST_XML")

    def test_xml_zip_validation_accepts_well_formed_members(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "netex.zip"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr(
                    "publication.xml",
                    "<PublicationDelivery xmlns='http://www.netex.org.uk/netex'/>",
                )
            adapters.validate_xml_zip(p)

    def test_wfs_geojson_pages_recompose(self):
        capabilities = FakeResponse(
            url="https://geo.example.test/wfs?request=GetCapabilities",
            content=b"""<?xml version="1.0"?>
            <WFS_Capabilities xmlns="http://www.opengis.net/wfs/2.0">
              <FeatureTypeList><FeatureType><Name>ns:roads</Name></FeatureType></FeatureTypeList>
            </WFS_Capabilities>""",
            headers={"content-type": "text/xml"},
        )
        hits = FakeResponse(
            url="https://geo.example.test/wfs?resultType=hits",
            content=b"""<?xml version="1.0"?>
            <FeatureCollection xmlns="http://www.opengis.net/wfs/2.0" numberMatched="3"/>""",
            headers={"content-type": "text/xml"},
        )
        page1 = FakeResponse(
            url="https://geo.example.test/wfs?page=1",
            obj={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"id": 1}, "geometry": None},
                    {"type": "Feature", "properties": {"id": 2}, "geometry": None},
                ],
            },
        )
        page2 = FakeResponse(
            url="https://geo.example.test/wfs?page=2",
            obj={
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"id": 3}, "geometry": None}
                ],
            },
        )
        with tempfile.TemporaryDirectory() as td, patch.object(
            adapters,
            "session",
            return_value=SequenceSession([capabilities, hits, page1, page2]),
        ):
            work = Path(td)
            out = adapters.wfs(
                self._spec(
                    "wfs",
                    {
                        "service_url": "https://geo.example.test/wfs",
                        "type_name": "ns:roads",
                        "page_size": 2,
                        "output_format": "application/json",
                    },
                ),
                work,
            )
            combined = json.loads(
                (work / "recomposed/features.geojson").read_text(encoding="utf-8")
            )
        self.assertEqual(out["validation_result"], "PASS_WFS_GEOJSON_RECOMPOSED")
        self.assertEqual(len(combined["features"]), 3)

    def test_sdmx_json_accepts_bounded_native_response(self):
        response = FakeResponse(
            url="https://sdmx.example.test/data/x",
            obj={"dataSets": [{"observations": {"0": [1]}}], "structure": {}},
        )
        with tempfile.TemporaryDirectory() as td, patch.object(
            adapters, "session", return_value=SequenceSession([response])
        ):
            out = adapters.sdmx_rest(
                self._spec(
                    "sdmx_rest",
                    {
                        "data_url": "https://sdmx.example.test/data/x",
                        "format": "json",
                    },
                ),
                Path(td),
            )
        self.assertEqual(out["validation_result"], "PASS_SDMX_BOUNDED_NATIVE_RESPONSE")
        self.assertEqual(out["assets"][-1]["format"], "SDMX-JSON")

    def test_sparql_select_preserves_standard_json_results(self):
        response = FakeResponse(
            url="https://kg.example.test/sparql",
            obj={
                "head": {"vars": ["s"]},
                "results": {
                    "bindings": [
                        {"s": {"type": "uri", "value": "https://example.test/a"}}
                    ]
                },
            },
        )
        with tempfile.TemporaryDirectory() as td, patch.object(
            adapters, "session", return_value=SequenceSession([response])
        ):
            out = adapters.sparql_json(
                self._spec(
                    "sparql_json",
                    {
                        "endpoint": "https://kg.example.test/sparql",
                        "query": "SELECT ?s WHERE { ?s ?p ?o } LIMIT 10",
                    },
                ),
                Path(td),
            )
        self.assertEqual(out["validation_result"], "PASS_SPARQL_JSON_BOUNDED")

    def test_sparql_update_is_forbidden(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(RuntimeError, "forbidden"):
                adapters.sparql_json(
                    self._spec(
                        "sparql_json",
                        {
                            "endpoint": "https://kg.example.test/sparql",
                            "query": "DELETE WHERE { ?s ?p ?o }",
                        },
                    ),
                    Path(td),
                )

    def test_rest_json_preserves_bounded_response(self):
        response = FakeResponse(
            url="https://api.example.test/stops",
            obj=[{"id": 1}, {"id": 2}],
        )
        with tempfile.TemporaryDirectory() as td, patch.object(
            adapters, "session", return_value=SequenceSession([response])
        ):
            out = adapters.rest_json(
                self._spec(
                    "rest_json",
                    {
                        "url": "https://api.example.test/stops",
                        "expected_top_level": "array",
                        "min_records": 2,
                    },
                ),
                Path(td),
            )
        self.assertEqual(out["validation_result"], "PASS_BOUNDED_REST_JSON")
        self.assertEqual(len(out["assets"]), 1)

    def test_bpstat_is_bounded_one_series_per_request(self):
        response = FakeResponse(
            url="https://bpstat.bportugal.pt/data/v1/domains/1/datasets/d?series_ids=7",
            obj={"value": [1, 2], "id": ["time"], "size": [2]},
        )
        with tempfile.TemporaryDirectory() as td, patch.object(
            adapters, "session", return_value=SequenceSession([response])
        ):
            out = adapters.bpstat_jsonstat(
                self._spec(
                    "bpstat_jsonstat",
                    {"domain_id": "1", "dataset_id": "d", "series_ids": ["7"]},
                ),
                Path(td),
            )
        self.assertEqual(out["validation_result"], "PASS_BPSTAT_BOUNDED_JSONSTAT")
        self.assertEqual(len(out["assets"]), 1)

    def test_ogc_features_follows_next_link_and_recomposes(self):
        collection = FakeResponse(
            url="https://geo.example.test/collections/a",
            obj={"id": "a", "title": "A"},
        )
        page1 = FakeResponse(
            url="https://geo.example.test/collections/a/items?limit=2",
            obj={
                "type": "FeatureCollection",
                "numberMatched": 3,
                "features": [
                    {"type": "Feature", "properties": {"id": 1}, "geometry": None},
                    {"type": "Feature", "properties": {"id": 2}, "geometry": None},
                ],
                "links": [
                    {
                        "rel": "next",
                        "href": "https://geo.example.test/collections/a/items?offset=2",
                    }
                ],
            },
        )
        page2 = FakeResponse(
            url="https://geo.example.test/collections/a/items?offset=2",
            obj={
                "type": "FeatureCollection",
                "numberMatched": 3,
                "features": [
                    {"type": "Feature", "properties": {"id": 3}, "geometry": None}
                ],
                "links": [],
            },
        )
        with tempfile.TemporaryDirectory() as td, patch.object(
            adapters,
            "session",
            return_value=SequenceSession([collection, page1, page2]),
        ):
            work = Path(td)
            out = adapters.ogc_api_features(
                self._spec(
                    "ogc_api_features",
                    {"collection_url": "https://geo.example.test/collections/a"},
                ),
                work,
            )
            combined = json.loads(
                (work / "recomposed/features.geojson").read_text(encoding="utf-8")
            )
        self.assertEqual(out["validation_result"], "PASS_OGC_API_FEATURES_RECOMPOSED")
        self.assertEqual(len(combined["features"]), 3)

    def test_ckan_resource_resolves_non_gtfs_resource(self):
        package = FakeResponse(
            url="https://catalog.example.test/api/3/action/package_show?id=x",
            obj={
                "success": True,
                "result": {
                    "resources": [
                        {
                            "name": "observations",
                            "format": "JSON",
                            "url": "https://files.example.test/data.json",
                            "last_modified": "2026-01-01",
                        }
                    ]
                },
            },
        )
        resource = FakeResponse(
            url="https://files.example.test/data.json",
            obj={"rows": [1]},
        )
        with tempfile.TemporaryDirectory() as td, patch.object(
            adapters, "session", return_value=SequenceSession([package, resource])
        ):
            out = adapters.ckan_resource(
                self._spec(
                    "ckan_resource",
                    {
                        "package_show_url": "https://catalog.example.test/api/3/action/package_show?id=x",
                        "formats": ["JSON"],
                    },
                ),
                Path(td),
            )
        self.assertEqual(out["validation_result"], "PASS_CKAN_RESOURCE_SERIES")
        self.assertEqual(out["assets"][0]["name"], "ckan-package-show.json")

    def test_atom_feed_discovers_download_distribution(self):
        feed = b"""<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <link rel="alternate" href="https://geo.example.test/data.gpkg" />
          </entry>
        </feed>"""
        feed_response = FakeResponse(
            url="https://geo.example.test/feed.xml",
            content=feed,
            headers={"content-type": "application/atom+xml"},
        )
        data_response = FakeResponse(
            url="https://geo.example.test/data.gpkg",
            content=b"dummy-geopackage-bytes",
            headers={"content-type": "application/octet-stream"},
        )
        with tempfile.TemporaryDirectory() as td, patch.object(
            adapters,
            "session",
            return_value=SequenceSession([feed_response, data_response]),
        ):
            out = adapters.atom_feed(
                self._spec(
                    "atom_feed",
                    {
                        "feed_url": "https://geo.example.test/feed.xml",
                        "allowed_extensions": ["gpkg"],
                    },
                ),
                Path(td),
            )
        self.assertEqual(out["validation_result"], "PASS_ATOM_DOWNLOAD_SERIES")
        self.assertTrue(any(a["name"] == "series-manifest.json" for a in out["assets"]))


if __name__ == "__main__":
    unittest.main()
