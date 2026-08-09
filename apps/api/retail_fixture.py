"""Deterministic retail demo fixture from PRD Trace A."""

from __future__ import annotations

import json
from pathlib import Path

from .requirements import RequirementService, RequirementVersion


RETAIL_JOB_ID = "retail-job"
RETAIL_JOB_SLUG = "retail-operations"
RETAIL_VERSION_ID = "retail-job-v1"

FIXTURE_PATH = Path(__file__).parents[2] / "fixtures" / "retail_job_v1.json"


def load_retail_fixture() -> dict[str, object]:
    with FIXTURE_PATH.open(encoding="utf-8") as fixture:
        return json.load(fixture)


def seed_retail_job(service: RequirementService) -> RequirementVersion:
    fixture = load_retail_fixture()
    job_data = fixture["job"]
    version_data = fixture["requirementVersion"]
    job = service.create_job(
        job_data["title"],
        job_data["slug"],
        job_id=job_data["id"],
    )
    try:
        return service.get_version(version_data["id"])
    except KeyError:
        draft = service.create_draft(
            job.id,
            version_data["criteria"],
            version_id=version_data["id"],
        )
        return service.publish(draft.id)
