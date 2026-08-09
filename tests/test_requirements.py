import pytest

from apps.api.requirements import ImmutableVersionError, RequirementService
from apps.api.retail_fixture import seed_retail_job
from apps.api.storage import SQLiteStore


def test_published_requirement_version_cannot_be_mutated(tmp_path):
    service = RequirementService(SQLiteStore(tmp_path / "requirements.sqlite3"))
    job = service.create_job("Retail Operations Associate", "retail-operations")
    version = service.create_draft(
        job.id,
        [
            {
                "id": "work_authorization",
                "label": "Work authorization",
                "type": "work_authorization",
                "operator": "equals",
                "expectedValue": True,
                "required": True,
                "knockout": True,
                "candidateQuestion": "Are you authorized to work in the job location?",
                "explanation": "This role requires current work authorization.",
            }
        ],
    )
    service.publish(version.id)

    with pytest.raises(ImmutableVersionError):
        service.replace_criteria(version.id, [])

    replacement = service.create_draft(
        job.id,
        [
            {
                "id": "work_authorization",
                "label": "Work authorization",
                "type": "work_authorization",
                "operator": "equals",
                "expectedValue": True,
                "required": True,
                "knockout": True,
                "candidateQuestion": "Can you work in the job location?",
                "explanation": "This role requires current work authorization.",
            }
        ],
    )
    service.publish(replacement.id)

    original = service.get_version(version.id)
    current = service.get_version(replacement.id)
    assert original.criteria[0].candidate_question == (
        "Are you authorized to work in the job location?"
    )
    assert current.criteria[0].candidate_question == "Can you work in the job location?"
    assert original.version == 1
    assert current.version == 2


def test_candidate_preview_matches_published_retail_criteria_in_order(tmp_path):
    service = RequirementService(SQLiteStore(tmp_path / "retail.sqlite3"))
    seed_retail_job(service)

    version = service.get_version("retail-job-v1")
    preview = service.candidate_preview(version.id)

    assert preview["requirementVersionId"] == "retail-job-v1"
    assert [item["criterionId"] for item in preview["questions"]] == [
        criterion.id for criterion in version.criteria
    ]
    assert [item["question"] for item in preview["questions"]] == [
        criterion.candidate_question for criterion in version.criteria
    ]
    assert len(preview["questions"]) == 5
