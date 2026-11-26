# AI 开发过程记录（AI_DEV_LOG）

> 记录实验二中与 AI 协作的关键事件：重要提示词、设计决策、发现的问题与人工判断。

| 时间/版本 | 任务与发给 AI 的关键指令 | AI 产出与问题 | 学生判断/验证 |
|-----------|--------------------------|---------------|---------------|
| 2026-11-19 / baseline-v1 | 请依据实验二初始需求，先识别领域对象（Student/Activity/Registration/Message）与状态枚举，再设计数据表结构 | 生成 models.py 与 db.py，字段与 B.1 一致 | 核对 B.1 字段与约束，确认状态集合限"待审核/已通过/已拒绝/已取消" |
| 2026-11-19 / baseline-v1 | 用策略模式表达报名规则：定义 RegistrationPolicy 抽象，DirectPolicy/ReviewPolicy 两实现，RegistrationService 依赖抽象 | 生成 policies.py，但把名额检查也放进了策略内部 | 人工判断：名额检查是"公共规则"应上移到 Service 统一执行，让策略只决定初始状态，符合 SRP |
| 2026-11-19 / baseline-v1 | 用观察者/事件分发解耦报名业务与站内通知 | 生成 notifications.py（EventDispatcher + InboxNotificationListener） | 确认通知失败仅留日志不回滚报名，满足 B.2 规则6 |
| 2026-11-19 / baseline-v1 | 实现 register 业务：校验活动存在/未开始/无重复/名额，再决定初始状态 | 首次实现对所有活动在提交时都检查名额 | 发现 bug：审核型活动提交时名额满会被拒，但待审核不应占名额。修正为仅直接报名提交时检查、批准时再检查 |
| 2026-11-19 / baseline-v1 | 编写 pytest 覆盖 C1~C10 | 通知监听器构造 Message 缺 message_id 报错 | 定位到 dataclass 必填字段，补默认值 0 修复 |
| 2026-11-19 / baseline-v1 | 运行全部测试 | 16 个测试通过（C1~C10 + 5 边界） | 复核验收用例覆盖完整，统计、持久化、审批冲突均验证通过 |
| 2026-11-26 / change-v2 | 接收 CR-01：Activity 支持年级限定直接报名，Student 新增 grade，仅大二大三可报名 | 提出新增 GradeDirectPolicy 策略 | 确认采用"新增独立策略 + 工厂加分支"，不修改 register 主流程，符合 OCP；年级校验放策略内、公共约束留在 Service |
| 2026-11-26 / change-v2 | 接收 CR-02：新增模拟邮件通知（MockEmailSender） | 生成 EmailNotificationListener + MockEmailSender | 确认沿用观察者模式新增监听器，邮件失败留痕不回滚报名；取消事件不触发邮件 |
| 2026-11-26 / change-v2 | 策略接口需基于学生属性判断 | 需把 initial_status() 扩展为 decide(student) | 判断：接口扩展是必要的（年级策略需读 Student.grade），属合理演进 |
| 2026-11-26 / change-v2 | 编写 CR1/CR2 测试并回归 | 27 个测试全部通过（新增 11 CR/边界 + C1~C10 回归） | 确认 CR1-05、CR2-05"原有用例保持通过"满足 |

## 关键设计决策（人工）

1. **名额检查归属**：名额检查是公共规则，上移到 `RegistrationService`，策略只负责初始状态。
2. **事务边界**：报名落库与通知分两步，通知失败留痕不回滚报名。
3. **软删除活动**：删除活动采用软删除，保留报名历史（B.2 规则7）。
4. **CR-01 采用新增策略**：年级限定新增 `GradeDirectPolicy`，不修改 `register` 主流程。
5. **CR-02 采用新增监听器**：邮件通知新增 `EmailNotificationListener`，不把邮件代码写入 `RegistrationService`。
