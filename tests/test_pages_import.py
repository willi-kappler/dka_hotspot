
import pytest


@pytest.mark.parametrize("module", [
    "pages.shared",
    "pages.login",
    "pages.overview",
    "pages.map_view",
    "pages.analysis",
    "pages.charts",
    "pages.data",
    "pages.admin",
])
def test_page_module_imports(module):
    __import__(module)


def test_every_route_the_header_links_to_is_registered():
    from nicegui import app

    import pages.admin  # noqa: F401
    import pages.analysis  # noqa: F401
    import pages.data  # noqa: F401
    import pages.map_view  # noqa: F401
    import pages.overview  # noqa: F401

    registered = {route.path for route in app.routes if hasattr(route, "path")}
    for path in ("/overview", "/map", "/analysis", "/data", "/admin/users"):
        assert path in registered, f"{path} is linked from the header but not registered"


def test_shared_helpers_format_percentages_and_intervals():
    from pages.shared import interval, percent

    assert percent(0.1234) == "12.3%"
    assert percent(0.1234, decimals=0) == "12%"
    assert percent(None) == "—"
    assert interval(0.10, 0.20) == "10.0–20.0%"
    assert interval(None, 0.2) == "—"


def test_research_pages_are_restricted_to_scientists_and_admins():
    from pages.shared import RESEARCH_ROLES

    assert RESEARCH_ROLES == {"scientist", "admin"}
    assert "user" not in RESEARCH_ROLES
