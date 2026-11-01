"""G26B original DGT 2m raster 1km tile vs research grid 2km distinction."""
import unittest,sys,importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
HAVE=all(importlib.util.find_spec(x) is not None for x in ("shapely","pyproj"))
if HAVE:
 from geo_rail_g26b_next_DGT2m_study_footprint_gate import indices,envelope,ENVELOPES
@unittest.skipUnless(HAVE,"G26B precise original 1km DGT vs 2km grid specialist")
class G26B(unittest.TestCase):
 def test_straight_buffer_tile_gaps_are_footprints_not_terrain_data(self):
  p=envelope((28500,180500),0,1500,300)
  ids=indices(p)
  self.assertIn((228,481),ids)
  self.assertGreaterEqual(len(ids),3)
  self.assertTrue(all(len(v)==2 for v in ids))
 def test_study_extents_grow(self):
  counts=[len(indices(envelope((28500,180500),15,a,b))) for a,b in ENVELOPES]
  self.assertTrue(counts[0]<counts[1]<counts[2])
if __name__=="__main__":unittest.main()
