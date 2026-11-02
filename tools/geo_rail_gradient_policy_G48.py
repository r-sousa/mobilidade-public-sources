"""MN-GEO-RAIL-001 G48 canonical gradient screening regime (NOT certification).

Grounded in EU INF TSI Annex 4.2.3.3 (current consolidated 2023) and Spanish
Orden TMA/135/2023 IFI 4.1.4.1.3. Spanish requirements are geographic/
functional design REFERENCES, not automatic Portuguese permissions.

The 12.5,15 mixed cases replace 18/25 as the primary engineering evidence
screens. 18/20 freight only conditional exceptional F1/F2-F3 in Spain with
further project-level approvals; 25 is passenger-majority reference under
Spanish IFI, NOT validated for freight on those gradients. The TSI allows
up to 35mm/m in specified dedicated passenger P1 conditions; not in this
study matrix. Passenger platform coupling and stabling 2.5mm/m applicable
only where those operations occur; for passenger-only platform stops the
Spanish PAT category 10mm/m reference requires context. All thresholds
remain operational hypotheses pending applicable PT/PT-ES full validation.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Final

REGIME_VERSION: Final = "G48-2026-11-02"
EU_TSI: Final = "https://eur-lex.europa.eu/eli/reg/2014/1299/2023-09-28/eng"
ES_IFI: Final = "https://www.boe.es/buscar/doc.php?id=BOE-A-2023-4324"
NOMINAL_GRADES_PERMILLE: Final = (12.5,15.0,18.0,20.0,25.0)
SPEED_SCREENS_KMH: Final = (160,200,250)
# Every option is conditional, none automatically satisfies Portuguese design.
GRADIENT_REGIMES: Final = {
  12.5: {"id":"MIXED_REFERENCE_ES_IFI","traffic":"mixed_freight_and_passengers",
         "screen":"primary_reference","exceptional":False,
         "territorial_legal_scope":"Spain_IFI_reference_not_automatically_PT_approved"},
  15.0: {"id":"MIXED_NORMAL_ES_IFI_SUBJECT_TO_TRACTION_JUSTIFICATION",
         "traffic":"mixed_freight_and_passengers","screen":"primary_normal",
         "exceptional":False,"territorial_legal_scope":"Spain_IFI_normal_with_justification_no_PT_blanket_approval"},
  18.0: {"id":"F1_FREIGHT_EXCEPTION_ES_IFI_CONDITIONAL",
         "traffic":"mixed_freight_and_passengers_if_F1_exception_approved",
         "screen":"exception_only","exceptional":True,
         "territorial_legal_scope":"Spain_specific_F1_exception_pending_approval"},
  20.0: {"id":"F2_F3_FREIGHT_EXCEPTION_ES_IFI_CONDITIONAL",
         "traffic":"mixed_freight_and_passengers_if_F2_F3_exception_approved",
         "screen":"exception_only","exceptional":True,
         "territorial_legal_scope":"Spain_specific_F2_F3_exception_pending_approval"},
  25.0: {"id":"PASSENGER_MAJORITY_ONLY_REFERENCE_ES_IFI",
         "traffic":"predominantly_passenger_only_steep_sections_no_freight_presumed",
         "screen":"passenger_functional_alternative",
         "exceptional":False,
         "territorial_legal_scope":"Spain_passenger_reference_not_mixed_freight_permitted"},
}
# Station function is not synonymous with a mainline speed/grade threshold.
STATION_SENSITIVITIES: Final = {
 "general_through_track_exploratory": {
      "station_max_permille":None,"meaning":"mainline_gradient_only"},
 "passenger_stop_PAT_ES_IFI_10_reference": {
      "station_max_permille":10.0,"meaning":"Spanish_PAT_reference_for_passenger_stop_without_coupling_or_long_stabling_not_PT_universal"},
 "coupling_or_stabling_EU_TSI_2p5": {
      "station_max_permille":2.5,"meaning":"EU_TSI_binding_if_regular_coupling_decoupling_or_stabling_conditions_apply"},
}
STATION_STRAIGHT_STUDY_M: Final = 800
REFERENCE_VERTICAL_RADII_M: Final = (None,10000,20000)
def classify(grade:float)->dict:
    key=float(grade)
    if key not in GRADIENT_REGIMES:raise ValueError("G48_unknown_gradient_regime")
    return {"max_gradient_permille":key,**GRADIENT_REGIMES[key]}
def assert_policy():
    assert NOMINAL_GRADES_PERMILLE == (12.5,15.0,18.0,20.0,25.0)
    assert all(classify(g)["traffic"].startswith("mixed") for g in NOMINAL_GRADES_PERMILLE[:-1])
    assert classify(25)["traffic"].startswith("predominantly_passenger")
    assert all(classify(g)["exceptional"] for g in (18,20))
    assert STATION_SENSITIVITIES["coupling_or_stabling_EU_TSI_2p5"]["station_max_permille"]==2.5
    assert SPEED_SCREENS_KMH==(160,200,250)
assert_policy()
