"""G31 GIS-only validation tests; generic public CI skips when GIS deps absent."""
import unittest,importlib.util,pathlib
try:
    import numpy as np
    import rasterio,shapely,matplotlib,pyproj,scipy
    GIS=True
except ImportError:
    GIS=False
if GIS:
    ROOT=pathlib.Path(__file__).resolve().parents[1]
    SPEC=importlib.util.spec_from_file_location("g31",ROOT/"tools/geo_rail_g31_terrain_natura_horizontal_vertical.py")
    G31=importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(G31)
@unittest.skipUnless(GIS,"Dedicated G31 Actions GIS stack required")
class G31SourceTerrainTests(unittest.TestCase):
    def test_declared_160_200_250_and_not_fixed_station_elevation(self):
        self.assertEqual(G31.SPEEDS_KMH,(160,200,250))
        self.assertEqual(G31.GRADIENTS,(18,25))
    def test_legal_site_no_labels_is_unknown_not_zero(self):
        self.assertIsNone(G31.identify_alvao_site([]))
    def test_grade_math_caps_synthetic_mountain(self):
        coord=np.array([(0.,0.),(1000.,0.),(2000.,0.)])
        z=np.array([0.,100.,0.])
        ss,h,delta=G31.profile(z,coord,25)
        self.assertTrue(np.all(np.abs(np.diff(h))<=25.001))
        self.assertGreater(max(abs(delta)),10)
        self.assertEqual(len(ss),3)
    def test_pressure_lengths_are_only_DSM_proxies(self):
        coord=np.array([(0.,0.),(1000.,0.),(2000.,0.)])
        z=np.array([0.,100.,0.])
        ss,h,delta=G31.profile(z,coord,18)
        r=G31.pressure_summary(ss,z,delta,coord,None)
        self.assertIsNone(r["Alvao_Marao_coincident_below_DSM_25m_km_NOT_tunnel"])
        self.assertTrue(r["all_absolute_DSM_proxy_lengths_not_structure_lengths"])
    def test_3km_envelope_checked_before_6km(self):
        self.assertEqual(G31.MAX_SHIFT_M,(3000.,6000.))
if __name__=="__main__":unittest.main()
