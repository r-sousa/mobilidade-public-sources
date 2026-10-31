"""Original DGT 2m G3 protected 80-source tile QA; offline, no credentials."""
import importlib.util,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import geo_rail_g3_native80 as m
class TestG3Native80(unittest.TestCase):
 def test_three_reviewed_batches_and_no_extraneous_sources(self):
  self.assertEqual(m.BATCHES,{"vila_real":7,"braganca":5,"regional":8})
  self.assertEqual(sum(m.BATCHES.values()),20)
  self.assertEqual(m.parse_id("MDT-2m-274503-09-2024"),(274,503))
  self.assertEqual(m.tile_bounds("MDT-2m-274503-09-2024"),[74000,202000,75000,203000])
  for id in ("MDT-2m-999999-00-2024","MDT-50cm-274503-09-2024",
             "MDT-2m-274503-09-2024;echo-bad"):
   with self.assertRaises(ValueError):m.parse_id(id)
 def test_expected_batched_auth_only_source_ids(self):
  groups=[{"batch":"vila_real"}]*7+[{"batch":"braganca"}]*5+[{"batch":"regional"}]*8
  self.assertEqual(len(m.batch_groups(groups,"regional")),8)
  with self.assertRaises(ValueError):m.batch_groups(groups,"sanabria")
  with self.assertRaises(ValueError):m.batch_groups(groups[:-1],"regional")
 def test_source_native_raster_exact_pixels_if_rasterio_installed(self):
  if not(importlib.util.find_spec("rasterio") and importlib.util.find_spec("numpy")):
   self.skipTest("requires source rasterio and numpy")
  import tempfile,numpy as np,rasterio
  from rasterio.transform import from_origin
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/"MDT-2m-274503-09-2024.tif"
   with rasterio.open(p,"w",driver="GTiff",count=1,width=500,height=500,
       crs="EPSG:3763",transform=from_origin(74000,203000,2,2),
       dtype="float32",compress="deflate") as ds:
    ds.write(np.full((500,500),650.,dtype="float32"),1)
   q=m.native_raster_QA(p,"MDT-2m-274503-09-2024")
   self.assertEqual(q["real_valid_ground_pixels"],250000)
   self.assertEqual(q["source_nodata_pixels"],0)
if __name__=="__main__":unittest.main()
