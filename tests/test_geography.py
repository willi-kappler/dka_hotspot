
import math

import pytest

from services.geography import (
    JITTER_MAX_METRES,
    JITTER_MIN_METRES,
    KREISE_WITHOUT_CLINIC,
    PILOT_KREISE,
    _metres_between,
    in_pilot_region,
    is_pilot_kreis,
    is_pilot_plz5,
    kreis_name,
    normalise_plz5,
    pilot_boundaries,
    pilot_bounds,
    pilot_plz5,
    pilot_view,
    plz5_centroids,
    plz5_city,
    plz5_jitter_radius,
    plz5_kreis,
    plz5_label,
    plz5_outside_region,
)


@pytest.mark.parametrize("raw, expected", [
    ("72070", "72070"),
    (" 72070 ", "72070"),
    ("72070 Tübingen", "72070"),
    ("D-72070", "72070"),
    (72070, "72070"),
    ("720700", "72070"),   # over-long input is truncated to five digits
])
def test_normalise_plz5_extracts_five_digits(raw, expected):
    assert normalise_plz5(raw) == expected


@pytest.mark.parametrize("raw", ["", "7207", "abcde", None, "  ", "1234"])
def test_normalise_plz5_rejects_anything_short_of_five_digits(raw):
    assert normalise_plz5(raw) == ""



def test_the_pilot_is_exactly_three_districts():
    assert set(PILOT_KREISE) == {"08415", "08416", "08417"}
    assert PILOT_KREISE["08416"] == "Tübingen"


def test_zollernalb_is_flagged_as_having_no_participating_clinic():
    assert KREISE_WITHOUT_CLINIC == {"08417"}
    assert KREISE_WITHOUT_CLINIC <= set(PILOT_KREISE)


@pytest.mark.parametrize("ags, expected", [
    ("08416", True), ("8416", True),      # unpadded AGS still resolves
    ("08111", False),                     # Stuttgart, outside the pilot
])
def test_is_pilot_kreis(ags, expected):
    assert is_pilot_kreis(ags) is expected


def test_kreis_name_of_an_unknown_district_is_empty():
    assert kreis_name("08111") == ""



def test_every_pilot_postcode_resolves_to_a_pilot_district():
    for postcode in pilot_plz5():
        ags = plz5_kreis(postcode)
        assert ags, f"{postcode} has no Landkreis in the reference table"
        assert is_pilot_kreis(ags), f"{postcode} maps outside the pilot ({ags})"


def test_the_reference_table_is_not_empty_and_covers_all_three_districts():
    postcodes = pilot_plz5()
    assert len(postcodes) > 50
    assert {plz5_kreis(p) for p in postcodes} == set(PILOT_KREISE)


def test_postcodes_are_unique_and_sorted():
    postcodes = pilot_plz5()
    assert list(postcodes) == sorted(set(postcodes))


def test_is_pilot_plz5_rejects_a_postcode_outside_the_region():
    assert is_pilot_plz5("70173") is False    # Stuttgart
    assert is_pilot_plz5(pilot_plz5()[0]) is True


def test_plz5_lookups_of_an_unknown_postcode_are_empty_not_an_error():
    assert plz5_kreis("70173") == ""
    assert plz5_city("70173") == ""
    assert plz5_label("") == "—"


def test_plz5_label_reads_as_postcode_then_town():
    postcode = pilot_plz5()[0]
    assert plz5_label(postcode).startswith(postcode)



def test_pilot_boundaries_hold_only_the_three_districts():
    features = pilot_boundaries()["features"]
    assert len(features) == 3
    assert {str(f["properties"]["AGS"]).zfill(5) for f in features} == set(PILOT_KREISE)


def test_pilot_bounds_enclose_the_region_and_sit_in_south_west_germany():
    (south, west), (north, east) = pilot_bounds()
    assert south < north and west < east
    assert 48.0 < south < north < 49.0
    assert 8.0 < west < east < 10.0


