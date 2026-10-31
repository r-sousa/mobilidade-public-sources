"""G3 source-only graph tests. Synthetic arrays are tests, never evidence."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import geo_rail_g3_continuity_open_dsm_sources as m
class TestGrid(unittest.TestCase):
 def test_four_neighbor_and_slope_switch(self):
  coords=[(0,0),(2000,0),(4000,0),(0,2000),(2000,2000),(4000,2000)]
  nodes={z:{"surface_robust_relief_m":10 if z[1]==2000 else 200,
       "surface_median_m":500,"euclidean_mapped_local_road_m":100} for z in coords}
  self.assertEqual(len(m.shortest(nodes,(0,0),(4000,0),"short")[0]),3)
  self.assertEqual(m.shortest(nodes,(0,0),(4000,0),"terrain")[0][1],(0,2000))
 def test_catalogue_four_original_ids_required(self):
  cat={}
  for x in (200,201):
   for y in (301,302):
    cat[x,y]={"id":f"MDT-2m-{x:03d}{y:03d}-07-2024"}
  self.assertEqual(len(m.cell_ids(cat,0,0)),4)
  del cat[201,302]
  self.assertIsNone(m.cell_ids(cat,0,0))
 def test_link_endpoints_and_no_sanabria(self):
  self.assertEqual(len(m.LINKS),5)
  self.assertEqual(set(m.EXISTING),{"Vila Real","Bragança"})
  self.assertNotIn("sanabria",str(m.LINKS).lower())
  self.assertTrue(all(v[0]%2000==0 and v[1]%2000==0 for l in m.LINKS for v in l[1:3]))
 def test_bad_mode_refused(self):
  nodes={(0,0):{"surface_robust_relief_m":4,"surface_median_m":1,"euclidean_mapped_local_road_m":0},
         (2000,0):{"surface_robust_relief_m":4,"surface_median_m":1,"euclidean_mapped_local_road_m":0}}
  with self.assertRaises(ValueError):m.shortest(nodes,(0,0),(2000,0),"rail_engineering")
if __name__=="__main__":unittest.main()
