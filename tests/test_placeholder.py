from eventindex.extract import is_placeholder_title


def test_venue_name_plus_generic_is_placeholder():
    assert is_placeholder_title("Sandburg Events", "Sandburg Linz")
    assert is_placeholder_title("Veranstaltungen im Smaragd", "CulturCafé Smaragd")
    assert is_placeholder_title("Termine", "Posthof")
    assert is_placeholder_title("", "X")


def test_real_titles_survive():
    assert not is_placeholder_title("Sommerfest im Smaragd", "CulturCafé Smaragd")
    assert not is_placeholder_title("Queen'z Garden LIVE", "Sandburg Linz")
    assert not is_placeholder_title("Klassik am Dom: Tom Jones", "Klassik am Dom")
    assert not is_placeholder_title("Flohmarkt der Stadtbibliothek", "Stadtbibliothek Linz")
