
import math

import pytest

from services.markers import (
    FEMALE_FALLBACK,
    FEMALE_STOPS,
    JITTER_SATURATION_PINS,
    MALE_FALLBACK,
    MALE_STOPS,
    PH_MAX,
    PH_MIN,
    marker_colour,
    ph_colour,
    pin_icon,
    popup_html,
    spiral_offset,
)


def test_colour_scale_runs_dark_at_low_ph_to_light_at_normal_ph():
    assert ph_colour(PH_MIN, MALE_STOPS) == MALE_STOPS[0][1]
    assert ph_colour(PH_MAX, MALE_STOPS) == MALE_STOPS[-1][1]


def test_ph_outside_the_scale_is_clamped_not_extrapolated():
    assert ph_colour(5.0, MALE_STOPS) == ph_colour(PH_MIN, MALE_STOPS)
    assert ph_colour(9.0, MALE_STOPS) == ph_colour(PH_MAX, MALE_STOPS)


def test_every_colour_is_a_valid_hex_triplet():
    for ph in [6.5, 6.9, 7.0, 7.2, 7.35, 7.5]:
        for stops in (MALE_STOPS, FEMALE_STOPS):
            colour = ph_colour(ph, stops)
            assert len(colour) == 7 and colour[0] == "#"
            int(colour[1:], 16)


def test_sex_selects_the_palette():
    male = marker_colour({"sex": "Male", "ph": 7.2})
    female = marker_colour({"sex": "Female", "ph": 7.2})
    assert male != female


@pytest.mark.parametrize("ph", [None, "", "n/a"])
def test_a_missing_ph_falls_back_to_a_flat_colour(ph):
    assert marker_colour({"sex": "Male", "ph": ph}) == MALE_FALLBACK
    assert marker_colour({"sex": "Female", "ph": ph}) == FEMALE_FALLBACK


def test_a_case_with_no_ph_key_at_all_still_renders():
    assert marker_colour({"sex": "Female"}) == FEMALE_FALLBACK



def test_the_first_pin_sits_on_the_anchor():
    assert spiral_offset(48.52, 9.05, 0, 450.0) == (48.52, 9.05)


def test_pins_never_leave_their_postcode_budget():
    lat, lon, budget = 48.52, 9.05, 450.0
    for index in range(300):
        pin_lat, pin_lon = spiral_offset(lat, lon, index, budget)
        north = (pin_lat - lat) * 111_320
        east = (pin_lon - lon) * 111_320 * math.cos(math.radians(lat))
        assert math.hypot(north, east) <= budget + 2


def test_pins_do_not_land_on_top_of_one_another():
    positions = [spiral_offset(48.52, 9.05, i, 450.0) for i in range(60)]
    assert len(set(positions)) == len(positions)


def test_the_spiral_opens_outward():
    lat, lon = 48.52, 9.05

    def radius(index):
        pin_lat, pin_lon = spiral_offset(lat, lon, index, 450.0)
        return math.hypot((pin_lat - lat), (pin_lon - lon))

    assert radius(1) < radius(20) < radius(80)


def test_the_budget_is_reached_at_the_saturation_point():
    lat, lon, budget = 48.52, 9.05, 450.0
    pin_lat, pin_lon = spiral_offset(lat, lon, JITTER_SATURATION_PINS, budget)
    north = (pin_lat - lat) * 111_320
    east = (pin_lon - lon) * 111_320 * math.cos(math.radians(lat))
    assert math.hypot(north, east) == pytest.approx(budget, rel=0.02)


def test_a_larger_budget_scatters_further():
    tight = spiral_offset(48.52, 9.05, 10, 300.0)
    loose = spiral_offset(48.52, 9.05, 10, 2500.0)
    assert abs(loose[0] - 48.52) > abs(tight[0] - 48.52)



def test_popup_escapes_values_that_come_from_the_clinic_export():
    html = popup_html(
        {"id": 1, "sex": "<script>alert(1)</script>", "age_at_onset": 7.0},
        "Severe",
        "72070 Tübingen",
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_popup_escapes_the_area_label_and_severity():
    html = popup_html({"id": 1}, "<b>x</b>", "<i>y</i>")
    assert "<b>x</b>" not in html and "<i>y</i>" not in html


def test_popup_renders_missing_values_as_a_dash():
    html = popup_html({"id": 1, "ph": None, "glucose": ""}, "Unknown", "—")
    assert "—" in html


def test_popup_always_states_that_the_position_is_not_an_address():
    html = popup_html({"id": 1}, "Mild", "72070 Tübingen")
    assert "not the patient's address" in html


def test_pin_icon_embeds_the_colour_as_valid_json():
    icon = pin_icon("#2563eb")
    assert "#2563eb" in icon
    assert icon.startswith("L.divIcon({")
