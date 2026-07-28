import pytest

from apps.fortunes.models import Fortune


@pytest.fixture(autouse=True)
def _reset_seeded_fortunes(db):
    """Data migrations seed the real 六十甲子籤 content into SIXTY_JIAZI.

    Tests build their own throwaway Fortune rows (often reusing numbers like
    1-4) against that same default set, so clear the seeded rows first to
    avoid colliding with the (fortune_set, number) unique constraint.
    """
    Fortune.objects.all().delete()
