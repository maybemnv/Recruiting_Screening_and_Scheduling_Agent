"""Versioned job requirements and candidate-facing question preview."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .storage import SQLiteStore


CRITERION_TYPES = {
    "boolean",
    "enum",
    "number",
    "duration",
    "text_review",
    "location",
    "availability",
    "work_authorization",
    "experience",
}
OPERATORS = {
    "equals",
    "one_of",
    "greater_than_or_equal",
    "contains",
    "overlaps",
}


class RequirementError(ValueError):
    """Raised when a requirement version cannot be created or changed."""


class ImmutableVersionError(RequirementError):
    """Raised when a published or retired version is changed."""


@dataclass(frozen=True)
class Criterion:
    id: str
    label: str
    type: str
    operator: str
    expected_value: Any
    required: bool
    knockout: bool
    candidate_question: str
    explanation: str

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "Criterion":
        required = {
            "id",
            "label",
            "type",
            "operator",
            "expectedValue",
            "required",
            "knockout",
            "candidateQuestion",
            "explanation",
        }
        missing = sorted(required - value.keys())
        if missing:
            raise RequirementError(
                f"Criterion is missing required fields: {', '.join(missing)}"
            )
        if value["type"] not in CRITERION_TYPES:
            raise RequirementError(f"Unsupported criterion type: {value['type']}")
        if value["operator"] not in OPERATORS:
            raise RequirementError(f"Unsupported criterion operator: {value['operator']}")
        if not isinstance(value["id"], str) or not value["id"].strip():
            raise RequirementError("Criterion id must be a non-empty string")
        if not isinstance(value["candidateQuestion"], str) or not value[
            "candidateQuestion"
        ].strip():
            raise RequirementError("Candidate-facing wording is required")
        return cls(
            id=value["id"],
            label=value["label"],
            type=value["type"],
            operator=value["operator"],
            expected_value=value["expectedValue"],
            required=bool(value["required"]),
            knockout=bool(value["knockout"]),
            candidate_question=value["candidateQuestion"],
            explanation=value["explanation"],
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "type": self.type,
            "operator": self.operator,
            "expectedValue": self.expected_value,
            "required": self.required,
            "knockout": self.knockout,
            "candidateQuestion": self.candidate_question,
            "explanation": self.explanation,
        }


@dataclass(frozen=True)
class Job:
    id: str
    slug: str
    title: str


@dataclass(frozen=True)
class RequirementVersion:
    id: str
    job_id: str
    version: int
    status: str
    criteria: tuple[Criterion, ...]


class RequirementService:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def create_job(self, title: str, slug: str, job_id: str | None = None) -> Job:
        existing = self.store.get_job_by_slug(slug)
        if existing is not None:
            return Job(existing["id"], existing["slug"], existing["title"])
        resolved_id = job_id or slug
        self.store.insert_job(resolved_id, slug, title)
        return Job(resolved_id, slug, title)

    def get_job(self, job_id: str) -> Job:
        row = self.store.get_job(job_id)
        if row is None:
            raise KeyError(f"Unknown job: {job_id}")
        return Job(row["id"], row["slug"], row["title"])

    def get_job_by_slug(self, slug: str) -> Job:
        row = self.store.get_job_by_slug(slug)
        if row is None:
            raise KeyError(f"Unknown job slug: {slug}")
        return Job(row["id"], row["slug"], row["title"])

    def list_jobs(self) -> list[Job]:
        return [Job(row["id"], row["slug"], row["title"]) for row in self.store.list_jobs()]

    def create_draft(
        self,
        job_id: str,
        criteria: list[dict[str, Any]],
        version_id: str | None = None,
    ) -> RequirementVersion:
        self.get_job(job_id)
        normalized = self._normalize_criteria(criteria)
        version = self.store.next_version_number(job_id)
        resolved_id = version_id or f"{self.get_job(job_id).slug}-v{version}"
        self.store.insert_requirement_version(
            resolved_id,
            job_id,
            version,
            [criterion.to_mapping() for criterion in normalized],
        )
        return self.get_version(resolved_id)

    def replace_criteria(
        self, version_id: str, criteria: list[dict[str, Any]]
    ) -> RequirementVersion:
        version = self.get_version(version_id)
        if version.status != "draft":
            raise ImmutableVersionError(
                f"Requirement version {version_id} is {version.status} and immutable"
            )
        normalized = self._normalize_criteria(criteria)
        self.store.update_criteria(
            version_id, [criterion.to_mapping() for criterion in normalized]
        )
        return self.get_version(version_id)

    def publish(self, version_id: str) -> RequirementVersion:
        version = self.get_version(version_id)
        if version.status != "draft":
            if version.status in {"published", "retired"}:
                raise ImmutableVersionError(
                    f"Requirement version {version_id} is {version.status} and immutable"
                )
            raise RequirementError(f"Cannot publish version in state {version.status}")
        self.store.publish_requirement_version(version_id)
        return self.get_version(version_id)

    def get_version(self, version_id: str) -> RequirementVersion:
        row = self.store.get_requirement_version(version_id)
        if row is None:
            raise KeyError(f"Unknown requirement version: {version_id}")
        criteria = tuple(
            Criterion.from_mapping(value) for value in self.store.get_criteria(version_id)
        )
        return RequirementVersion(
            id=row["id"],
            job_id=row["job_id"],
            version=int(row["version"]),
            status=row["status"],
            criteria=criteria,
        )

    def get_published_version(self, job_id: str) -> RequirementVersion:
        row = self.store.get_latest_published(job_id)
        if row is None:
            raise KeyError(f"Job has no published requirement version: {job_id}")
        return self.get_version(row["id"])

    def candidate_preview(self, version_id: str) -> dict[str, Any]:
        version = self.get_version(version_id)
        if version.status != "published":
            raise RequirementError("Candidate preview requires a published version")
        return {
            "requirementVersionId": version.id,
            "questions": [
                {
                    "criterionId": criterion.id,
                    "label": criterion.label,
                    "question": criterion.candidate_question,
                    "type": criterion.type,
                    "knockout": criterion.knockout,
                }
                for criterion in version.criteria
            ],
        }

    @staticmethod
    def _normalize_criteria(criteria: list[dict[str, Any]]) -> tuple[Criterion, ...]:
        if not criteria:
            raise RequirementError("At least one screening criterion is required")
        normalized = tuple(Criterion.from_mapping(value) for value in criteria)
        ids = [criterion.id for criterion in normalized]
        if len(ids) != len(set(ids)):
            raise RequirementError("Criterion ids must be unique within a version")
        return normalized
