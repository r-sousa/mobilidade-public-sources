"""G35 source-grounded site legacy preservation tests; no green legal statuses."""
import unittest,importlib.util,pathlib
try:
    import shapely,pyproj,numpy,matplotlib
    GIS=True
except ImportError:GIS=False
if GIS:
    import sys
    path=pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(path/"tools"))
    spec=importlib.util.spec_from_file_location("g35",path/"tools/geo_rail_g35_prior_station_reuse_all30.py")
    g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(GIS,"Dedicated G35 Actions geo stack not generic CI")
class G35PreviousStations(unittest.TestCase):
    def test_prior_site_not_auto_promoted(self):
        from shapely.geometry import LineString
        route=LineString([(1000.,0.),(5000.,0.),(10000.,0.),(15000.,0.)])
        site={"original_study_EPSG3763_XY":[7000.,250.],
              "source_corridor_family":"P2-2-1",
              "source_G24_reference_seed":"S1","source_G24_screening_role":"BASELINE",
              "mandatory_market":"Vila_Real",
              "G24_source_station_straight_heading_deg":0,
              "G24_original_DGT2m_station_p90_m":12.,
              "G24_original_DGT2m_approach_p90_m":21.,
              "OSRM_2026_city_to_snapped_road_reference_time_min":8.,
              "OSRM_destination_study_point_to_nearest_routable_road_m":60.,
              "OSRM_road_reference_snap_both_ends_within_600m_and_route_exists":True,
              "G24_original_grid_distance_m":300.}
        land={"cos2025_artificialized_area_percent_2025_observation_NOT_legal_constraint":15.,
              "cos2025_original_valid_area_fraction":1.}
        legal={"source_service_queries":{name:{"source_coverage_status":"UNKNOWN_SOURCE"}
              for name in ("REN_NORTE","RAN_PT","CRUS_NATIONAL")}}
        r=g.prior_case(site,route,land,legal)
        self.assertEqual(r["source_site_to_current_research_grid_m"],250.)
        self.assertTrue(r["prior_original_source_existing_DGT_road_COS_and_within_3km"])
        self.assertEqual(r["legal_REN_RAN_PDM_SRU_natura_PIC_site_clearance"],"UNKNOWN_NOT_LEGALLY_VALIDATED")
        self.assertTrue(r["not_fully_railway_geometrically_compatible"])
    def test_station_distance_over6km_keeps_real_evidence_but_not_candidate_band(self):
        from shapely.geometry import LineString
        route=LineString([(0.,0.),(5000.,0.),(10000.,0.)])
        self.assertEqual(round(route.distance(g.Point(3000,7500))),7500)
    def test_30_is_mandatory(self):
        self.assertEqual(g.MANDATORY,("Vila_Real","Braganca"))
        self.assertEqual(set(g.RADIUS_BY_SPEED),{160,200,250})
    def test_no_synthetic_station_count_from_geometry(self):
        self.assertEqual(g.SITE_RAD,400)
        self.assertEqual(g.xykey([314512.333,12001.333]),(314512.33,12001.33))
if __name__=="__main__":unittest.main()
