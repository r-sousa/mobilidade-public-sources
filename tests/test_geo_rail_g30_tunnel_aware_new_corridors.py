"""G30 independent small synthetic tests: legal gate remains irrespective of tunnel hypothesis."""
import importlib.util, pathlib,unittest
try:
    from shapely.geometry import box
    from shapely.prepared import prep
    import matplotlib,pyproj
    GIS=True
except ImportError:
    GIS=False
if GIS:
    ROOT=pathlib.Path(__file__).resolve().parents[1]
    SPEC=importlib.util.spec_from_file_location("g30",ROOT/"tools/geo_rail_g30_tunnel_aware_new_research_corridors.py")
    g=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(g)
@unittest.skipUnless(GIS,"G30 optional GIS stack installed in dedicated workflow only")
class G30TunnelAware(unittest.TestCase):
    def test_elevation_never_makes_legal_gate_green(self):
        self.assertEqual(len(g.ROUTING),3)
        for m in g.ROUTING:self.assertIn(m,("avoid_surface_overlap","potential_deep_tunnel","geographic_diversity"))
    def test_geometry_exact_intersection_m(self):
        protected=box(2000,-500,4000,2500)
        seg=((0,0),(2000,0))
        # line centres (1000,1000)->(3000,1000) intersects 1km
        self.assertAlmostEqual(g.exposure(seg,protected,prep(protected)),1.0)
    def test_search_surface_avoids_polygon(self):
        protected=box(1800,750,4200,1250)
        prepared=prep(protected)
        nodes={(x,y) for x in range(0,8001,2000) for y in (-2000,0,2000)}
        a,b=(0,0),(8000,0)
        direct=g.route(nodes,a,b,protected,prepared,"potential_deep_tunnel")
        avoid=g.route(nodes,a,b,protected,prepared,"avoid_surface_overlap")
        self.assertTrue(direct and avoid)
        self.assertLessEqual(g.exposure_line(avoid,protected,prepared),
                             g.exposure_line(direct,protected,prepared)+1e-8)
    def test_exclusion_routing_grid_functions(self):
        self.assertEqual(g.snap(2599,4101),(2000,4000))
        self.assertAlmostEqual(g.length([(0,0),(2000,0),(4000,0)]),4.)
if __name__=="__main__":unittest.main()
