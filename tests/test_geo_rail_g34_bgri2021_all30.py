"""G34 census 2021 full portfolio QA, no inference of rail demand."""
import unittest,importlib.util,pathlib
try:
    import shapely,pyproj,numpy,matplotlib
    GIS=True
except ImportError:GIS=False
if GIS:
    p=pathlib.Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location("g34",p/"tools/geo_rail_g34_bgri2021_census_all30.py")
    g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(GIS,"G34 GIS stack only in dedicated runner")
class G34FullCensusContracts(unittest.TestCase):
    def source(self):
        rows=[]
        for a in (1,2,3):
            for b in (1,2,3):
                for c in (1,2,3):
                    for market in g.CITY:
                        rows.append({"option_id":f"P{a}-{b}-{c}","urban_key":market,
                            "2021_population_with_real_network_catchment":None})
        for name in ("avoid_surface_overlap","potential_deep_tunnel","geographic_diversity"):
            for market in g.CITY:
                rows.append({"option_id":"G30-"+name,"urban_key":market,
                    "2021_population_with_real_network_catchment":None})
        return {"mission":"MN-GEO-RAIL-001","G10":27,"G30":3,
                "road_network_source_receipts":[{}]*6,"PIC_UNRESOLVED":True,
                "new_DGT_tiles":0,"no_Fxx_or_site":True,
                "six_city_all_180_records":rows}
    def test_30_times_six_valid(self):
        self.assertEqual(len(g.validate(self.source())),180)
    def test_all_30_must_be_preserved(self):
        data=self.source();data["six_city_all_180_records"].pop()
        with self.assertRaisesRegex(ValueError,"30x6|unrepeated"):
            g.validate(data)
    def test_no_census_imputation_from_G17_only_three_options(self):
        data=self.source()
        data["six_city_all_180_records"][0]["2021_population_with_real_network_catchment"]=0
        with self.assertRaisesRegex(ValueError,"old_census_not_uniform"):
            g.validate(data)
    def test_2021_demography_fields_source_mapping(self):
        d={"centroid_or_interior_point_population_counts":{"N_INDIVIDUOS":200,"N_INDIVIDUOS_65_OU_MAIS":30},
           "area_weighted_uniform_within_subsection_population_estimates":{"N_INDIVIDUOS":170},
           "original_subsections_intersecting_area":4,
           "missing_census_field_observations":2,"invalid_original_geometries_skipped":0}
        mapped=g.source_census_record(d)
        self.assertEqual(mapped["residents_2021_representative_subsection"],200)
        self.assertEqual(mapped["missing_census_field_observations_not_imputed"],2)
    def test_only_5_and_10km_not_road_isochrones(self):
        self.assertEqual(g.RADII,(5000,10000))
if __name__=="__main__":unittest.main()
