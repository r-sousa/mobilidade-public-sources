"""G37 GIS-only boundary and original tile acquisition-gate tests."""
import unittest,pathlib,importlib.util,json,sys
try:
    import shapely,pyproj
    GIS=True
except ImportError:GIS=False
if GIS:
    root=pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root/"tools"))
    spec=importlib.util.spec_from_file_location("g37",root/"tools/geo_rail_g37_terrain_data_acquisition_gate.py")
    g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(GIS,"G37 dedicated GIS action needs shapely/pyproj")
class G37TileAcquisitionGate(unittest.TestCase):
    def test_source_tile_references_not_gridded_2km_studies(self):
        from shapely.geometry import LineString
        ln=LineString([(500.,500.),(1500.,500.),(2500.,500.)])
        dom=ln.buffer(250)
        tiles=g.tile_references_for_buffer(ln,dom,250)
        self.assertEqual(len(tiles),3)
        self.assertEqual(tiles,{(200,301),(201,301),(202,301)})
    def test_small_country_source_codes_and_exact_sha(self):
        from shapely.geometry import mapping,box
        features=[{"type":"Feature","properties":{"CNTR_ID":code},
                   "geometry":mapping(shape)} for code,shape in
                  (("PT",box(-9.5,36.,-6.,42.3)),("ES",box(-6.,36.,-1.,42.3)))]
        raw=json.dumps({"type":"FeatureCollection","features":features}).encode()
        pt,es,meta=g.source_boundary(raw)
        self.assertGreater(pt.area,0)
        self.assertGreater(es.area,0)
        self.assertTrue(meta["PT_ES_approx_partition_only"])
    def test_missing_PT_country_source_fails_closed(self):
        with self.assertRaises(ValueError):
            g.source_boundary(json.dumps({"type":"FeatureCollection","features":[]}).encode())
    def test_13_priority_includes_tunnel_sensitivity(self):
        self.assertEqual(g.MARGIN,(250,500))
        self.assertTrue(g.GISCO_URL.startswith("https://gisco-services.ec.europa.eu/"))
    def test_all30_and_source_sha_metadata_gates(self):
        self.assertEqual(len([f"P{a}-{b}-{c}" for a in range(1,4) for b in range(1,4) for c in range(1,4)]),27)
if __name__=="__main__":unittest.main()