def test_pilot_view_returns_a_centre_inside_the_bounds():
    (south, west), (north, east) = pilot_bounds()
    (lat, lon), zoom = pilot_view()
    assert south <= lat <= north
    assert west <= lon <= east
    assert 6 <= zoom <= 12


def test_pilot_view_zooms_out_for_a_smaller_viewport():
    _, wide = pilot_view((1600, 900))
    _, narrow = pilot_view((400, 300))
    assert narrow <= wide



def test_a_point_far_outside_the_region_is_rejected():
    assert in_pilot_region(48.1372, 11.5756) is False   # Munich
    assert in_pilot_region(52.5200, 13.4050) is False   # Berlin
    assert in_pilot_region(0.0, 0.0) is False


def test_district_centres_fall_inside_the_region():
    inside = sum(
        1 for lat, lon in plz5_centroids().values() if in_pilot_region(lat, lon)
    )
    assert inside > len(plz5_centroids()) * 0.8, (
        "most postcode centroids should fall inside the district polygons"
    )



def test_every_centroid_belongs_to_a_known_pilot_postcode():
    assert set(plz5_centroids()) <= set(pilot_plz5())


def test_centroid_coverage_is_complete():
    missing = set(pilot_plz5()) - set(plz5_centroids())
    assert not missing, f"postcodes with no centroid: {sorted(missing)}"


def test_centroids_are_plausible_coordinates():
    for postcode, (lat, lon) in plz5_centroids().items():
        assert 47.5 < lat < 49.5, f"{postcode} latitude {lat} is not in the region"
        assert 8.0 < lon < 10.5, f"{postcode} longitude {lon} is not in the region"


def test_outside_region_postcodes_are_flagged_not_dropped():
    flagged = plz5_outside_region()
    assert flagged <= set(pilot_plz5())
    assert flagged <= set(plz5_centroids())


def test_jitter_radius_stays_within_its_floor_and_ceiling():
    for postcode in plz5_centroids():
        radius = plz5_jitter_radius(postcode)
        assert JITTER_MIN_METRES <= radius <= JITTER_MAX_METRES


def test_jitter_radius_is_larger_where_centroids_are_further_apart():
    radii = {p: plz5_jitter_radius(p) for p in plz5_centroids()}
    assert len(set(radii.values())) > 1, "radii should vary across the region"


def test_unknown_postcode_falls_back_to_the_minimum_radius():
    assert plz5_jitter_radius("70173") == JITTER_MIN_METRES


def test_metres_between_is_symmetric_and_zero_on_itself():
    a, b = (48.52, 9.05), (48.49, 9.21)
    assert _metres_between(a, a) == 0.0
    assert _metres_between(a, b) == pytest.approx(_metres_between(b, a))


def test_metres_between_matches_a_known_distance():
    assert _metres_between((48.0, 9.0), (49.0, 9.0)) == pytest.approx(111_320, rel=0.01)


def test_metres_between_shrinks_longitude_at_this_latitude():
    north = _metres_between((48.0, 9.0), (48.5, 9.0))
    east = _metres_between((48.0, 9.0), (48.0, 9.5))
    assert east == pytest.approx(north * math.cos(math.radians(48.25)), rel=0.02)



def test_paediatric_practices_are_restricted_to_pilot_postcodes():
    from services.geography import paediatric_practices

    practices = paediatric_practices()
    assert practices, "the practice overlay should not be empty"
    pilot = set(pilot_plz5())
    for practice in practices:
        assert practice["postcode"] in pilot
        assert 47.5 < practice["lat"] < 49.5
        assert 8.0 < practice["lon"] < 10.5
        assert practice["name"]


def test_hospitals_overlay_marks_which_are_participating():
    from services.geography import clinics_on_map

    hospitals = clinics_on_map()
    assert hospitals
    flags = {hospital["participating"] for hospital in hospitals}
    assert flags == {True, False}, "both participating and non-participating expected"
    participating = {h["name"] for h in hospitals if h["participating"]}
    assert any("Tübingen" in name for name in participating)
