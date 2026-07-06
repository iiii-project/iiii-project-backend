import random

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.fortunes.models import FortuneSet

from .models import BlockCast, DivinationSession

MAX_BLOCK_CAST_ATTEMPTS = 3


class DomainError(APIException):
    status_code = 400
    default_code = "INVALID_REQUEST"

    def __init__(self, code: str, message: str, status_code: int = 400):
        self.status_code = status_code
        self.detail = message
        self.default_code = code


def create_session(*, fortune_set_code: str, question: str, category: str, interaction_mode: str, anonymous_user_id: str):
    try:
        fortune_set = FortuneSet.objects.get(code=fortune_set_code, is_active=True)
    except FortuneSet.DoesNotExist as exc:
        raise DomainError("FORTUNE_SET_NOT_FOUND", "找不到可用籤系", 404) from exc

    return DivinationSession.objects.create(
        fortune_set=fortune_set,
        question=question,
        category=category,
        interaction_mode=interaction_mode,
        anonymous_user_id=anonymous_user_id,
    )


@transaction.atomic
def complete_prayer(session_uuid: str) -> DivinationSession:
    session = DivinationSession.objects.select_for_update().get(session_uuid=session_uuid)
    if session.status not in {"created", "praying"}:
        raise DomainError("INVALID_SESSION_STATE", "目前狀態不可完成祈求", 409)
    session.status = "drawing"
    session.save(update_fields=["status", "updated_at"])
    return session


@transaction.atomic
def draw_fortune(session_uuid: str) -> DivinationSession:
    session = DivinationSession.objects.select_for_update().get(session_uuid=session_uuid)
    if session.fortune_id:
        return session
    if session.status != "drawing":
        raise DomainError("INVALID_SESSION_STATE", "目前狀態不可抽籤", 409)

    fortune_ids = list(session.fortune_set.fortunes.filter(is_active=True).values_list("id", flat=True))
    if not fortune_ids:
        raise DomainError("FORTUNE_DATA_UNAVAILABLE", "目前籤系沒有可用籤詩", 409)

    session.fortune_id = random.choice(fortune_ids)
    session.status = "waiting_for_blocks"
    session.save(update_fields=["fortune", "status", "updated_at"])
    return session


def block_result(block_one: str, block_two: str) -> str:
    if block_one == block_two == "flat":
        return "xiao"
    if block_one == block_two == "round":
        return "yin"
    return "sheng"


@transaction.atomic
def cast_blocks(session_uuid: str) -> BlockCast:
    session = DivinationSession.objects.select_for_update().get(session_uuid=session_uuid)
    if session.status != "waiting_for_blocks":
        raise DomainError("INVALID_SESSION_STATE", "目前狀態不可擲筊", 409)
    if session.confirmed:
        raise DomainError("INVALID_SESSION_STATE", "已取得聖筊，不可再次擲筊", 409)

    attempt_number = session.block_casts.count() + 1
    if attempt_number > MAX_BLOCK_CAST_ATTEMPTS:
        raise DomainError("BLOCK_CAST_LIMIT_REACHED", "擲筊次數已達上限", 409)

    block_one = random.choice(["flat", "round"])
    block_two = random.choice(["flat", "round"])
    result = block_result(block_one, block_two)
    cast = BlockCast.objects.create(
        divination_session=session,
        attempt_number=attempt_number,
        block_one=block_one,
        block_two=block_two,
        result=result,
    )

    if result == "sheng":
        session.confirmed = True
        session.status = "confirmed"
        session.save(update_fields=["confirmed", "status", "updated_at"])
    elif attempt_number == MAX_BLOCK_CAST_ATTEMPTS:
        session.status = "rejected"
        session.completed_at = timezone.now()
        session.save(update_fields=["status", "completed_at", "updated_at"])

    return cast
