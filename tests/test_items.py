"""Item groups stay tight, and ceiling text is not a spend total."""

from __future__ import annotations

from pipeline.items import ceiling_mention, choose_vendor_display, group_amount_cents, resolve_item


def test_stress_ball_variants_share_one_label_and_keep_the_line_amount():
    rows = [
        "24 pack slow rise stress balls",
        "HyDren 100 Pcs Mini Globe Stress Balls Bulk",
        "24 Pack Slow Rising Stress Cube, Large Size Dough Stress Balls",
        "Blulu 30 Pack Mini Footballs Foam Stress Ball Bulk",
    ]
    resolved = [resolve_item(text, f"line-{index}") for index, text in enumerate(rows)]
    assert {row["item_label"] for row in resolved} == {"stress balls"}
    assert all(row["item_method"] == "description_phrase" for row in resolved)
    assert all("stress ball" in str(row["item_evidence"]).lower() for row in resolved)
    amounts = [{"amount_cents": cents} for cents in (2063, 4211, 2915, 1792)]
    assert group_amount_cents(amounts) == 2063 + 4211 + 2915 + 1792


def test_broad_ball_and_bare_stress_cube_stay_ungrouped():
    assert resolve_item("foam football for the equipment room", "x")["item_label"] is None
    assert resolve_item("saguaro cactus poster", "x")["item_label"] is None
    assert resolve_item("stress cube only", "x")["item_label"] is None


def test_not_to_exceed_text_is_not_the_group_total():
    description = "NOT TO EXCEED AMOUNT $3,654,818.18 stress balls for a classroom"
    assert ceiling_mention(description)
    resolved = resolve_item(description, "nte")
    assert resolved["item_label"] == "stress balls"
    assert group_amount_cents([{"amount_cents": 2063, "description": description}]) == 2063


def test_group_labels_and_evidence_do_not_carry_personal_text():
    description = "stress balls for student Alex Rivera, 123 Main Street, check 1800086572"
    resolved = resolve_item(description, "pii")
    blob = f"{resolved['item_label']} {resolved['item_evidence']}"
    assert "Alex" not in blob
    assert "Main Street" not in blob
    assert "1800086572" not in blob
    assert "IEP" not in blob.upper()


def test_manual_override_wins_and_vendor_display_prefers_the_common_form():
    resolved = resolve_item("unrelated paper", "line-9", {"line-9": {"label": "stress balls", "confidence": 1, "evidence": "reviewer"}})
    assert resolved["item_method"] == "manual_override"
    assert resolved["item_label"] == "stress balls"
    assert choose_vendor_display([
        ("AMAZON CAPITAL SERVICES", 2),
        ("AMAZON CAPITAL SERVICES, INC.", 9),
    ]) == "AMAZON CAPITAL SERVICES, INC."
