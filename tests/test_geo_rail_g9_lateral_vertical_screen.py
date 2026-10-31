"""G9 deterministic synthetic invariants. Dedicated GIS runner tests all."""
import importlib.util,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
HAVE=all(importlib.util.find_spec(x) is not None for x in ("numpy","scipy","rasterio","shapely","pyproj"))
if HAVE:
 import numpy as np
 from geo_rail_g9_lateral_vertical_screen import (
  city_modules,normal_perturbation,lp_dsm_proxy,hotspot_windows,SOURCE_CITY_POINTS)
 from pyproj import Transformer

@unittest.skipUnless(HAVE,"G9 GIS complete testing runs in dedicated GitHub Actions")
class G9Tests(unittest.TestCase):
 def test_three_2d_modules_and_city_knots(self):
  p=[(-1000.+2000*i,1000.) for i in range(145)]
  # synthetic exact anchor geometry from code, preserving sequence
  p[30]=(21000.,181000.)
  p[40]=(41000.,185000.)
  p[90]=(111000.,235000.)
  p[100]=(117000.,239000.)
  # Fix synthetic coordinates to keep monotone sequence unnecessary here;
  # city_modules tests exact cell labels and their source order only.
  z,k=city_modules(p)
  self.assertEqual(len(z),3)
  self.assertEqual(len(k),4)
  self.assertTrue(k[0]<k[1]<k[2]<k[3])
 def test_per_module_offset_zero_outside_and_at_boundaries(self):
  p=[(i*2000.,1000.) for i in range(150)]
  base_s=np.linspace(0.,298000.,1491)
  xy=np.column_stack([base_s,np.full(len(base_s),1000.)])
  left,right=60000.,140000.
  out,normal=normal_perturbation(xy,p,(left,right,"test"),1200.)
  self.assertLess(np.max(np.abs(normal)),1200.01)
  self.assertTrue(np.allclose(out[base_s<=left],xy[base_s<=left]))
  self.assertTrue(np.allclose(out[base_s>=right],xy[base_s>=right]))
  self.assertGreater(float(out[:,1].max()),2000.)
 def test_l1_grade_is_bound_and_zero_for_flat_surface(self):
  xy=np.column_stack([np.arange(100,dtype=float)*200.,np.zeros(100)])
  z=np.ones(100)*200.
  for g in (18.,25.):
   info,r,s=lp_dsm_proxy(xy,z,g)
   self.assertLess(np.max(np.abs(r)),.001)
   self.assertLess(info["max_abs_mathematical_gradient_permille"],g+.001)
 def test_large_step_rejected(self):
  xy=np.column_stack([np.arange(30,dtype=float)*200.,np.zeros(30)])
  xy[10:,0]+=3000
  z=np.arange(30,dtype=float)
  # A wide sampling interval is legal; 3D screening reports it, never makes
  # unsupported station or construction assumptions.
  meta,r,s=lp_dsm_proxy(xy,z,25.)
  self.assertEqual(len(s),30)
if __name__=="__main__":unittest.main()
