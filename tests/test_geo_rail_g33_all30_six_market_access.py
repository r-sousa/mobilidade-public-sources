"""G33 test 30×6 contracts, mandatory nodes, missing road values and exact integration."""
import importlib.util,pathlib,unittest
try:
    import numpy,scipy,rasterio,shapely,pyproj,matplotlib
    GIS=True
except ImportError:GIS=False
if GIS:
    p=pathlib.Path(__file__).resolve().parents[1]
    s=importlib.util.spec_from_file_location("g33",p/"tools/geo_rail_g33_all30_six_market_access.py")
    g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
@unittest.skipUnless(GIS,"G33 GIS stack only in dedicated Actions")
class G33Contracts(unittest.TestCase):
    def sources(self):
        geo={"type":"LineString","coordinates":[(-8.67,41.23),(-8.1,41.3),(-7.7,41.35),
             (-7.2,41.5),(-6.75,41.8),(-6.1,41.7),(-5.75,41.5)]}
        g10={"features":[]}
        for a in (1,2,3):
          for b in (1,2,3):
            for c in (1,2,3):
              g10["features"].append({"properties":{"id":f"P{a}-{b}-{c}",
                  "this_is_not_an_approved_or_proposed_railway_alignment":True},
                  "geometry":geo})
        variants=("avoid_surface_overlap","potential_deep_tunnel","geographic_diversity")
        g30geo={"features":[{"properties":{"id":"G30-"+v,
             "NOT_an_engineered_railway":True,
             "legal_Natura_screen":"ASSESSMENT_REQUIRED"},"geometry":geo} for v in variants]}
        g30={"number_new_independent_search_scenarios":3,
              "deep_tunnel_is_only_hypothesis_no_verified_3D_alignment":True}
        ids=[f["properties"]["id"] for f in g10["features"]+g30geo["features"]]
        g32={"G10_count":27,"G30_count":3,"total_rows":90,
             "PIC_status":"UNRESOLVED_MUST_NOT_RANK_AS_LEGALLY_CLEARED",
             "canonical_portfolio_next_stages_all_27_G10_plus_3_G30":True,
             "rows":[{"option_id":rid,"scenario_speed_kmh":speed} for rid in ids
                    for speed in (160,200,250)]}
        return g10,g30,g30geo,g32
    def test_full_30x6_and_compulsory_nodes(self):
        items=g.validate(*self.sources())
        rows=g.build_refs(items)
        self.assertEqual(len(items),30);self.assertEqual(len(rows),180)
        self.assertEqual(sum(r["mandatory_market"] for r in rows),60)
        self.assertTrue(all(r["road_drive_minutes_to_snapped_grid_road_not_station"] is None for r in rows))
    def test_all_90_technical_and_360_hypothetical_stops(self):
        source=self.sources();items=g.validate(*source)
        rows=g.build_refs(items)
        technical,patterns=g.combine_all(items,source[3],rows)
        self.assertEqual(len(technical),90);self.assertEqual(len(patterns),360)
        self.assertTrue(all(set(g.MANDATORY).issubset(v["hypothetical_urban_stops"]) for v in patterns))
        self.assertTrue(all(v["mandatory_both_OSRM_road_targets_valid"] is False for v in technical))
    def test_missing_earlier_G10_or_speed_must_fail(self):
        g10,g30,geo,g32=self.sources();g32["rows"].pop()
        with self.assertRaisesRegex(ValueError,"original_G32|30_options"):
            g.validate(g10,g30,geo,g32)
    def test_no_2021_demography_imputed_from_G17_three_families(self):
        items=g.validate(*self.sources())
        rows=g.build_refs(items)
        self.assertTrue(all(v["2021_population_with_real_network_catchment"] is None for v in rows))
    def test_road_query_disabled_does_not_create_zero(self):
        items=g.validate(*self.sources());rows=g.build_refs(items)
        receipts=g.route_road(rows,enabled=False)
        self.assertEqual(len(receipts),6)
        self.assertTrue(all(r["road_drive_minutes_to_snapped_grid_road_not_station"] is None for r in rows))
if __name__=="__main__":unittest.main()
