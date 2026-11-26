"""通知机制（观察者 / 事件分发模式）。

将“报名事件”与“站内通知写入”解耦：业务层只发布领域事件，
站内通知监听器订阅事件并负责写入 Message。

设计理由：
1. 解耦：RegistrationService 不直接依赖通知写入逻辑，新增通知渠道
   （邮件、短信）时只需新增监听器，无需改动业务主流程；
2. 事务边界：通知失败应“留痕”但不得导致已合法提交的报名记录丢失。
   因此通知与报名分属两个事务——报名提交先落库成功，再异步/容错地
   派发通知；通知写入失败时记录日志（留痕），不影响报名结果；
3. 避免重复通知：事件派发具备幂等性，每个业务动作只发布一次对应事件，
   监听器按事件消费，不会重复写入同一条消息。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, List

from .models import EmailRecord, Message

logger = logging.getLogger(__name__)


@dataclass
class RegistrationEvent:
    """报名领域事件。"""

    event_type: str  # "submitted" / "approved" / "rejected" / "cancelled"
    student_id: str
    activity_id: int
    activity_title: str
    content: str
    occurred_at: datetime = field(default_factory=datetime.now)


# 事件监听器签名：接收 Database + RegistrationEvent
Listener = Callable[[object, RegistrationEvent], None]


class EventDispatcher:
    """轻量级事件分发器（观察者模式核心）。"""

    def __init__(self) -> None:
        self._listeners: List[Listener] = []

    def subscribe(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def publish(self, event: RegistrationEvent) -> None:
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as exc:  # 通知失败留痕，不向上抛出影响业务
                logger.error("通知监听器处理事件失败: %s", exc)


class InboxNotificationListener:
    """站内通知监听器：把报名事件落库为站内消息。"""

    def __init__(self, db) -> None:
        self._db = db

    def __call__(self, event: RegistrationEvent) -> None:
        self._db.add_message(
            Message(
                message_id=0,
                student_id=event.student_id,
                activity_id=event.activity_id,
                content=event.content,
                created_at=event.occurred_at,
                is_read=False,
            )
        )


class MockEmailSender:
    """模拟邮件发送器（CR-02）。

    不接入真实邮件服务器，而是把“发送动作”记录到数据库（收件人/主题/内容/状态/时间），
    便于教学演示与测试断言。可注入 failure 开关模拟发送失败。
    """

    def __init__(self, db, failure: bool = False) -> None:
        self._db = db
        self._failure = failure  # True 时模拟发送失败

    def send(self, to: str, subject: str, body: str) -> EmailRecord:
        if self._failure:
            record = EmailRecord(
                email_id=0,
                student_id=to,
                subject=subject,
                content=body,
                status="failed",
                error="模拟邮件发送失败（网络异常）",
                created_at=datetime.now(),
            )
            self._db.add_email_record(record)
            raise RuntimeError("模拟邮件发送失败")
        record = EmailRecord(
            email_id=0,
            student_id=to,
            subject=subject,
            content=body,
            status="sent",
            error="",
            created_at=datetime.now(),
        )
        self._db.add_email_record(record)
        return record


class EmailNotificationListener:
    """邮件通知监听器（CR-02）。

    订阅报名事件，对“报名通过 / 审核通过 / 审核拒绝”三类事件同步发送模拟邮件。
    邮件发送失败时记录错误日志（留痕），但不向上抛出，保证不回滚已成功的报名。
    """

    # 需要邮件通知的事件类型
    NOTIFY_TYPES = {"submitted", "approved", "rejected"}

    def __init__(self, sender: MockEmailSender) -> None:
        self._sender = sender

    def __call__(self, event: RegistrationEvent) -> None:
        if event.event_type not in self.NOTIFY_TYPES:
            return  # 取消等事件不触发邮件
        subject = f"活动通知：{event.activity_title}"
        try:
            self._sender.send(event.student_id, subject, event.content)
        except Exception as exc:
            # 邮件失败仅记录错误，不影响报名业务
            logger.error("邮件发送失败（student=%s）: %s", event.student_id, exc)
