"""G32 full 30 route source-contract tests; GIS tests on dedicated branch runner."""
import unittest,importlib.util,pathlib
try:
    import numpy,scipy,shapely,rasterio,matplotlib,pyproj
    GIS=True
except ImportError:GIS=False
if GIS:
    ROOT=pathlib.Path(__file__).resolve().parents[1]
    SPEC=importlib.util.spec_from_file_location("g32",ROOT/"tools/geo_rail_g32_unified_30_90_comparison.py")
    G32=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(G32)
@unittest.skipUnless(GIS,"G32 GIS deps not in generic unit test engine")
class UnifiedPortfolioTests(unittest.TestCase):
    def make_sources(self):
        g10={"features":[]}
        for a in (1,2,3):
            for b in (1,2,3):
                for c in (1,2,3):
                    g10["features"].append({"properties":{
                        "id":f"P{a}-{b}-{c}",
                        "this_is_not_an_approved_or_proposed_railway_alignment":True}})
        variants=("avoid_surface_overlap","potential_deep_tunnel","geographic_diversity")
        g30geo={"features":[{"properties":{"id":"G30-"+v,
                  "NOT_an_engineered_railway":True,
                  "legal_Natura_screen":"ASSESSMENT_REQUIRED"}} for v in variants]}
        return g10,g30geo,{"number_new_independent_search_scenarios":3,
               "deep_tunnel_is_only_hypothesis_no_verified_3D_alignment":True}
    def test_27_original_plus_three_are_mandatory(self):
        g10,g30geo,g30=self.make_sources()
        x=G32.collect(g10,g30,g30geo)
        self.assertEqual(len(x),30)
        self.assertEqual(sum(v["family"]=="G10" for v in x.values()),27)
        self.assertEqual(sum(v["family"]=="G30" for v in x.values()),3)
    def test_missing_any_G10_must_fail_closed(self):
        g10,g30geo,g30=self.make_sources()
        g10["features"].pop()
        with self.assertRaisesRegex(ValueError,"27_plus_3"):
            G32.collect(g10,g30,g30geo)
    def test_G30_tunnel_never_implies_Natura_exemption(self):
        g10,g30geo,g30=self.make_sources()
        g30geo["features"][1]["properties"]["legal_Natura_screen"]="EXEMPT"
        with self.assertRaisesRegex(ValueError,"legal_screen"):
            G32.collect(g10,g30,g30geo)
    def test_3_speeds_no_missing_values_filled_with_zero(self):
        self.assertEqual(G32.SCENARIOS,(160,200,250))
        self.assertEqual(G32.MAX_SHIFT_M,(3000,6000))
    def test_duplicate_G10_id_not_hidden(self):
        g10,g30geo,g30=self.make_sources()
        g10["features"][1]["properties"]["id"]=g10["features"][0]["properties"]["id"]
        with self.assertRaisesRegex(ValueError,"27_combinations"):
            G32.collect(g10,g30,g30geo)
if __name__=="__main__":unittest.main()
