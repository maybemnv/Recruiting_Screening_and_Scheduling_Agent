"""Fixture-first application intake, evidence, screening, and handoff domain."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from .requirements import Criterion, RequirementService


APPROVED_FAQS: tuple[dict[str, str], ...] = (
    {
        "id": "schedule-format",
        "question": "What happens after I submit my application?",
        "answer": "A recruiter reviews the explicit screening evidence before confirming an interview.",
    },
    {
        "id": "human-review",
        "question": "Can I ask a recruiter for help?",
        "answer": "Yes. Use the human-help path and automated screening pauses for recruiter follow-up.",
    },
)


class ApplicationError(ValueError):
    """A safe, typed application-domain error for the HTTP boundary."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class ApplicationService:
    """Coordinate append-only evidence and deterministic screening results."""

    def __init__(self, store: Any, requirements: RequirementService):
        self.store = store
        self.requirements = requirements
        self.scheduler: Any | None = None

    def create_application(self, job_slug: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        job = self.requirements.get_job_by_slug(job_slug)
        version = self.requirements.get_published_version(job.id)
        contact = self._contact(payload.get("contact"))
        consent = self._consent(payload.get("consent"))
        answers = payload.get("answers", {})
        if not isinstance(answers, Mapping):
            raise ApplicationError(422, "INVALID_APPLICATION", "answers must be an object")
        known_criteria = {criterion.id: criterion for criterion in version.criteria}
        unknown = sorted(set(answers) - set(known_criteria))
        if unknown:
            raise ApplicationError(
                422,
                "UNKNOWN_CRITERION",
                f"Answer references unknown criteria: {', '.join(unknown)}",
            )

        resume = payload.get("resume", {})
        if resume is None:
            resume = {}
        if not isinstance(resume, Mapping):
            raise ApplicationError(422, "INVALID_RESUME", "resume must be an object")
        resume_status = str(resume.get("status", "not_provided"))
        allowed_resume_statuses = {"not_provided", "complete", "uncertain", "unavailable", "corrected"}
        if resume_status not in allowed_resume_statuses:
            raise ApplicationError(422, "INVALID_RESUME", f"Unsupported resume status: {resume_status}")
        resume_file_id = resume.get("fileId")
        if resume_status != "not_provided" and (
            not isinstance(resume_file_id, str) or not resume_file_id.strip()
        ):
            raise ApplicationError(
                422,
                "INVALID_RESUME",
                "A fileId is required when resume status is not_provided",
            )

        application_id = self._id("app")
        status = "human_handoff" if payload.get("requestHuman") is True else "in_progress"
        self.store.insert_application(
            application_id,
            job.id,
            version.id,
            dict(contact),
            consent,
            status,
            resume_status,
            resume_file_id,
        )
        correlation_id = f"intake:{application_id}"
        self._audit(
            application_id,
            version.id,
            "application_created",
            before_state=None,
            after_state={"status": status, "requirementVersionId": version.id},
            correlation_id=correlation_id,
            actor_type="candidate",
        )

        for criterion in version.criteria:
            if criterion.id not in answers:
                continue
            evidence_id = self._id("ev")
            self.store.insert_evidence(
                evidence_id,
                application_id,
                criterion.id,
                "candidate_answer",
                answers[criterion.id],
                {"kind": "answer", "id": f"answer:{application_id}:{criterion.id}"},
                1.0,
                "complete",
            )
            self._audit(
                application_id,
                version.id,
                "candidate_answer_recorded",
                before_state=None,
                after_state={"criterionId": criterion.id, "evidenceId": evidence_id},
                correlation_id=correlation_id,
                actor_type="candidate",
            )

        if resume_status != "not_provided":
            evidence_id = self._id("ev")
            self.store.insert_evidence(
                evidence_id,
                application_id,
                None,
                "resume",
                None,
                {"kind": "document_span", "id": str(resume_file_id)},
                None if resume_status in {"unavailable", "uncertain"} else 1.0,
                resume_status,
            )
            self._audit(
                application_id,
                version.id,
                "resume_received",
                before_state=None,
                after_state={"status": resume_status, "evidenceId": evidence_id},
                correlation_id=correlation_id,
                actor_type="candidate",
            )

        if status == "human_handoff":
            self._queue_handoff(
                application_id,
                version.id,
                "candidate_requested_human",
                correlation_id,
            )
        return self.application_summary(application_id)

    def screen_application(
        self,
        application_id: str,
        idempotency_key: str | None = None,
        force_rerun: bool = False,
    ) -> dict[str, Any]:
        application = self._get_application(application_id)
        version = self.requirements.get_version(application["requirement_version_id"])
        existing = self.store.list_evaluations(application_id)
        if application["status"] == "human_handoff":
            return self.screening_response(application, existing)
        if existing and not force_rerun:
            return self.screening_response(application, existing)
        if force_rerun and existing:
            self.store.delete_evaluations(application_id)

        evidence = self.store.list_evidence(application_id)
        by_criterion: dict[str, list[Mapping[str, Any]]] = {}
        resume_evidence = []
        for item in evidence:
            normalized = self._evidence_mapping(item)
            criterion_id = normalized["criterionId"]
            if criterion_id is None:
                resume_evidence.append(normalized)
            else:
                by_criterion.setdefault(criterion_id, []).append(normalized)

        results: list[dict[str, Any]] = []
        for criterion in version.criteria:
            criterion_evidence = by_criterion.get(criterion.id, [])
            result, explanation, evidence_ids = self._evaluate(
                criterion, criterion_evidence, resume_evidence
            )
            evaluation_id = self._id("eval")
            rule_expression = (
                f"{criterion.id} {criterion.operator} "
                f"{json.dumps(criterion.expected_value, sort_keys=True)}"
            )
            self.store.insert_evaluation(
                evaluation_id,
                application_id,
                version.id,
                criterion.id,
                result,
                evidence_ids,
                rule_expression,
                explanation,
                "rule_engine",
            )
            results.append(
                {
                    "id": evaluation_id,
                    "applicationId": application_id,
                    "requirementVersionId": version.id,
                    "criterionId": criterion.id,
                    "result": result,
                    "evidenceIds": evidence_ids,
                    "ruleExpression": rule_expression,
                    "explanation": explanation,
                    "evaluator": "rule_engine",
                }
            )

        required_results = {
            result["criterionId"]: result["result"]
            for result, criterion in zip(results, version.criteria)
            if criterion.required
        }
        if all(result == "pass" for result in required_results.values()):
            next_status = "ready_to_schedule"
        else:
            next_status = "review"
        self.store.update_application(application_id, status=next_status)
        correlation_id = idempotency_key or f"screen:{application_id}:{version.id}"
        self._audit(
            application_id,
            version.id,
            "screening_evaluated",
            before_state={"status": application["status"]},
            after_state={"status": next_status, "results": results},
            correlation_id=correlation_id,
            actor_type="worker",
        )
        if next_status == "review":
            self._queue_handoff(
                application_id,
                version.id,
                "screening_requires_review",
                correlation_id,
            )
        return self.screening_response(
            self._get_application(application_id),
            self.store.list_evaluations(application_id),
        )

    def request_handoff(self, application_id: str, reason: str) -> dict[str, Any]:
        if not isinstance(reason, str) or not reason.strip():
            raise ApplicationError(409, "HANDOFF_REASON_REQUIRED", "A handoff reason is required")
        application = self._get_application(application_id)
        version_id = application["requirement_version_id"]
        correlation_id = f"handoff:{application_id}:{reason.strip()}"
        self.store.update_application(application_id, status="human_handoff")
        self._queue_handoff(application_id, version_id, reason.strip(), correlation_id)
        self._audit(
            application_id,
            version_id,
            "human_handoff_requested",
            before_state={"status": application["status"]},
            after_state={"status": "human_handoff"},
            reason=reason.strip(),
            correlation_id=correlation_id,
            actor_type="candidate",
        )
        return self.application_summary(application_id)

    def record_disposition(
        self,
        application_id: str,
        actor_type: str,
        actor_id: str | None,
        disposition: str,
        reason: str | None,
    ) -> dict[str, Any]:
        if actor_type != "recruiter":
            raise ApplicationError(
                403,
                "HUMAN_ACTOR_REQUIRED",
                "Only a recruiter can record final disposition",
            )
        if not isinstance(reason, str) or not reason.strip():
            raise ApplicationError(409, "HUMAN_REASON_REQUIRED", "A reason is required")
        if disposition not in {"advance", "hold", "decline", "withdrawn"}:
            raise ApplicationError(422, "INVALID_DISPOSITION", "Unsupported disposition")
        application = self._get_application(application_id)
        version_id = application["requirement_version_id"]
        self.store.update_application(
            application_id,
            status="dispositioned",
            disposition=disposition,
            disposition_reason=reason.strip(),
            dispositioned_by=actor_id or "recruiter",
        )
        self._audit(
            application_id,
            version_id,
            "disposition_recorded",
            before_state={"status": application["status"]},
            after_state={"status": "dispositioned", "disposition": disposition},
            reason=reason.strip(),
            correlation_id=f"disposition:{application_id}",
            actor_type="recruiter",
            actor_id=actor_id,
        )
        return self.application_summary(application_id)

    def correct_answer(
        self, application_id: str, criterion_id: str, value: Any
    ) -> dict[str, Any]:
        application = self._get_application(application_id)
        version = self.requirements.get_version(application["requirement_version_id"])
        if criterion_id not in {criterion.id for criterion in version.criteria}:
            raise ApplicationError(422, "UNKNOWN_CRITERION", f"Unknown criterion: {criterion_id}")
        evidence_id = self._id("ev")
        self.store.insert_evidence(
            evidence_id,
            application_id,
            criterion_id,
            "candidate_answer",
            value,
            {"kind": "answer", "id": f"correction:{application_id}:{criterion_id}:{evidence_id}"},
            0.95,
            "corrected",
        )
        if application["status"] not in {"human_handoff", "dispositioned"}:
            self.store.update_application(application_id, status="review")
        self._audit(
            application_id,
            application["requirement_version_id"],
            "candidate_answer_corrected",
            before_state=None,
            after_state={"criterionId": criterion_id, "evidenceId": evidence_id},
            correlation_id=f"correction:{application_id}:{criterion_id}",
            actor_type="candidate",
        )
        return self.application_summary(application_id)

    def update_consent(self, application_id: str, channel: str) -> dict[str, Any]:
        if channel not in {"sms", "email"}:
            raise ApplicationError(422, "INVALID_CHANNEL", "channel must be sms or email")
        application = self._get_application(application_id)
        consent = self._json_value(application["consent"], {})
        consent[channel] = "denied"
        self.store.update_application(application_id, consent=consent)
        self._audit(
            application_id,
            application["requirement_version_id"],
            "candidate_opted_out",
            before_state={"consent": self._json_value(application["consent"], {})},
            after_state={"consent": consent},
            correlation_id=f"opt-out:{application_id}:{channel}",
            actor_type="candidate",
        )
        return self.application_summary(application_id)

    def list_faqs(self, job_slug: str) -> dict[str, Any]:
        self.requirements.get_job_by_slug(job_slug)
        return {"jobSlug": job_slug, "faqs": [dict(item) for item in APPROVED_FAQS]}

    def get_faq(self, job_slug: str, faq_id: str) -> dict[str, Any]:
        self.requirements.get_job_by_slug(job_slug)
        faq = next((item for item in APPROVED_FAQS if item["id"] == faq_id), None)
        if faq is None:
            raise ApplicationError(404, "FAQ_NOT_APPROVED", "The question is not in the approved FAQ")
        return {"jobSlug": job_slug, "approved": True, **faq}

    def application_summary(self, application_id: str) -> dict[str, Any]:
        return self._serialize_application(self._get_application(application_id))

    def application_detail(self, application_id: str) -> dict[str, Any]:
        application = self._get_application(application_id)
        detail = {
            **self._serialize_application(application),
            "evidence": [self._evidence_mapping(item) for item in self.store.list_evidence(application_id)],
            "evaluations": [self._evaluation_mapping(item) for item in self.store.list_evaluations(application_id)],
            "workItems": [self._work_item_mapping(item) for item in self.store.list_work_items(application_id)],
            "auditEvents": [
                self._audit_mapping(item)
                for item in self.store.list_audit_events("application", application_id)
            ],
        }
        if self.scheduler is not None:
            detail.update(self.scheduler.detail(application_id))
        else:
            detail.update({"interviews": [], "messages": []})
        return detail

    def pipeline(self, job_id: str, status_filter: str | None = None) -> dict[str, Any]:
        self.requirements.get_job(job_id)
        rows = self.store.list_applications(job_id)
        if status_filter:
            if status_filter in {
                "received", "in_progress", "awaiting_candidate", "review",
                "ready_to_schedule", "scheduled", "interviewed", "human_handoff",
                "withdrawn", "dispositioned",
            }:
                rows = [row for row in rows if row["status"] == status_filter]
            elif status_filter == "missing_evidence":
                rows = [
                    row
                    for row in rows
                    if any(
                        result["result"] in {"review", "not_evaluated"}
                        for result in self.store.list_evaluations(row["id"])
                    )
                ]
            elif status_filter == "failed_work":
                rows = [
                    row
                    for row in rows
                    if any(
                        item["status"] in {"retryable", "failed"}
                        for item in self.store.list_work_items(row["id"])
                    )
                ]
            else:
                raise ApplicationError(422, "INVALID_PIPELINE_FILTER", "Unsupported pipeline filter")
        counts: dict[str, int] = {}
        for row in rows:
            status = row["status"]
            counts[status] = counts.get(status, 0) + 1
        return {
            "jobId": job_id,
            "counts": counts,
            "rows": [self._serialize_application(row, include_contact=True) for row in rows],
        }

    def analytics(self, job_id: str, date_from: str | None = None, date_to: str | None = None) -> dict[str, Any]:
        self.requirements.get_job(job_id)
        rows = self.store.list_applications(job_id)
        stages: dict[str, int] = {}
        versions: dict[str, int] = {}
        without_evaluation = 0
        evaluations_without_evidence = 0
        for row in rows:
            stages[row["status"]] = stages.get(row["status"], 0) + 1
            version_id = row["requirement_version_id"]
            versions[version_id] = versions.get(version_id, 0) + 1
            evaluations = self.store.list_evaluations(row["id"])
            if not evaluations:
                without_evaluation += 1
            evaluations_without_evidence += sum(
                1 for evaluation in evaluations if not self._json_value(evaluation["evidence_ids"], [])
            )
        return {
            "jobId": job_id,
            "dateRange": {"from": date_from, "to": date_to},
            "timestampDefinition": "applications.created_at",
            "denominator": len(rows),
            "stages": stages,
            "byRequirementVersion": versions,
            "missingness": {
                "applicationsWithoutEvaluation": without_evaluation,
                "evaluationsWithoutEvidence": evaluations_without_evidence,
            },
            "finalDisposition": {
                "humanRecorded": sum(1 for row in rows if row["status"] == "dispositioned"),
                "automated": 0,
            },
        }

    def screening_response(
        self, application: Mapping[str, Any], evaluations: list[Mapping[str, Any]]
    ) -> dict[str, Any]:
        return {
            "applicationId": application["id"],
            "requirementVersionId": application["requirement_version_id"],
            "results": [self._evaluation_mapping(item) for item in evaluations],
            "nextAction": (
                "human_handoff"
                if application["status"] == "human_handoff"
                else application["status"]
            ),
        }

    def _evaluate(
        self,
        criterion: Criterion,
        criterion_evidence: list[Mapping[str, Any]],
        resume_evidence: list[Mapping[str, Any]],
    ) -> tuple[str, str, list[str]]:
        latest = criterion_evidence[-1] if criterion_evidence else None
        evidence_ids = [str(item["id"]) for item in criterion_evidence]
        value = latest["value"] if latest is not None else None
        missing = value is None or value == "" or value == [] or value == {}
        if criterion.id == "experience" and missing:
            unavailable = any(item["extractionStatus"] in {"unavailable", "uncertain"} for item in resume_evidence)
            if unavailable:
                evidence_ids.extend(str(item["id"]) for item in resume_evidence)
                return "review", "Resume evidence is unavailable; experience requires recruiter review.", evidence_ids
        if missing:
            return "not_evaluated", "No usable evidence was provided; screening cannot evaluate this criterion.", evidence_ids

        if criterion.id == "work_authorization":
            result = "pass" if value is True else "fail" if value is False else "review"
        elif criterion.id == "availability":
            text = self._flatten_text(value).lower()
            result = "review" if "sometimes" in text or "maybe" in text else (
                "pass" if "weekend" in text else "review"
            )
        elif criterion.id == "location":
            text = self._flatten_text(value).lower()
            result = "pass" if "chicago" in text else "fail" if text else "review"
        elif criterion.id == "experience":
            try:
                number = float(value)
            except (TypeError, ValueError):
                result = "review"
            else:
                result = "pass" if number >= float(criterion.expected_value) else "fail"
        elif criterion.id == "interview_slot":
            result = "pass" if value else "not_evaluated"
        else:
            result = self._generic_result(criterion, value)

        if result == "pass":
            explanation = "Evidence matched the configured requirement."
        elif result == "fail":
            explanation = "Evidence did not satisfy the configured requirement; recruiter review remains required."
        elif result == "review":
            explanation = "Evidence is ambiguous or incomplete; recruiter review is required."
        else:
            explanation = "No usable evidence was provided; screening cannot evaluate this criterion."
        return result, explanation, evidence_ids

    @staticmethod
    def _generic_result(criterion: Criterion, value: Any) -> str:
        expected = criterion.expected_value
        if criterion.operator == "equals":
            return "pass" if value == expected else "fail"
        if criterion.operator == "contains":
            return "pass" if str(expected).lower() in str(value).lower() else "fail"
        if criterion.operator == "one_of" and isinstance(expected, list):
            return "pass" if value in expected else "fail"
        if criterion.operator == "overlaps":
            values = value if isinstance(value, list) else [value]
            expected_values = expected if isinstance(expected, list) else [expected]
            return "pass" if set(values).intersection(expected_values) else "review"
        return "review"

    def _queue_handoff(
        self, application_id: str, version_id: str, reason: str, correlation_id: str
    ) -> None:
        self.store.insert_work_item(
            self._id("work"),
            application_id,
            "human_handoff",
            f"human-handoff:{application_id}:{reason}",
            reason,
        )

    def _audit(
        self,
        application_id: str,
        version_id: str,
        action: str,
        *,
        before_state: Any,
        after_state: Any,
        correlation_id: str,
        actor_type: str,
        actor_id: str | None = None,
        reason: str | None = None,
    ) -> None:
        self.store.insert_audit_event(
            self._id("audit"),
            actor_type,
            actor_id,
            action,
            "application",
            application_id,
            before_state,
            after_state,
            reason,
            correlation_id,
            version_id,
        )

    def _get_application(self, application_id: str) -> Mapping[str, Any]:
        row = self.store.get_application(application_id)
        if row is None:
            raise ApplicationError(404, "NOT_FOUND", f"Unknown application: {application_id}")
        return row

    @staticmethod
    def _contact(value: Any) -> Mapping[str, str | None]:
        if not isinstance(value, Mapping):
            raise ApplicationError(422, "INVALID_CONTACT", "contact must be an object")
        name = value.get("name")
        email = value.get("email")
        phone = value.get("phone")
        if not isinstance(name, str) or not name.strip():
            raise ApplicationError(422, "INVALID_CONTACT", "contact.name is required")
        if email is not None and not isinstance(email, str):
            raise ApplicationError(422, "INVALID_CONTACT", "contact.email must be a string")
        if phone is not None and not isinstance(phone, str):
            raise ApplicationError(422, "INVALID_CONTACT", "contact.phone must be a string")
        if not email and not phone:
            raise ApplicationError(422, "INVALID_CONTACT", "contact.email or contact.phone is required")
        return {"name": name.strip(), "email": email, "phone": phone}

    @staticmethod
    def _consent(value: Any) -> dict[str, str]:
        if value is None:
            value = {}
        if not isinstance(value, Mapping):
            raise ApplicationError(422, "INVALID_CONSENT", "consent must be an object")
        allowed = {"granted", "denied", "unknown"}
        result = {}
        for channel in ("sms", "email"):
            state = value.get(channel, "unknown")
            if state not in allowed:
                raise ApplicationError(422, "INVALID_CONSENT", f"Unsupported {channel} consent")
            result[channel] = state
        return result

    @staticmethod
    def _flatten_text(value: Any) -> str:
        if isinstance(value, Mapping):
            return " ".join(ApplicationService._flatten_text(item) for item in value.values())
        if isinstance(value, list):
            return " ".join(ApplicationService._flatten_text(item) for item in value)
        return str(value)

    @staticmethod
    def _id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex[:16]}"

    @staticmethod
    def _json_value(value: Any, default: Any = None) -> Any:
        if value is None:
            return default
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    def _serialize_application(
        self, row: Mapping[str, Any], include_contact: bool = True
    ) -> dict[str, Any]:
        result = {
            "id": row["id"],
            "jobId": row["job_id"],
            "requirementVersionId": row["requirement_version_id"],
            "status": row["status"],
            "consent": self._json_value(row["consent"], {}),
            "resume": {"status": row["resume_status"], "fileId": row["resume_file_id"]},
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }
        if include_contact:
            result["contact"] = self._json_value(row["contact"], {})
        if row["disposition"] is not None:
            result["disposition"] = {
                "value": row["disposition"],
                "reason": row["disposition_reason"],
                "actorId": row["dispositioned_by"],
            }
        return result

    def _evidence_mapping(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "applicationId": row["application_id"],
            "criterionId": row["criterion_id"],
            "source": row["source"],
            "value": self._json_value(row["value"]),
            "sourceReference": self._json_value(row["source_reference"], {}),
            "confidence": row["confidence"],
            "extractionStatus": row["extraction_status"],
            "createdAt": row["created_at"],
        }

    def _evaluation_mapping(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "applicationId": row["application_id"],
            "requirementVersionId": row["requirement_version_id"],
            "criterionId": row["criterion_id"],
            "result": row["result"],
            "evidenceIds": self._json_value(row["evidence_ids"], []),
            "ruleExpression": row["rule_expression"],
            "explanation": row["explanation"],
            "evaluator": row["evaluator"],
            "evaluatedAt": row["evaluated_at"],
        }

    @staticmethod
    def _work_item_mapping(row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "applicationId": row["application_id"],
            "kind": row["kind"],
            "idempotencyKey": row["idempotency_key"],
            "status": row["status"],
            "attempts": row["attempts"],
            "reason": row["reason"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    def _audit_mapping(self, row: Mapping[str, Any]) -> dict[str, Any]:
        try:
            before_state = row["before_state"]
        except (IndexError, KeyError):
            before_state = row["before"]
        try:
            after_state = row["after_state"]
        except (IndexError, KeyError):
            after_state = row["after"]
        return {
            "id": row["id"],
            "occurredAt": row["occurred_at"],
            "actorType": row["actor_type"],
            "actorId": row["actor_id"],
            "action": row["action"],
            "entityType": row["entity_type"],
            "entityId": row["entity_id"],
            "before": self._json_value(before_state),
            "after": self._json_value(after_state),
            "reason": row["reason"],
            "correlationId": row["correlation_id"],
            "sourceVersion": row["source_version"],
        }
