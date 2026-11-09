import pytest
from letterboxdpy.core.exceptions import AccessDeniedError
from plugins.letterboxd import Letterboxd

# Test data as fixtures
@pytest.fixture
def test_list_output():
    return [
        {'title': 'The Godfather', 'media_type': 'movie', 'imdb_id': 'tt0068646', 'release_year': '1972'},
        {'title': 'The Godfather Part II', 'media_type': 'movie', 'imdb_id': 'tt0071562', 'release_year': '1974'}
    ]

# Parametrized test for different lists
@pytest.mark.parametrize("test_list", [
    "jf_auto_collect/watchlist",
    "jf_auto_collect/list/test_list/"
])
def test_get_list(test_list, test_list_output):
    try:
        result = Letterboxd.get_list(test_list, {"imdb_id_filter": True})
    except AccessDeniedError as e:
        # Letterboxd blocks requests from some IP ranges (e.g. CI runners)
        pytest.skip(f"Letterboxd blocked the request: {e}")

    assert result["items"] == test_list_output


def test_likes_list_not_supported():
    with pytest.raises(NotImplementedError):
        Letterboxd.get_list("jf_auto_collect/likes/films", {"imdb_id_filter": True})
