"""CampusEvent Web API 冒烟测试。"""
from __future__ import annotations

from datetime import datetime, timedelta

FUTURE = (datetime.now() + timedelta(days=7)).isoformat()


def test_create_and_list_activity(client):
    resp = client.post("/api/activities", json={
        "title": "篮球赛", "category": "体育", "start_at": FUTURE,
        "location": "操场", "capacity": 10, "policy_type": "direct",
    })
    assert resp.status_code == 201
    aid = resp.get_json()["activity_id"]

    resp = client.get("/api/activities")
    assert resp.status_code == 200
    titles = [a["title"] for a in resp.get_json()]
    assert "篮球赛" in titles

    resp = client.get(f"/api/activities/{aid}/stats")
    data = resp.get_json()
    assert data["approved"] == 0
    assert data["remaining"] == 10


def test_register_via_api(client):
    aid = client.post("/api/activities", json={
        "title": "讲座", "category": "讲座", "start_at": FUTURE,
        "location": "报告厅", "capacity": 5, "policy_type": "direct",
    }).get_json()["activity_id"]

    resp = client.post(f"/api/activities/{aid}/register", json={"student_id": "S100"})
    assert resp.status_code == 201
    assert resp.get_json()["status"] == "approved"

    resp = client.get("/api/students/S100/messages")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 1


def test_review_approve_flow(client):
    aid = client.post("/api/activities", json={
        "title": "讲座2", "category": "讲座", "start_at": FUTURE,
        "location": "报告厅", "capacity": 2, "policy_type": "review",
    }).get_json()["activity_id"]

    rid = client.post(f"/api/activities/{aid}/register", json={"student_id": "S200"}).get_json()["registration_id"]
    assert client.get(f"/api/activities/{aid}/registrations").get_json()[0]["status"] == "pending"

    resp = client.post(f"/api/registrations/{rid}/approve", json={})
    assert resp.get_json()["status"] == "approved"
