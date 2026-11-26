# CampusEvent 校园活动报名与管理系统

基于设计模式的校园活动报名与管理系统（实验二）。学生主导设计，AI 辅助实现，支持"直接报名""管理员审核""年级限定直接报名"三类活动，通过策略模式与观察者模式实现可维护、可扩展的软件结构。

> 变更说明：`baseline-v1` 为初始验收版本；`change-v2` 实现了教师发布的 CR-01（年级限定报名）与 CR-02（邮件通知）。

## 技术栈

- Python 3.11+
- Flask（Web 框架）
- SQLite（持久化）
- pytest（自动化测试）

## 功能特性

| 编号 | 功能 | 说明 |
|------|------|------|
| P2-F01 | 活动管理 | 管理员创建、编辑、删除活动 |
| P2-F02 | 活动查看 | 学生浏览列表与详情，按名称筛选 |
| P2-F03 | 报名/取消 | 报名、取消；禁止重复有效报名 |
| P2-F04 | 报名策略 | 直接报名自动通过；审核型进入待审核；年级限定型仅大二/大三可报 |
| P2-F05 | 审批操作 | 批准/拒绝，批准时再次检查名额 |
| P2-F06 | 状态管理 | 待审核/已通过/已拒绝/已取消 |
| P2-F07 | 站内通知 | 报名及审核结果写入站内消息 |
| P2-F08 | 统计 | 已通过数、待审核数、剩余名额 |
| CR-01 | 年级限定报名 | Student 新增 grade 字段，仅 grade∈{2,3} 可报名年级限定活动 |
| CR-02 | 邮件通知 | 报名通过/审核通过/拒绝同步发模拟邮件，失败留痕不回滚 |

## 项目结构

```
CampusEvent/
├── app/
│   ├── __init__.py        # 应用工厂
│   ├── models.py          # 领域对象与枚举
│   ├── db.py              # SQLite 数据访问层
│   ├── policies.py        # 策略模式（报名规则）
│   ├── notifications.py   # 观察者/事件分发（站内通知）
│   ├── services.py        # 业务服务层
│   ├── views.py           # Flask 路由
│   └── templates/
│       └── index.html     # 管理界面
├── tests/
│   ├── conftest.py        # 测试夹具
│   ├── test_registration.py  # 验收用例 C1~C10 + 边界
│   └── test_api.py        # API 冒烟测试
├── docs/                  # 设计文档、UML、变更分析
├── run.py                 # 启动入口
├── requirements.txt
└── AI_DEV_LOG.md
```

## 从零开始运行

### 1. 环境准备

```bash
# 创建虚拟环境
python -m venv .venv
# 激活（Windows）
.venv\Scripts\activate
# 激活（macOS/Linux）
source .venv/bin/activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 启动服务

```bash
python run.py
```

浏览器访问 http://127.0.0.1:5000 打开管理界面。

### 4. 运行测试

```bash
python -m pytest tests/ -v
```

## API 说明

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/activities | 活动列表（支持 ?title= 筛选） |
| POST | /api/activities | 创建活动 |
| GET | /api/activities/{id}/stats | 活动统计 |
| POST | /api/activities/{id}/register | 学生报名 |
| POST | /api/activities/{id}/cancel | 取消报名 |
| POST | /api/registrations/{id}/approve | 批准报名 |
| POST | /api/registrations/{id}/reject | 拒绝报名 |
| GET | /api/activities/{id}/registrations | 报名列表 |
| GET | /api/students/{id}/messages | 站内消息 |

## 设计说明

详见 `docs/设计文档.md`，包含 SRS 分析、UML 类图、时序图与设计模式决策报告。

## Git 标签

- `baseline-v1`：初始验收版本
- `change-v2`：需求变更完成版本（预留，待教师发布 CR 后实施）

## 已知限制

- 使用固定演示账号，无用户注册与复杂权限系统；
- 通知仅站内消息，未接入邮件/短信；
- 活动删除采用软删除，保留历史报名记录。
