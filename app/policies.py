"""报名策略（Strategy 模式）。

RegistrationPolicy 是稳定抽象；DirectPolicy / ReviewPolicy / GradeDirectPolicy 是三种实现。
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

CR-01 设计理由（为什么新增独立策略 GradeDirectPolicy）：
年级限定是“报名资格”层面的差异，与 direct/review 同属“报名规则”的变化维度。
新增一个策略子类即可，无需改动 RegistrationService 的核心 register 流程，
符合开闭原则（OCP）。年级资格校验放在策略内部（它属于策略自身特有的规则），
而名额、开始时间、重复报名等仍是公共约束，由 Service 统一执行。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import RegistrationStatus, Student


class RegistrationPolicy(ABC):
    """报名策略抽象：决定一次新报名提交后的初始状态。

    decide(student) 接收学生对象，允许策略基于学生属性（如年级）做资格判断。
    """

    @abstractmethod
    def decide(self, student: "Student") -> "RegistrationStatus":
        """根据学生信息决定报名初始状态；不符合资格时抛 BusinessError。"""


class DirectPolicy(RegistrationPolicy):
    """直接报名策略：名额充足时直接通过。"""

    def decide(self, student: "Student") -> "RegistrationStatus":
        from .models import RegistrationStatus
        return RegistrationStatus.APPROVED


class ReviewPolicy(RegistrationPolicy):
    """审核报名策略：提交后进入待审核。"""

    def decide(self, student: "Student") -> "RegistrationStatus":
        from .models import RegistrationStatus
        return RegistrationStatus.PENDING


class GradeDirectPolicy(RegistrationPolicy):
    """年级限定直接报名策略（CR-01）。

    仅年级 grade ∈ {2, 3} 的学生可报名；其他年级抛出明确提示。
    通过即“已通过”，后续名额检查等公共约束仍由 Service 执行。
    """

    ALLOWED_GRADES = {2, 3}

    def decide(self, student: "Student") -> "RegistrationStatus":
        from .errors import BusinessError
        from .models import RegistrationStatus
        if student.grade not in self.ALLOWED_GRADES:
            raise BusinessError(
                f"本活动仅面向大二、大三学生开放，您当前为{_grade_name(student.grade)}，暂不符合报名条件"
            )
        return RegistrationStatus.APPROVED


def _grade_name(grade: int) -> str:
    names = {1: "大一", 2: "大二", 3: "大三", 4: "大四"}
    return names.get(grade, f"年级{grade}")


# 策略工厂：按活动报名方式返回对应策略实例
def policy_for(policy_type: str) -> RegistrationPolicy:
    from .models import PolicyType
    ptype = PolicyType(policy_type)
    if ptype is PolicyType.DIRECT:
        return DirectPolicy()
    if ptype is PolicyType.GRADE_DIRECT:
        return GradeDirectPolicy()
    return ReviewPolicy()
