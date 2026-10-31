"""Official DGT source NP159 5 variant mark metadata and bounded request safety."""
import importlib.util
import sys
import json
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
spec=importlib.util.spec_from_file_location("np159",ROOT/"tools"/"geo_rail_rngap_np159_original_descriptors.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class Contracts(unittest.TestCase):
    def test_exact_five_DGT_original_mark_variants(self):
        marks,sha=m.producer_mark_records(ROOT/m.SOURCE_MARKS_PATH) if hasattr(m,"SOURCE_MARKS_PATH") else m.producer_mark_records(ROOT/"reports/mn-geo-rail-001/pt-rngap-three-window-complete-ALTH38-source.json")
        self.assertEqual(len(marks),5)
        self.assertEqual(m.MAX_FEATURES,30)
        self.assertEqual(m.WINDOW,(79418,202238,79518,202338))
        self.assertIn("typeNames=RGN%3ARedeNivelamento",m.url_for_source())
        self.assertTrue(all(x["WFS_feature_id"] in m.SOURCE_MARKS for x in marks))
    def test_five_original_source_records_retain_description_and_original_height(self):
        marks,_=m.producer_mark_records(ROOT/"reports/mn-geo-rail-001/pt-rngap-three-window-complete-ALTH38-source.json")
        rows=[{"type":"Feature","id":x["WFS_feature_id"],
               "geometry":{"type":"Point","coordinates":x["native_xy_epsg3763"]},
               "properties":{"MARCA":x["mark_label_MARCA"],
                             "ALTH38":x["DGT_ALTH38_original_source_value"],
                             "DESCRICAO":"Synthetic reference mark description",
                             "MARCA2":"alternate mark name"}} for x in marks]
        d=m.inspect(json.dumps({"type":"FeatureCollection","features":rows}).encode(),
                    {x["WFS_feature_id"]:x for x in marks})
        self.assertEqual(d["matching_reviewed_source_records"],5)
        self.assertFalse(d["physical_mark_height_offset_explained_by_detailed_source"])
        self.assertTrue(all("DESCRICAO" in x["original_attributes"] for x in
                            d["selected_mark_physical_identification_fields"]))
    def test_missing_variants_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"five_reviewed"):
            m.inspect(b'{"type":"FeatureCollection","features":[]}',{})
if __name__=="__main__":unittest.main()
