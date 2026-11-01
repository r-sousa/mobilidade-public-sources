import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
try:
 from geo_rail_g29_natura_hotspot_and_macro_reranking import validate,SELECT
 HAVE_GIS=True
except ImportError:
 HAVE_GIS=False
@unittest.skipUnless(HAVE_GIS,'specialized G29 GIS job installs optional matplotlib and shapely')
class G29Tests(unittest.TestCase):
 def test_three_origins_distinct(self):
  self.assertEqual(len(set(SELECT)),3)
 def test_missing_original_paths_never_accepted(self):
  with self.assertRaises((ValueError,KeyError)):
   validate({'type':'FeatureCollection','features':[]},{},{},b'')
 def test_pic_unresolved_never_claims_source_legal_clear(self):
  geo={'type':'FeatureCollection','features':[]}
  g10={'type':'FeatureCollection','features':[{'properties':{'id':str(i),
      'this_is_not_an_approved_or_proposed_railway_alignment':True}} for i in range(27)]}
  report={'mission':'MN-GEO-RAIL-001','corridor_grid_research_27':[{}]*27,
          'city_research_circles_7':[{}]*7,
          'source_receipts':{'PT_ICNF':{'status':'VERIFIED'},'ES_MITECO':{'status':'VERIFIED'}},
          'PIC':'UNKNOWN','producer_clipped_natura_polygon_cache_sha256':'broken',
          'producer_clipped_natura_polygon_count':0}
  with self.assertRaises(ValueError):validate(g10,report,geo,b'')
if __name__=='__main__':unittest.main()
