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

from .models import Message

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
