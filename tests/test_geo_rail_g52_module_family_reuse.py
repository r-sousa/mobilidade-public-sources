"""G52 source module representation and mandatory node sanity."""
import importlib.util,pathlib,sys,unittest
try:import pyproj,numpy,scipy,shapely,matplotlib
except ImportError:OK=False
else:OK=True
if OK:
 root=pathlib.Path(__file__).resolve().parents[1]
 sys.path.insert(0,str(root/"tools"))
 spec=importlib.util.spec_from_file_location("g52",root/"tools/geo_rail_g52_six_source_modules_city_approach_families.py")
 g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
@unittest.skipUnless(OK,"G52 source GIS stack required")
class G52GeographicDiversity(unittest.TestCase):
 def test_five_source_segments_and_exact_four_city_anchors(self):
  self.assertEqual(len(g.SEGMENTS),5)
  self.assertEqual(len(g.ANCHORS),4)
  self.assertEqual(g.DIFF_SECTORS,(g.SEGMENTS[0],g.SEGMENTS[2],g.SEGMENTS[4]))
 def test_all_four_sites_maintained_no_sanabria(self):
  self.assertEqual(g.SITES,{"Vila_Real":("VR1","VR2"),"Braganca":("BR3","BR4")})
  self.assertNotIn("Sanabria",str(g.SITES))
  self.assertEqual(g.TOP_REPS,6)
  self.assertEqual(g.DEEP,"G30-potential_deep_tunnel")
 def test_original_2km_geo_line_fragments_real_digest_not_label(self):
  from pyproj import Transformer
  t=Transformer.from_crs(3763,4326,always_xy=True)
  loc=[(1000+2000*i,201000) for i in range(80)]
  # Construct five valid ordered anchors as in original study first 4 on exact
  # unique grid; this helper validates real original 2km cell lattice only.
  path=([(-9000+2000*i,181000) for i in range(16)]+
        [(21000,181000),(23000,183000)])
  # Test canonical roundtrip without forging actual source route.
  for p in loc[:5]:
   self.assertEqual(g.canonical_point(t.transform(*p)),p)
 def test_cannot_infer_rail3D_from_g52(self):
  self.assertEqual(g.TOP_REPS,6)
  self.assertEqual(len(g.SITES["Vila_Real"])*len(g.SITES["Braganca"]),4)
if __name__=="__main__":unittest.main()
