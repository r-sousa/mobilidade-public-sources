"""G7 synthetic validation of the necessary-condition screen; full raster tests in G7 workflow."""
import importlib.util,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
HAVE=all(importlib.util.find_spec(x) is not None for x in ("numpy","scipy","rasterio","pyproj","shapely"))
if HAVE:
 import numpy as np
 from geo_rail_g7_rail_screen import (grade_envelopes,dense,smooth,radius_screen,
   choose_geometry,SPEEDS,MAX_REF_DISPLACEMENT_M)
@unittest.skipUnless(HAVE,"full G7 GIS dependencies installed in specialized public-source CI")
class G7Geometry(unittest.TestCase):
 def test_vertical_lipschitz_profile_reconstruction(self):
  z=np.asarray([0.,0.,70.,100.,25.,10.,10.,40.])
  s=np.arange(len(z),dtype=float)*200.
  for grade in (.018,.025,.035):
   h=grade_envelopes(z,s,grade)
   self.assertTrue(np.all(np.abs(np.diff(h))<=grade*200+1e-6))
   self.assertTrue(np.isfinite(h).all())
 def test_flat_profile_identity(self):
  z=np.linspace(12,27,101);s=np.arange(101)*200.
  self.assertTrue(np.allclose(grade_envelopes(z,s,.025),z))
 def test_spatial_smoothing_wont_claim_rail_stations(self):
  source=[(i*2000,0) for i in range(30)]
  a,_=choose_geometry(source,SPEEDS[250])
  self.assertIsNotNone(a)
  line,proof=a
  self.assertLessEqual(proof["max_distance_to_source_research_polyline_m"],MAX_REF_DISPLACEMENT_M)
  self.assertGreaterEqual(proof["min_proxy_radius_m"],SPEEDS[250])
 def test_lattice_topology_guard(self):
  with self.assertRaises(ValueError):dense([(0,0),(5000,0)]+[(i*2000,0) for i in range(4,15)])
if __name__=="__main__":unittest.main()
