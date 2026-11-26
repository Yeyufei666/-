"""实验二需求变更 CR-01 / CR-02 测试。

CR-01：年级限定报名（GradeDirectPolicy）
CR-02：邮件通知（EmailNotificationListener + MockEmailSender）
以及变更后回归 C1~C10（原有用例保持通过）。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models import PolicyType, RegistrationStatus
from app.services import BusinessError


FUTURE = (datetime.now() + timedelta(days=7)).isoformat()


def _add_student(services, sid, name, grade):
    services["db"].add_student(sid, name, grade)


def _create_grade_activity(services, capacity=2):
    return services["activity"].create_activity(
        title="大二大三限定讲座",
        category="讲座",
        start_at=datetime.fromisoformat(FUTURE),
        location="报告厅",
        capacity=capacity,
        policy_type=PolicyType.GRADE_DIRECT,
    )


def _create_direct(services, capacity=2):
    return services["activity"].create_activity(
        title="校园歌手大赛", category="文体",
        start_at=datetime.fromisoformat(FUTURE), location="礼堂",
        capacity=capacity, policy_type=PolicyType.DIRECT,
    )


def _create_review(services, capacity=2):
    return services["activity"].create_activity(
        title="学术讲座", category="讲座",
        start_at=datetime.fromisoformat(FUTURE), location="报告厅",
        capacity=capacity, policy_type=PolicyType.REVIEW,
    )


# ---------- CR-01：年级限定报名 ----------

def test_cr1_01_grade2_allowed(services):
    a = _create_grade_activity(services)
    _add_student(services, "S201", "大二学生", grade=2)
    reg = services["registration"].register(a.activity_id, "S201")
    assert reg.status is RegistrationStatus.APPROVED


def test_cr1_02_grade3_allowed(services):
    a = _create_grade_activity(services)
    _add_student(services, "S301", "大三学生", grade=3)
    reg = services["registration"].register(a.activity_id, "S301")
    assert reg.status is RegistrationStatus.APPROVED


def test_cr1_03_grade1_rejected(services):
    a = _create_grade_activity(services)
    _add_student(services, "S101", "大一学生", grade=1)
    with pytest.raises(BusinessError) as exc:
        services["registration"].register(a.activity_id, "S101")
    assert "仅面向大二、大三" in str(exc.value)  # 明确提示原因


def test_cr1_04_grade4_rejected(services):
    a = _create_grade_activity(services)
    _add_student(services, "S401", "大四学生", grade=4)
    with pytest.raises(BusinessError) as exc:
        services["registration"].register(a.activity_id, "S401")
    assert "仅面向大二、大三" in str(exc.value)


def test_cr1_grade_activity_respects_capacity(services):
    """年级限定活动同样遵守名额限制（公共约束）。"""
    a = _create_grade_activity(services, capacity=1)
    _add_student(services, "S201", "大二学生", grade=2)
    _add_student(services, "S202", "大二学生B", grade=2)
    services["registration"].register(a.activity_id, "S201")
    with pytest.raises(BusinessError):
        services["registration"].register(a.activity_id, "S202")


def test_cr1_grade_activity_respects_duplicate(services):
    """年级限定活动同样禁止重复有效报名。"""
    a = _create_grade_activity(services)
    _add_student(services, "S201", "大二学生", grade=2)
    services["registration"].register(a.activity_id, "S201")
    with pytest.raises(BusinessError):
        services["registration"].register(a.activity_id, "S201")


def test_cr1_original_direct_review_unchanged(services):
    """CR1-05 的一部分：原有 direct/review 行为不变。"""
    a = _create_direct(services)
    _add_student(services, "S101", "大一学生", grade=1)
    reg = services["registration"].register(a.activity_id, "S101")
    assert reg.status is RegistrationStatus.APPROVED  # 普通直接报名不受年级限制


# ---------- CR-02：邮件通知 ----------

def test_cr2_01_direct_register_sends_email(services):
    a = _create_direct(services)
    _add_student(services, "S001", "学生", grade=2)
    services["registration"].register(a.activity_id, "S001")
    emails = services["db"].list_email_records("S001")
    assert len(emails) == 1
    assert emails[0].status == "sent"
    # 站内消息也有记录
    assert len(services["registration"].list_messages("S001")) == 1


def test_cr2_02_approve_reject_send_email(services):
    a = _create_review(services)
    _add_student(services, "S001", "学生", grade=2)
    _add_student(services, "S002", "学生B", grade=2)
    r1 = services["registration"].register(a.activity_id, "S001")
    r2 = services["registration"].register(a.activity_id, "S002")
    services["registration"].approve(r1.registration_id)
    services["registration"].reject(r2.registration_id)
    emails = services["db"].list_email_records("S001")
    # 提交（submitted）+ 批准（approved）各一封
    assert len(emails) == 2
    emails2 = services["db"].list_email_records("S002")
    # 提交 + 拒绝各一封
    assert len(emails2) == 2


def test_cr2_03_email_failure_does_not_rollback(app, tmp_path):
    """邮件发送失败时报名状态正确、错误有日志。"""
    import os
    db_path = os.path.join(tmp_path, "fail.db")
    fail_app = create_app_with_failure(db_path)
    services = {
        "activity": fail_app.extensions["activity_service"],
        "registration": fail_app.extensions["registration_service"],
        "db": fail_app.extensions["db"],
    }
    a = _create_direct(services)
    services["db"].add_student("S001", "学生", grade=2)
    reg = services["registration"].register(a.activity_id, "S001")
    # 报名成功（状态正确）
    assert reg.status is RegistrationStatus.APPROVED
    # 邮件记录为 failed，且记录了错误
    emails = services["db"].list_email_records("S001")
    assert len(emails) == 1
    assert emails[0].status == "failed"
    assert emails[0].error
    # 站内消息仍正常（通知不回滚）
    assert len(services["registration"].list_messages("S001")) == 1


def test_cr2_04_no_duplicate_notifications(services):
    """同一业务动作不重复生成多份通知。"""
    a = _create_direct(services)
    _add_student(services, "S001", "学生", grade=2)
    services["registration"].register(a.activity_id, "S001")
    emails = services["db"].list_email_records("S001")
    msgs = services["registration"].list_messages("S001")
    assert len(emails) == 1
    assert len(msgs) == 1


def create_app_with_failure(db_path):
    from app import create_app
    return create_app({"db_path": db_path, "email_failure": True})
