"""DGT native NoData regression: source masks preserved; no fabricated ground."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import geo_rail_g3_native80 as qa

class TestOriginalSourceMasks(unittest.TestCase):
 def test_partial_source_nodata_seams_and_mosaic_preserve_original_ground(self):
  import numpy as np,rasterio
  from rasterio.transform import from_origin
  originals=[
   "MDT-2m-280507-09-2024","MDT-2m-281507-09-2024",
   "MDT-2m-280508-09-2024","MDT-2m-281508-09-2024"]
  group={"group_id":"G3-synthetic-only","batch":"regional",
     "grid_epsg3763":[80000,206000,82000,208000],"tile_ids":originals}
  with tempfile.TemporaryDirectory() as root:
   stage=Path(root)
   for ix,id in enumerate(originals):
    col,row=qa.parse_id(id)
    native=np.full((500,500),600.+ix,dtype="float32")
    native+=np.arange(500,dtype="float32")[None,:]*.002
    if ix==0:native[0:40,490:500]=-9999.
    with rasterio.open(stage/(id+".tif"),"w",driver="GTiff",count=1,
         width=500,height=500,dtype="float32",crs="EPSG:3763",
         transform=from_origin((col-200)*1000,(row-300)*1000,2,2),
         nodata=-9999.,compress="DEFLATE") as ds:ds.write(native,1)
   native_qa=[qa.native_raster_QA(stage/(id+".tif"),id) for id in originals]
   self.assertEqual(sum(q["real_valid_ground_pixels"] for q in native_qa),999600)
   self.assertEqual(sum(q["source_nodata_pixels"] for q in native_qa),400)
   seams=qa.four_seams(stage,group)
   self.assertEqual(len(seams),4)
   self.assertTrue(any(z["pairs_with_at_least_one_unfilled_NoData"]>0 for z in seams))
   self.assertTrue(all(z["pairs_valid"]+z["pairs_with_at_least_one_unfilled_NoData"]==500 for z in seams))
   mosaic=qa.create_mosaic(stage,group)
   result=qa.verify_mosaic(stage,group,mosaic)
   self.assertEqual(result["real_valid_ground_pixels"],999600)
   self.assertEqual(result["original_source_nodata_pixels"],400)
   self.assertFalse(result["all_cells_valid"])
   self.assertTrue(result["no_gap_fill_or_interpolation_performed"])
   with rasterio.open(mosaic) as ds:
    self.assertEqual(ds.nodata,-9999.)
    self.assertEqual(ds.read(1,masked=True).count(),999600)
 def test_original_nodata_na_not_misclassified_as_elevation(self):
  import numpy as np,rasterio
  from rasterio.transform import from_origin
  source="MDT-2m-280507-09-2024"
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)/(source+".tif")
   vals=np.full((500,500),550.,dtype="float32")
   vals[40,60]=float("nan")
   with rasterio.open(p,"w",driver="GTiff",count=1,width=500,height=500,
      crs="EPSG:3763",dtype="float32",transform=from_origin(80000,207000,2,2),
      compress="DEFLATE") as ds:ds.write(vals,1)
   report=qa.native_raster_QA(p,source)
   self.assertEqual(report["real_valid_ground_pixels"],249999)
   self.assertEqual(report["source_nodata_pixels"],1)
 def test_void_only_source_is_recorded_not_used_as_terrain(self):
  import numpy as np,rasterio
  from rasterio.transform import from_origin
  source="MDT-2m-280507-09-2024"
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)/(source+".tif")
   with rasterio.open(p,"w",driver="GTiff",count=1,width=500,height=500,
      crs="EPSG:3763",dtype="float32",nodata=-9999.,
      transform=from_origin(80000,207000,2,2),compress="DEFLATE") as ds:
    ds.write(np.full((500,500),-9999.,dtype="float32"),1)
   report=qa.native_raster_QA(p,source)
   self.assertEqual(report["real_valid_ground_pixels"],0)
   self.assertEqual(report["range_m"],None)
   self.assertTrue(report["source_has_unfilled_NoData"])

if __name__=="__main__":unittest.main()
