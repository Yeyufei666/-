"""报名策略（Strategy 模式）。

RegistrationPolicy 是稳定抽象；DirectPolicy / ReviewPolicy 是两种实现。
RegistrationService 依赖抽象（RegistrationPolicy），不在主流程中硬编码
活动类型判断。

设计理由（名额检查属于公共规则还是策略责任）：
名额检查（容量校验）属于“公共规则”，由 RegistrationService 统一执行，
而不是放进具体策略中。原因：
1. 无论直接报名还是审核报名，“已通过”人数不得超过容量”是全局不变量，
   两种策略都必须遵守，属于横切规则；
2. 审核型活动批准时需“再次检查名额”，若名额检查散落在各策略内部，
   批准路径难以复用同一套校验逻辑，容易产生不一致；
3. 把公共规则上移到 Service，策略只负责“决定提交后报名处于什么状态”，
   职责更单一，符合 SRP（单一职责）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import RegistrationStatus


class RegistrationPolicy(ABC):
    """报名策略抽象：决定一次新报名提交后的初始状态。"""

    @abstractmethod
    def initial_status(self) -> "RegistrationStatus":
        """返回新报名记录的初始状态。"""


class DirectPolicy(RegistrationPolicy):
    """直接报名策略：名额充足时直接通过。"""

    def initial_status(self) -> "RegistrationStatus":
        from .models import RegistrationStatus
        return RegistrationStatus.APPROVED


class ReviewPolicy(RegistrationPolicy):
    """审核报名策略：提交后进入待审核。"""

    def initial_status(self) -> "RegistrationStatus":
        from .models import RegistrationStatus
        return RegistrationStatus.PENDING


# 策略工厂：按活动报名方式返回对应策略实例
def policy_for(policy_type: str) -> RegistrationPolicy:
    from .models import PolicyType
    if PolicyType(policy_type) is PolicyType.DIRECT:
        return DirectPolicy()
    return ReviewPolicy()
