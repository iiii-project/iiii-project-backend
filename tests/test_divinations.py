import pytest
from django.db import IntegrityError

from apps.divinations.models import DivinationSession
from apps.divinations.serializers import BlockCastSerializer
from apps.divinations.services import block_result, cast_blocks, complete_prayer, create_session, draw_fortune
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
def test_non_sheng_requires_a_new_fortune_draw(session, fortune_set, monkeypatch):
    make_fortune(fortune_set)
    complete_prayer(session.session_uuid)
    draw_fortune(session.session_uuid)
    monkeypatch.setattr("apps.divinations.services.random.choice", lambda choices: "flat")

    cast = cast_blocks(session.session_uuid)
    session.refresh_from_db()

    assert cast.result == "xiao"
    assert session.fortune is None
    assert session.status == "drawing"
    assert session.block_casts.count() == 0
    monkeypatch.undo()
    assert draw_fortune(session.session_uuid).status == "waiting_for_blocks"


@pytest.mark.django_db
def test_one_sheng_result_confirms_session(session, fortune_set, monkeypatch):
    make_fortune(fortune_set)
    complete_prayer(session.session_uuid)
    draw_fortune(session.session_uuid)
    sides = iter(["flat", "round"])
    monkeypatch.setattr("apps.divinations.services.random.choice", lambda choices: next(sides))

    cast = cast_blocks(session.session_uuid)
    session.refresh_from_db()

    assert cast.result == "sheng"
    assert BlockCastSerializer(cast).data["remaining_attempts"] == 0
    assert session.confirmed is True
    assert session.status == "confirmed"


@pytest.mark.django_db
def test_create_session_accepts_fortune_number(fortune_set):
    fortune = make_fortune(fortune_set, number=8)

    session = create_session(
        fortune_set_code=fortune_set.code,
        question="最近適合換工作嗎？",
        category="career",
        interaction_mode="click",
        anonymous_user_id="guest",
        fortune_number=8,
    )

    assert session.fortune_id == fortune.id
    assert session.status == "confirmed"
    assert session.confirmed is True
