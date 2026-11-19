"""实验二初始版本核心验收用例 C1~C10。

覆盖指导书 3.5 节的 10 个验收用例，另加边界测试（重复报名、名额超限、
取消、审批冲突、通知解耦等 B.2 规则）。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.models import PolicyType, RegistrationStatus
from app.services import BusinessError


FUTURE = (datetime.now() + timedelta(days=7)).isoformat()


def _create_direct(services, capacity=2):
    return services["activity"].create_activity(
        title="校园歌手大赛",
        category="文体",
        start_at=datetime.fromisoformat(FUTURE),
        location="礼堂",
        capacity=capacity,
        policy_type=PolicyType.DIRECT,
    )


def _create_review(services, capacity=2):
    return services["activity"].create_activity(
        title="学术讲座",
        category="讲座",
        start_at=datetime.fromisoformat(FUTURE),
        location="报告厅",
        capacity=capacity,
        policy_type=PolicyType.REVIEW,
    )


def test_c1_create_direct_activity(services):
    a = _create_direct(services, capacity=2)
    assert a.activity_id > 0
    assert a.policy_type is PolicyType.DIRECT
    assert a.capacity == 2


def test_c2_direct_register_auto_approved(services):
    a = _create_direct(services, capacity=2)
    reg = services["registration"].register(a.activity_id, "S001")
    assert reg.status is RegistrationStatus.APPROVED
    # 生成站内通知
    msgs = services["registration"].list_messages("S001")
    assert any("成功报名" in m.content for m in msgs)


def test_c3_duplicate_active_registration_rejected(services):
    a = _create_direct(services, capacity=2)
    services["registration"].register(a.activity_id, "S001")
    with pytest.raises(BusinessError):
        services["registration"].register(a.activity_id, "S001")


def test_c4_capacity_limit(services):
    a = _create_direct(services, capacity=2)
    services["registration"].register(a.activity_id, "S001")
    services["registration"].register(a.activity_id, "S002")
    with pytest.raises(BusinessError):
        services["registration"].register(a.activity_id, "S003")


def test_c5_review_register_pending(services):
    a = _create_review(services, capacity=2)
    reg = services["registration"].register(a.activity_id, "S001")
    assert reg.status is RegistrationStatus.PENDING


def test_c6_approve_pending(services):
    a = _create_review(services, capacity=2)
    reg = services["registration"].register(a.activity_id, "S001")
    approved = services["registration"].approve(reg.registration_id)
    assert approved.status is RegistrationStatus.APPROVED
    msgs = services["registration"].list_messages("S001")
    assert any("通过" in m.content for m in msgs)


def test_c7_reject_pending(services):
    a = _create_review(services, capacity=2)
    reg = services["registration"].register(a.activity_id, "S001")
    rejected = services["registration"].reject(reg.registration_id)
    assert rejected.status is RegistrationStatus.REJECTED
    msgs = services["registration"].list_messages("S001")
    assert any("拒绝" in m.content for m in msgs)


def test_c8_approve_when_full(services):
    a = _create_review(services, capacity=1)
    r1 = services["registration"].register(a.activity_id, "S001")
    services["registration"].approve(r1.registration_id)  # 已占满名额
    r2 = services["registration"].register(a.activity_id, "S002")  # 待审核，不占名额
    with pytest.raises(BusinessError):
        services["registration"].approve(r2.registration_id)  # 批准时满员，失败


def test_c9_cancel_pending_or_approved(services):
    a = _create_direct(services, capacity=2)
    reg = services["registration"].register(a.activity_id, "S001")
    cancelled = services["registration"].cancel(a.activity_id, "S001")
    assert cancelled.status is RegistrationStatus.CANCELLED
    stats = services["activity"].statistics(a.activity_id)
    assert stats["approved"] == 0  # 统计同步变化


def test_c10_persistence(services):
    a = _create_direct(services, capacity=2)
    services["registration"].register(a.activity_id, "S001")
    # 通过重新读取数据库验证持久化（SQLite 落盘即持久）
    db = services["db"]
    assert db.get_activity(a.activity_id).title == "校园歌手大赛"
    assert db.count_status(a.activity_id, RegistrationStatus.APPROVED) == 1
    assert len(db.list_messages("S001")) == 1


# ---------- 边界测试 ----------
def test_register_after_start_rejected(services):
    past = datetime.now() - timedelta(days=1)
    a = services["activity"].create_activity(
        title="已开始活动", category="文体", start_at=past,
        location="礼堂", capacity=5, policy_type=PolicyType.DIRECT,
    )
    with pytest.raises(BusinessError):
        services["registration"].register(a.activity_id, "S001")


def test_reapply_after_cancel(services):
    a = _create_direct(services, capacity=2)
    services["registration"].register(a.activity_id, "S001")
    services["registration"].cancel(a.activity_id, "S001")
    # 取消后允许再次报名
    reg = services["registration"].register(a.activity_id, "S001")
    assert reg.status is RegistrationStatus.APPROVED


def test_capacity_positive(services):
    with pytest.raises(BusinessError):
        services["activity"].create_activity(
            title="x", category="x", start_at=datetime.fromisoformat(FUTURE),
            location="x", capacity=0, policy_type=PolicyType.DIRECT,
        )


import pytest
