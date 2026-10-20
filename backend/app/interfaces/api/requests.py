"""İstek gövdelerinden domain nesnelerine dönüşüm."""
from dataclasses import fields

from flask import current_app, request

from app.domain.evaluation.desirability import Goals
from app.domain.process.model import ProcessSettings


def body() -> dict:
    return request.get_json(silent=True) or {}


def container():
    return current_app.extensions["container"]


def parse_settings(data: dict) -> ProcessSettings:
    raw = data.get("settings") or {}
    return ProcessSettings(
        n_applications=int(raw.get("n_applications", ProcessSettings.n_applications)),
        target_moisture=float(raw.get("target_moisture", ProcessSettings.target_moisture)),
    )


def parse_goals(data: dict) -> Goals:
    raw = data.get("goals") or {}
    valid = {f.name for f in fields(Goals)}
    return Goals(**{k: float(v) for k, v in raw.items() if k in valid})


def parse_overrides(data: dict) -> dict:
    overrides = data.get("overrides") or {}
    if not isinstance(overrides, dict):
        raise ValueError("overrides bir nesne olmalı")
    return overrides
