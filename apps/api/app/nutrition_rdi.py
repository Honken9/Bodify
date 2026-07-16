"""Referensvärden för dagligt intag.

Förenklade vuxenvärden baserade på NNR 2023 (Nordiska näringsrekommen-
dationer). Individuella behov varierar med kön, ålder och graviditet —
värdena här är riktmärken för visualisering, inte medicinsk rådgivning.

kind = "rdi": rekommenderat intag att nå upp till (grön stapel).
kind = "max": gräns att hålla sig UNDER (varningsfärg över 100 %).
"""

NUTRIENTS: list[dict] = [
    {"key": "fiber_g", "label": "Fiber", "unit": "g", "rdi": 30, "kind": "rdi"},
    {"key": "salt_g", "label": "Salt", "unit": "g", "rdi": 6, "kind": "max"},
    {"key": "sugar_g", "label": "Socker", "unit": "g", "rdi": 50, "kind": "max"},
    {
        "key": "saturated_fat_g",
        "label": "Mättat fett",
        "unit": "g",
        "rdi": 22,
        "kind": "max",
    },
    {"key": "vitamin_a_ug", "label": "Vitamin A", "unit": "µg", "rdi": 800, "kind": "rdi"},
    {"key": "vitamin_c_mg", "label": "Vitamin C", "unit": "mg", "rdi": 100, "kind": "rdi"},
    {"key": "vitamin_d_ug", "label": "Vitamin D", "unit": "µg", "rdi": 10, "kind": "rdi"},
    {"key": "vitamin_b12_ug", "label": "Vitamin B12", "unit": "µg", "rdi": 4, "kind": "rdi"},
    {"key": "folate_ug", "label": "Folat", "unit": "µg", "rdi": 330, "kind": "rdi"},
    {"key": "calcium_mg", "label": "Kalcium", "unit": "mg", "rdi": 950, "kind": "rdi"},
    {"key": "iron_mg", "label": "Järn", "unit": "mg", "rdi": 11, "kind": "rdi"},
    {"key": "magnesium_mg", "label": "Magnesium", "unit": "mg", "rdi": 350, "kind": "rdi"},
    {"key": "potassium_mg", "label": "Kalium", "unit": "mg", "rdi": 3500, "kind": "rdi"},
    {"key": "zinc_mg", "label": "Zink", "unit": "mg", "rdi": 11, "kind": "rdi"},
]
