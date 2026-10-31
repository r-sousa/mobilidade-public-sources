"""Offline checks for C1 ground DTM5m evidence with Vila Real & Bragança required."""
import importlib.util,sys,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/"tools"))
spec=importlib.util.spec_from_file_location("c1",R/"tools"/"geo_rail_es_c1_ground_5m.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class C1SourceReview(unittest.TestCase):
    def test_two_disjoint_N122_terrain_research_panels(self):
        self.assertEqual(m.SITE_BOXES,{
            "Alcanices":[218000,4619000,226000,4625000],
            "Muelas_del_Pan":[248000,4597000,256000,4603000]})
        self.assertEqual(m.COVERAGE,"Elevacion25830_5")
        self.assertEqual(m.RES,5)
        self.assertEqual(len(m.SITE_BOXES),2)
        for site in m.SITE_BOXES:
            cells=m.site_blocks(site)
            self.assertEqual(len(cells),12)
            self.assertEqual(len({tuple(z[2]) for z in cells}),12)
            self.assertEqual(sum((b[2]-b[0])*(b[3]-b[1]) for _,_,b in cells),48_000_000)
            for _,_,b in cells:self.assertIn("coverageId=Elevacion25830_5",m.url_for(b))
    def test_no_sanabria_in_acquisition(self):
        self.assertTrue(all("Sanabria" not in k for k in m.SITE_BOXES))
        self.assertIn("IGN",m.REQUIRED_NOTICE)
        with self.assertRaises(ValueError):m.url_for([0,0,2000,2000])
        with self.assertRaises(ValueError):m.site_blocks("Sanabria")
if __name__=="__main__":unittest.main()
