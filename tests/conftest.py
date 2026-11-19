"""CampusEvent 测试夹具。"""
from __future__ import annotations

import os
import tempfile

import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    db_path = os.path.join(tmp_path, "test.db")
    app = create_app({"db_path": db_path})
    app.config["TESTING"] = True
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def services(app):
    """直接返回服务对象，便于业务层断言。"""
    return {
        "activity": app.extensions["activity_service"],
        "registration": app.extensions["registration_service"],
        "db": app.extensions["db"],
    }
