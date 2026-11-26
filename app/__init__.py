"""CampusEvent 应用工厂。

创建 Flask 应用、装配 Database、服务与事件分发器。
"""
from __future__ import annotations

import os

from flask import Flask

from .db import Database
from .notifications import (
    EmailNotificationListener,
    EventDispatcher,
    InboxNotificationListener,
    MockEmailSender,
)
from .services import ActivityService, RegistrationService


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)

    db_path = os.environ.get("CAMPUSEVENT_DB", "campus_event.db")
    if test_config and "db_path" in test_config:
        db_path = test_config["db_path"]

    db = Database(db_path)

    # 测试可注入邮件失败开关，用于验证 CR2-03
    email_failure = bool(test_config and test_config.get("email_failure", False))

    dispatcher = EventDispatcher()
    dispatcher.subscribe(InboxNotificationListener(db))
    # CR-02：新增邮件通知监听器，与站内通知并列订阅同一事件
    dispatcher.subscribe(EmailNotificationListener(MockEmailSender(db, failure=email_failure)))

    activity_service = ActivityService(db)
    registration_service = RegistrationService(db, dispatcher)

    # 挂到 app 扩展对象，供视图使用
    app.extensions["db"] = db
    app.extensions["activity_service"] = activity_service
    app.extensions["registration_service"] = registration_service

    from . import views  # noqa: F401
    views.register(app)

    return app
