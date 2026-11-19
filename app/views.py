"""CampusEvent Flask 视图（REST API + 简单管理界面）。

提供 JSON API 覆盖 P2-F01~F08，以及一个极简中文管理页面便于演示。
"""
from __future__ import annotations

from datetime import datetime

from flask import Flask, jsonify, render_template, request

from .models import PolicyType
from .services import BusinessError


def register(app: Flask) -> None:
    activity_svc = app.extensions["activity_service"]
    registration_svc = app.extensions["registration_service"]

    @app.errorhandler(BusinessError)
    def _handle_business_error(err):
        return jsonify({"error": str(err)}), 400

    # ---------- 页面 ----------
    @app.get("/")
    def index():
        return render_template("index.html")

    # ---------- 活动管理 ----------
    @app.get("/api/activities")
    def list_activities():
        title = request.args.get("title", "")
        activities = activity_svc.list_activities(title)
        return jsonify([
            {
                "activity_id": a.activity_id,
                "title": a.title,
                "category": a.category,
                "start_at": a.start_at.isoformat(),
                "location": a.location,
                "capacity": a.capacity,
                "policy_type": a.policy_type.value,
            }
            for a in activities
        ])

    @app.post("/api/activities")
    def create_activity():
        data = request.get_json(force=True)
        try:
            policy = PolicyType(data["policy_type"])
        except (KeyError, ValueError):
            raise BusinessError("报名方式无效，应为 direct 或 review")
        try:
            capacity = int(data["capacity"])
            start_at = datetime.fromisoformat(data["start_at"])
        except (KeyError, ValueError):
            raise BusinessError("容量或开始时间格式无效")

        activity = activity_svc.create_activity(
            title=data.get("title", ""),
            category=data.get("category", ""),
            start_at=start_at,
            location=data.get("location", ""),
            capacity=capacity,
            policy_type=policy,
        )
        return jsonify({"activity_id": activity.activity_id}), 201

    @app.get("/api/activities/<int:activity_id>/stats")
    def activity_stats(activity_id):
        return jsonify(activity_svc.statistics(activity_id))

    # ---------- 报名 ----------
    @app.post("/api/activities/<int:activity_id>/register")
    def register(activity_id):
        data = request.get_json(force=True)
        student_id = data.get("student_id", "")
        if not student_id:
            raise BusinessError("缺少 student_id")
        registration = registration_svc.register(activity_id, student_id)
        return jsonify({
            "registration_id": registration.registration_id,
            "status": registration.status.value,
        }), 201

    @app.post("/api/activities/<int:activity_id>/cancel")
    def cancel(activity_id):
        data = request.get_json(force=True)
        student_id = data.get("student_id", "")
        registration = registration_svc.cancel(activity_id, student_id)
        return jsonify({
            "registration_id": registration.registration_id,
            "status": registration.status.value,
        })

    # ---------- 审批 ----------
    @app.post("/api/registrations/<int:registration_id>/approve")
    def approve(registration_id):
        registration = registration_svc.approve(registration_id)
        return jsonify({"status": registration.status.value})

    @app.post("/api/registrations/<int:registration_id>/reject")
    def reject(registration_id):
        registration = registration_svc.reject(registration_id)
        return jsonify({"status": registration.status.value})

    @app.get("/api/activities/<int:activity_id>/registrations")
    def list_registrations(activity_id):
        regs = registration_svc.list_registrations(activity_id)
        return jsonify([
            {
                "registration_id": r.registration_id,
                "activity_id": r.activity_id,
                "student_id": r.student_id,
                "status": r.status.value,
                "created_at": r.created_at.isoformat(),
            }
            for r in regs
        ])

    # ---------- 站内通知 ----------
    @app.get("/api/students/<student_id>/messages")
    def list_messages(student_id):
        msgs = registration_svc.list_messages(student_id)
        return jsonify([
            {
                "message_id": m.message_id,
                "activity_id": m.activity_id,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
                "is_read": m.is_read,
            }
            for m in msgs
        ])
