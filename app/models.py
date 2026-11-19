"""CampusEvent 数据模型与领域常量定义。

本模块定义领域对象（Student / Activity / Registration / Message）的字段与状态，
以及报名状态、报名方式等枚举常量。持久化由 db.py 通过 SQLite 完成。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class PolicyType(str, Enum):
    """报名方式：直接报名 / 管理员审核。"""

    DIRECT = "direct"
    REVIEW = "review"


class RegistrationStatus(str, Enum):
    """报名状态，符合 B.2 业务规则的状态集合。"""

    PENDING = "pending"     # 待审核
    APPROVED = "approved"   # 已通过
    REJECTED = "rejected"   # 已拒绝
    CANCELLED = "cancelled" # 已取消


# 同一学生对同一活动不得存在两条“待审核”或“已通过”的有效报名。
ACTIVE_STATUSES = (RegistrationStatus.PENDING, RegistrationStatus.APPROVED)


@dataclass
class Student:
    """学生。"""

    student_id: str
    name: str


@dataclass
class Activity:
    """活动。"""

    activity_id: int
    title: str
    category: str
    start_at: datetime
    location: str
    capacity: int          # 容量为正整数
    policy_type: PolicyType


@dataclass
class Registration:
    """报名记录。"""

    registration_id: int
    activity_id: int
    student_id: str
    status: RegistrationStatus
    created_at: datetime
    updated_at: datetime


@dataclass
class Message:
    """站内消息。"""

    message_id: int
    student_id: str
    activity_id: int
    content: str
    created_at: datetime
    is_read: bool = False
