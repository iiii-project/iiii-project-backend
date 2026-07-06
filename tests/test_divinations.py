import pytest
from django.db import IntegrityError

from apps.divinations.models import DivinationSession
from apps.divinations.services import block_result, cast_blocks, complete_prayer, draw_fortune
from apps.fortunes.models import Fortune, FortuneSet


@pytest.fixture
def fortune_set(db):
    return FortuneSet.objects.get(code="SIXTY_JIAZI")


@pytest.fixture
def session(fortune_set):
    return DivinationSession.objects.create(
        fortune_set=fortune_set,
        question="最近適合換工作嗎？",
        category="career",
        interaction_mode="click",
    )


def make_fortune(fortune_set, number=1, active=True):
    return Fortune.objects.create(
        fortune_set=fortune_set,
        number=number,
        poem=f"第{number}首",
        is_active=active,
    )


@pytest.mark.django_db
def test_draw_uses_active_fortunes_only(session, fortune_set):
    inactive = make_fortune(fortune_set, number=1, active=False)
    active = make_fortune(fortune_set, number=2, active=True)

    complete_prayer(session.session_uuid)
    result = draw_fortune(session.session_uuid)

    assert result.fortune_id == active.id
    assert result.fortune_id != inactive.id
    assert result.status == "waiting_for_blocks"


@pytest.mark.django_db
def test_draw_is_idempotent(session, fortune_set):
    make_fortune(fortune_set)
    complete_prayer(session.session_uuid)

    first = draw_fortune(session.session_uuid)
    second = draw_fortune(session.session_uuid)

    assert second.fortune_id == first.fortune_id


@pytest.mark.django_db
def test_fortune_number_unique_in_set(fortune_set):
    make_fortune(fortune_set)

    with pytest.raises(IntegrityError):
        make_fortune(fortune_set)


def test_block_result_mapping():
    assert block_result("flat", "round") == "sheng"
    assert block_result("round", "flat") == "sheng"
    assert block_result("flat", "flat") == "xiao"
    assert block_result("round", "round") == "yin"


@pytest.mark.django_db
def test_block_cast_limit(session, fortune_set, monkeypatch):
    make_fortune(fortune_set)
    complete_prayer(session.session_uuid)
    draw_fortune(session.session_uuid)
    monkeypatch.setattr("apps.divinations.services.random.choice", lambda choices: "flat")

    cast_blocks(session.session_uuid)
    cast_blocks(session.session_uuid)
    third = cast_blocks(session.session_uuid)
    session.refresh_from_db()

    assert third.attempt_number == 3
    assert session.status == "rejected"
