"""G49 ground-study station and freight reference physics audit tests."""
import importlib.util,pathlib,unittest
root=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("g49",root/"tools/geo_rail_g49_mixed_freight_station_source_comparison.py")
g49=importlib.util.module_from_spec(spec);spec.loader.exec_module(g49)
class SourceTraction(unittest.TestCase):
 def test_reference_physics_1500t_12p5perthousand_60kmh(self):
  x=g49.grade_only(1500,12.5,60)
  self.assertAlmostEqual(x["grade_gravity_only_force_kN"],183.875,places=2)
  self.assertAlmostEqual(x["grade_gravity_only_ideal_rail_power_MW"],3.0646,places=3)
  self.assertTrue(x["excluded_resistance_acceleration_adhesion_mechanical_losses"])
 def test_15perthousand_20pct_gravity_increase(self):
  a=g49.grade_only(1500,12.5,60)
  b=g49.grade_only(1500,15,60)
  self.assertAlmostEqual(b["grade_gravity_only_force_kN"]/a["grade_gravity_only_force_kN"],1.2,places=4)
 def test_downhill_not_train_braking_rating(self):
  v=g49.grade_only(2000,20,80)
  self.assertEqual(v["grade_downgrade_energy_dissipation_floor_MW_if_same_speed"],
    v["grade_gravity_only_ideal_rail_power_MW"])
  self.assertTrue(v["not_train_brake_rating_or_locotractor_performance"])
 def test_no_25perthousand_freight_or_train_length_assumptions(self):
  self.assertEqual(g49.FREIGHT_GRADES,(12.5,15.,18.,20.))
  self.assertEqual(g49.MIXED,(12.5,15.))
  self.assertEqual(g49.MASS_T,(1000,1500,2000))
  self.assertEqual(len(g49.SITES),4)
 def test_zero_bad_scenarios(self):
  for a,b,c in ((0,12.5,60),(1500,0,60),(1500,15,0)):
   with self.assertRaises(ValueError):g49.grade_only(a,b,c)
 def test_freight_physics_consistent_speed_and_mass(self):
  a=g49.grade_only(1000,15,40)
  b=g49.grade_only(2000,15,80)
  self.assertAlmostEqual(b["grade_gravity_only_force_kN"]/a["grade_gravity_only_force_kN"],2,places=3)
  self.assertAlmostEqual(b["grade_gravity_only_ideal_rail_power_MW"]/a["grade_gravity_only_ideal_rail_power_MW"],4,places=3)
if __name__=="__main__":unittest.main()
