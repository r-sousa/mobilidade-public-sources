"""G21 DGT exact original raster NoData regression; no invented terrain.

Reproduces failure of G21 run 41256251901 (source cells not universally
valid); reuses source mask behavior already accepted in G3. Tests are entirely
synthetic and must never attempt DGT authentication or log URL/credentials.
"""
import importlib.util,sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
HAVE=all(importlib.util.find_spec(n) is not None for n in ("requests","rasterio","numpy"))
if HAVE:
 import numpy as np
 import rasterio
 from rasterio.transform import from_origin
 from geo_rail_g21_protected_original_DGT_native_acquisition import (
  TILE,MAX_TOTAL_BYTES,MAX_NEW_TILES,original_qa,NATIVE_PIXELS_PER_TILE)
@unittest.skipUnless(HAVE,"G21 original raster tests only in GIS specialist runner")
class G21(unittest.TestCase):
 def test_exact_pinned_source_tile_identifier(self):
  self.assertTrue(TILE.fullmatch("MDT-2m-228481-07-2024"))
  self.assertTrue(TILE.fullmatch("MDT-2m-313539-06-2024"))
  self.assertFalse(TILE.fullmatch("MDT-2m-other"))
  self.assertFalse(TILE.fullmatch("MDT-50cm-313539-06-2024"))
 def test_bound_total_source_download(self):
  self.assertLessEqual(MAX_NEW_TILES,54)
  self.assertLessEqual(MAX_TOTAL_BYTES,160000000)
 def native(self,folder,values,nodata=-9999.,shift=0):
  item={"producer_ID":"MDT-2m-228481-07-2024",
    "expected_original_GeoTIFF_bbox_EPSG3763_m":[28000,180000,29000,181000]}
  p=Path(folder)/(item["producer_ID"]+".tif")
  with rasterio.open(p,"w",driver="GTiff",count=1,width=500,height=500,
     dtype="float32",crs="EPSG:3763",nodata=nodata,
     transform=from_origin(28000+shift,181000,2,2),
     compress="DEFLATE") as ds: ds.write(values,1)
  return p,item
 def test_partial_original_source_nodata_preserved(self):
  with tempfile.TemporaryDirectory() as root:
   arr=np.full((500,500),570.,dtype="float32")
   arr[0:40,490:500]=-9999.
   p,meta=self.native(root,arr)
   qa=original_qa(p,meta)
   self.assertEqual(qa["source_native_valid_pixels"],249600)
   self.assertEqual(qa["source_nodata_pixels"],400)
   self.assertTrue(qa["source_has_unfilled_NoData"])
   self.assertFalse(qa["source_original_tile_is_entirely_NoData_unusable_as_ground"])
   self.assertEqual(qa["source_terrain_original_z_min_max_m"],[570.,570.])
   self.assertTrue(qa["no_synthetic_ground_gap_filling_interpolation_or_zero_elevation"])
   self.assertEqual(qa["source_native_valid_pixels"]+qa["source_nodata_pixels"],NATIVE_PIXELS_PER_TILE)
 def test_undeclared_nan_is_not_valid_ground(self):
  with tempfile.TemporaryDirectory() as root:
   arr=np.full((500,500),615.,dtype="float32")
   arr[80,90]=float("nan")
   p,meta=self.native(root,arr,nodata=None)
   qa=original_qa(p,meta)
   self.assertEqual(qa["source_native_valid_pixels"],249999)
   self.assertEqual(qa["source_nodata_pixels"],1)
   self.assertTrue(qa["source_has_unfilled_NoData"])
 def test_entirely_nodata_original_archived_but_not_ground(self):
  with tempfile.TemporaryDirectory() as root:
   p,meta=self.native(root,np.full((500,500),-9999.,dtype="float32"))
   qa=original_qa(p,meta)
   self.assertEqual(qa["source_native_valid_pixels"],0)
   self.assertEqual(qa["source_nodata_pixels"],250000)
   self.assertIsNone(qa["source_terrain_original_z_min_max_m"])
   self.assertTrue(qa["source_original_tile_is_entirely_NoData_unusable_as_ground"])
 def test_false_native_source_transform_rejected(self):
  with tempfile.TemporaryDirectory() as root:
   p,meta=self.native(root,np.full((500,500),540.,dtype="float32"),shift=10)
   with self.assertRaises(ValueError):
    original_qa(p,meta)
 def test_valid_ground_out_of_territory_z_rejected(self):
  with tempfile.TemporaryDirectory() as root:
   p,meta=self.native(root,np.full((500,500),6000.,dtype="float32"))
   with self.assertRaises(ValueError):
    original_qa(p,meta)
if __name__=="__main__":unittest.main()
