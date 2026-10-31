"""B1 strict static source and synthetic native tile QA; secrets never required."""
import importlib.util,json,sys,unittest,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import geo_rail_pt_b1_native32 as m
CONFIG=ROOT/"configs"/"MN-GEO-RAIL-001-B1-DGT32-source-IDs.json"
class Review(unittest.TestCase):
 def test_32_statically_pinned_exact_native_2m_producer_tiles(self):
  d=m.read_review(CONFIG)
  self.assertEqual({g["city"] for g in d["groups"]},{"vila_real","braganca"})
  self.assertEqual(len(d["groups"]),8)
  self.assertEqual(len({x["direction"] for x in m.city_groups(d,"braganca")}),4)
  original=[id for g in d["groups"] for id in g["tile_ids"]]
  self.assertEqual(len(original),32)
  self.assertEqual(len(set(original)),32)
  for g in d["groups"]:
   e,s,w,n=g["grid_epsg3763"]
   self.assertEqual((w-e,n-s),(2000,2000))
   self.assertEqual(len(g["tile_ids"]),4)
   positions={tuple(m.parse_tile(t)[:2]) for t in g["tile_ids"]}
   self.assertEqual(positions,{(e//1000+200+dc,s//1000+301+dr)
                               for dc in (0,1) for dr in (0,1)})
  self.assertTrue(d["sanabria_excluded"])
  self.assertFalse(d["station_location_determined"])
  self.assertFalse(d["active_railway_line_defined"])
 def test_refuse_wrong_edition_city_and_scope(self):
  with self.assertRaises(ValueError):m.parse_tile("MDT-2m-999999-00-0000")
  with self.assertRaises(ValueError):m.parse_tile("MDT-50cm-220481-07-2024")
  with self.assertRaises(ValueError):m.city_groups(m.read_review(CONFIG),"sanabria")
  invalid=json.loads(CONFIG.read_text())
  invalid["mandatory_cities"]=["vila_real"]
  with tempfile.TemporaryDirectory() as tmp:
   bad=Path(tmp)/"bad.json"
   bad.write_text(json.dumps(invalid))
   with self.assertRaises(ValueError):m.read_review(bad)
 def test_one_tile_exact_producer_native_QA_if_geo_libraries_available(self):
  if not(importlib.util.find_spec("rasterio") and importlib.util.find_spec("numpy")):
   self.skipTest("source pixel QA runs with rasterio and numpy in protected workflow")
  import rasterio,numpy as np,tempfile
  from rasterio.transform import from_origin
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/"MDT-2m-220481-07-2024.tif"
   with rasterio.open(p,"w",driver="GTiff",width=500,height=500,count=1,
     crs="EPSG:3763",transform=from_origin(20000,181000,2,2),dtype="float32",compress="DEFLATE") as ds:
    ds.write(np.full((500,500),120.,dtype="float32"),1)
   qa=m.native_qa(p,"MDT-2m-220481-07-2024")
   self.assertEqual(qa["valid_pixels"],250000)
   self.assertEqual(qa["horizontal_crs"],"EPSG:3763")
   self.assertEqual(qa["nodata_pixels"],0)
if __name__=="__main__":unittest.main()
