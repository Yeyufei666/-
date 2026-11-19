"""业务服务层。

ActivityService：活动管理（创建/编辑/删除/查看/统计）。
RegistrationService：报名业务核心，依赖 RegistrationPolicy 抽象，
                     并通过 EventDispatcher 解耦通知。

关键业务规则（B.2）在此集中实现：
- 名额按“已通过”报名计算，待审核不占用名额；
- 同一学生对同一活动不得有两条有效报名（待审核/已通过）；
- 已取消/已拒绝保留历史，允许再次申请；
- 活动开始后不允许新增报名；
- 批准时再次检查剩余名额。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from .models import (
    Activity,
    PolicyType,
    Registration,
    RegistrationStatus,
    ACTIVE_STATUSES,
)
from .notifications import EventDispatcher, RegistrationEvent
from .policies import RegistrationPolicy, policy_for


class BusinessError(Exception):
    """业务规则违反异常，携带面向用户的提示。"""


class ActivityService:
    """活动管理。"""

    def __init__(self, db):
        self._db = db

    def create_activity(
        self,
        title: str,
        category: str,
        start_at: datetime,
        location: str,
        capacity: int,
        policy_type: PolicyType,
    ) -> Activity:
        if capacity <= 0:
            raise BusinessError("活动容量必须为正整数")
        if not title or not title.strip():
            raise BusinessError("活动名称不能为空")
        activity = Activity(
            activity_id=0,
            title=title.strip(),
            category=category,
            start_at=start_at,
            location=location,
            capacity=capacity,
            policy_type=policy_type,
        )
        return self._db.add_activity(activity)

    def get_activity(self, activity_id: int) -> Optional[Activity]:
        return self._db.get_activity(activity_id)

    def list_activities(self, title_filter: str = "") -> list[Activity]:
        return self._db.list_activities(title_filter)

    def update_activity(self, activity: Activity) -> None:
        self._db.update_activity(activity)

    def delete_activity(self, activity_id: int) -> None:
        """删除活动：采用软删除，保留报名历史记录（B.2 规则7）。"""
        self._db.soft_delete_activity(activity_id)

    def statistics(self, activity_id: int) -> dict:
        """按活动返回已通过数、待审核数和剩余名额。"""
        activity = self._db.get_activity(activity_id)
        if activity is None:
            raise BusinessError("活动不存在")
        approved = self._db.count_status(activity_id, RegistrationStatus.APPROVED)
        pending = self._db.count_status(activity_id, RegistrationStatus.PENDING)
        remaining = activity.capacity - approved
        return {
            "activity_id": activity_id,
            "capacity": activity.capacity,
            "approved": approved,
            "pending": pending,
            "remaining": max(remaining, 0),
        }


class RegistrationService:
    """报名业务核心。依赖抽象策略 + 事件分发。"""

    def __init__(self, db, dispatcher: EventDispatcher):
        self._db = db
        self._dispatcher = dispatcher

    def _activity_or_raise(self, activity_id: int) -> Activity:
        activity = self._db.get_activity(activity_id)
        if activity is None:
            raise BusinessError("活动不存在")
        return activity

    def _policy_for(self, activity: Activity) -> RegistrationPolicy:
        return policy_for(activity.policy_type.value)

    def _check_capacity(self, activity: Activity) -> None:
        """公共规则：名额按“已通过”计算，满员则拒绝。"""
        approved = self._db.count_status(activity.activity_id, RegistrationStatus.APPROVED)
        if approved >= activity.capacity:
            raise BusinessError("活动名额已满")

    def register(self, activity_id: int, student_id: str) -> Registration:
        """学生报名。

        公共规则（对所有策略一致）：
        1. 活动存在；
        2. 活动开始前允许报名；
        3. 无重复有效报名；
        4. 名额充足（按已通过计算）。

        策略差异：决定报名初始状态（直接通过 / 待审核）。
        """
        activity = self._activity_or_raise(activity_id)

        if datetime.now() >= activity.start_at:
            raise BusinessError("活动已开始，不允许报名")

        existing = self._db.find_active_registration(activity_id, student_id)
        if existing is not None:
            raise BusinessError("您已报名该活动，请勿重复报名")

        policy = self._policy_for(activity)
        status = policy.initial_status()

        # 名额检查仅对“直接报名”在提交时执行：
        # 直接报名提交即通过、占用名额，须在此校验；
        # 审核报名提交后为“待审核”，暂不占用名额，故提交时不校验，
        # 名额在批准时（approve）再次检查，避免满员仍可提交审核的歧义。
        if status is RegistrationStatus.APPROVED:
            self._check_capacity(activity)
        now = datetime.now()
        registration = Registration(
            registration_id=0,
            activity_id=activity_id,
            student_id=student_id,
            status=status,
            created_at=now,
            updated_at=now,
        )
        self._db.add_registration(registration)

        # 解耦通知：发布领域事件
        if status is RegistrationStatus.APPROVED:
            content = f"您已成功报名活动「{activity.title}」"
        else:
            content = f"您的报名申请已提交，活动「{activity.title}」等待管理员审核"
        self._dispatcher.publish(
            RegistrationEvent(
                event_type="submitted",
                student_id=student_id,
                activity_id=activity_id,
                activity_title=activity.title,
                content=content,
            )
        )
        return registration

    def cancel(self, activity_id: int, student_id: str) -> Registration:
        """学生取消自己的待审核/已通过报名。"""
        registration = self._db.find_active_registration(activity_id, student_id)
        if registration is None:
            raise BusinessError("没有可取消的有效报名")
        self._db.update_registration_status(
            registration.registration_id, RegistrationStatus.CANCELLED
        )
        activity = self._activity_or_raise(activity_id)
        self._dispatcher.publish(
            RegistrationEvent(
                event_type="cancelled",
                student_id=student_id,
                activity_id=activity_id,
                activity_title=activity.title,
                content=f"您已取消活动「{activity.title}」的报名",
            )
        )
        return self._db.get_registration(registration.registration_id)

    def approve(self, registration_id: int) -> Registration:
        """管理员批准待审核报名，批准时再次检查名额。"""
        registration = self._db.get_registration(registration_id)
        if registration is None:
            raise BusinessError("报名记录不存在")
        if registration.status is not RegistrationStatus.PENDING:
            raise BusinessError("仅待审核的报名可被批准")

        activity = self._activity_or_raise(registration.activity_id)
        # 批准时再次检查剩余名额
        self._check_capacity(activity)

        self._db.update_registration_status(registration_id, RegistrationStatus.APPROVED)
        self._dispatcher.publish(
            RegistrationEvent(
                event_type="approved",
                student_id=registration.student_id,
                activity_id=activity.activity_id,
                activity_title=activity.title,
                content=f"您报名活动「{activity.title}」的申请已通过",
            )
        )
        return self._db.get_registration(registration_id)

    def reject(self, registration_id: int) -> Registration:
        """管理员拒绝待审核报名。"""
        registration = self._db.get_registration(registration_id)
        if registration is None:
            raise BusinessError("报名记录不存在")
        if registration.status is not RegistrationStatus.PENDING:
            raise BusinessError("仅待审核的报名可被拒绝")

        activity = self._activity_or_raise(registration.activity_id)
        self._db.update_registration_status(registration_id, RegistrationStatus.REJECTED)
        self._dispatcher.publish(
            RegistrationEvent(
                event_type="rejected",
                student_id=registration.student_id,
                activity_id=activity.activity_id,
                activity_title=activity.title,
                content=f"您报名活动「{activity.title}」的申请被拒绝",
            )
        )
        return self._db.get_registration(registration_id)

    def list_registrations(self, activity_id: int) -> list[Registration]:
        return self._db.list_registrations(activity_id)

    def list_messages(self, student_id: str):
        return self._db.list_messages(student_id)
