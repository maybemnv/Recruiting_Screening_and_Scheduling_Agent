"""Fixture-first interview slot booking and calendar callback reconciliation."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from .applications import ApplicationError


FIXTURE_SLOTS: tuple[dict[str, str], ...] = (
    {
        "id": "slot-001",
        "startsAt": "2026-08-12T09:00:00-05:00",
        "endsAt": "2026-08-12T09:30:00-05:00",
        "timeZone": "America/Chicago",
    },
    {
        "id": "slot-002",
        "startsAt": "2026-08-13T13:00:00-05:00",
        "endsAt": "2026-08-13T13:30:00-05:00",
        "timeZone": "America/Chicago",
    },
    {
        "id": "slot-003",
        "startsAt": "2026-08-14T10:00:00-05:00",
        "endsAt": "2026-08-14T10:30:00-05:00",
        "timeZone": "America/Chicago",
    },
)


class SchedulingService:
    """Keep booking state auditable while the provider remains a fixture."""

    def __init__(self, store: Any, applications: Any, *, calendar_mode: str | None = None):
        self.store = store
        self.applications = applications
        self.calendar_mode = calendar_mode or os.getenv("RECRUITING_DEMO_CALENDAR_MODE", "fixture")

    def available_slots(self, application_id: str) -> dict[str, Any]:
        self._application(application_id)
        active_slots = {
            row["slot_id"]
            for row in self.store.list_interviews(application_id)
            if row["status"] in {"held", "confirmed", "reschedule_requested"}
        }
        return {
            "applicationId": application_id,
            "provider": "fixture",
            "timeZone": "America/Chicago",
            "slots": [
                {**slot, "status": "booked" if slot["id"] in active_slots else "available"}
                for slot in FIXTURE_SLOTS
            ],
        }

    def book(self, application_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        application = self._application(application_id)
        slot = self._slot(payload.get("slotId"))
        channel = self._channel(payload.get("channel", "sms"))
        booking_key = f"interview:{application_id}:{slot['id']}"
        existing = self.store.get_interview_by_booking_key(booking_key)
        if existing is not None and existing["status"] == "confirmed":
            return self._booking_response(application_id, existing)

        self._require_ready(application)
        self._require_consent(application, channel)
        self._provider_available(application_id, booking_key, "Calendar provider is unavailable")

        active = self.store.get_active_interview(application_id)
        if active is not None:
            raise ApplicationError(
                409,
                "INTERVIEW_ALREADY_BOOKED",
                "An active interview already exists; use reschedule instead",
            )

        interview = self._insert_interview(application_id, slot, booking_key)
        self.store.update_application(application_id, status="scheduled")
        message = self._send_confirmation(application, interview, channel, rescheduled=False)
        return {"interview": interview, "messages": [message]}

    def reschedule(self, application_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        application = self._application(application_id)
        slot = self._slot(payload.get("slotId"))
        channel = self._channel(payload.get("channel", "sms"))
        active = self.store.get_active_interview(application_id)
        if active is None:
            raise ApplicationError(409, "INTERVIEW_NOT_BOOKED", "Book an interview before rescheduling")
        if active["slot_id"] == slot["id"]:
            return self._booking_response(application_id, active)

        booking_key = f"interview:{application_id}:{slot['id']}"
        existing = self.store.get_interview_by_booking_key(booking_key)
        if existing is not None and existing["status"] == "confirmed":
            return self._booking_response(application_id, existing)

        self._require_consent(application, channel)
        self._provider_available(application_id, booking_key, "Calendar provider is unavailable")
        # The fixture reserves the replacement before releasing the old event.
        replacement = self._insert_interview(application_id, slot, booking_key)
        self.store.update_interview(active["id"], status="cancelled")
        self.store.update_application(application_id, status="scheduled")
        message = self._send_confirmation(application, replacement, channel, rescheduled=True)
        return {"interview": replacement, "messages": [message]}

    def reconcile_callback(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        provider_event_id = self._required_string(payload.get("providerEventId"), "providerEventId")
        external_event_id = self._required_string(payload.get("externalEventId"), "externalEventId")
        event_type = self._required_string(payload.get("eventType"), "eventType")
        interview = self.store.get_interview_by_external_id(external_event_id)
        if interview is None:
            raise ApplicationError(404, "UNKNOWN_PROVIDER_EVENT", "The calendar event is not known")
        inserted = self.store.insert_provider_event(
            f"provider_event:{uuid4().hex[:16]}",
            provider_event_id,
            interview["booking_key"],
            event_type,
            dict(payload),
        )
        if inserted:
            if event_type == "confirmed":
                self.store.update_interview(interview["id"], status="confirmed")
            elif event_type in {"cancelled", "canceled"}:
                self.store.update_interview(interview["id"], status="cancelled")
        return {
            "duplicate": not inserted,
            "providerEventId": provider_event_id,
            "interview": self._interview_mapping(
                self.store.get_interview_by_external_id(external_event_id) or interview
            ),
        }

    def detail(self, application_id: str) -> dict[str, list[dict[str, Any]]]:
        self._application(application_id)
        return {
            "interviews": [self._interview_mapping(row) for row in self.store.list_interviews(application_id)],
            "messages": [self._message_mapping(row) for row in self.store.list_messages(application_id)],
        }

    def _insert_interview(
        self, application_id: str, slot: Mapping[str, str], booking_key: str
    ) -> dict[str, Any]:
        interview_id = f"interview_{uuid4().hex[:16]}"
        external_event_id = f"fixture-event-{uuid4().hex[:16]}"
        self.store.insert_interview(
            interview_id,
            application_id,
            "retail-screen",
            slot["id"],
            "fixture",
            external_event_id,
            slot["startsAt"],
            slot["endsAt"],
            slot["timeZone"],
            "confirmed",
            booking_key,
        )
        row = self.store.get_interview_by_booking_key(booking_key)
        if row is None:
            raise ApplicationError(500, "PERSISTENCE_ERROR", "Interview could not be persisted")
        return self._interview_mapping(row)

    def _send_confirmation(
        self,
        application: Mapping[str, Any],
        interview: Mapping[str, Any],
        channel: str,
        *,
        rescheduled: bool,
    ) -> dict[str, Any]:
        if os.getenv("RECRUITING_DEMO_MESSAGING_MODE", "fixture") == "outage":
            self.store.insert_work_item(
                f"work_{uuid4().hex[:16]}",
                application["id"],
                "send_message",
                f"message:{interview['id']}:{channel}",
                "Messaging provider is unavailable",
                status="retryable",
                last_error_code="PROVIDER_DEGRADED",
            )
            raise ApplicationError(503, "PROVIDER_DEGRADED", "Messaging provider is unavailable")
        kind = "interview_rescheduled" if rescheduled else "interview_confirmation"
        idempotency_key = f"message:{kind}:{interview['id']}"
        self.store.insert_message(
            f"message_{uuid4().hex[:16]}",
            application["id"],
            interview["id"],
            channel,
            f"{kind}:v1",
            self._recipient(application, channel),
            self._consent(application, channel),
            "sent",
            "sent",
            idempotency_key,
        )
        rows = [row for row in self.store.list_messages(application["id"]) if row["idempotency_key"] == idempotency_key]
        return self._message_mapping(rows[0])

    def _booking_response(self, application_id: str, interview: Mapping[str, Any]) -> dict[str, Any]:
        message_rows = [
            row for row in self.store.list_messages(application_id) if row["interview_id"] == interview["id"]
        ]
        return {
            "interview": self._interview_mapping(interview),
            "messages": [self._message_mapping(row) for row in message_rows],
        }

    def _provider_available(self, application_id: str, booking_key: str, reason: str) -> None:
        if self.calendar_mode != "outage":
            return
        self.store.insert_work_item(
            f"work_{uuid4().hex[:16]}",
            application_id,
            "book_interview",
            f"calendar:{booking_key}",
            reason,
            status="retryable",
            last_error_code="PROVIDER_DEGRADED",
        )
        raise ApplicationError(503, "PROVIDER_DEGRADED", reason)

    def _application(self, application_id: str) -> Mapping[str, Any]:
        row = self.store.get_application(application_id)
        if row is None:
            raise ApplicationError(404, "NOT_FOUND", f"Unknown application: {application_id}")
        return row

    @staticmethod
    def _slot(slot_id: Any) -> Mapping[str, str]:
        if not isinstance(slot_id, str) or not slot_id.strip():
            raise ApplicationError(422, "INVALID_SLOT", "slotId is required")
        for slot in FIXTURE_SLOTS:
            if slot["id"] == slot_id:
                return slot
        raise ApplicationError(409, "SLOT_UNAVAILABLE", "The requested interview slot is unavailable")

    @staticmethod
    def _channel(value: Any) -> str:
        if value not in {"sms", "email"}:
            raise ApplicationError(422, "INVALID_CHANNEL", "channel must be sms or email")
        return value

    @staticmethod
    def _require_ready(application: Mapping[str, Any]) -> None:
        if application["status"] != "ready_to_schedule":
            raise ApplicationError(409, "NOT_READY_TO_SCHEDULE", "Application is not ready to schedule")

    @staticmethod
    def _require_consent(application: Mapping[str, Any], channel: str) -> None:
        consent = application["consent"]
        if isinstance(consent, str):
            consent = json.loads(consent)
        if consent.get(channel) != "granted":
            raise ApplicationError(409, "CONSENT_REQUIRED", f"{channel} consent is required")

    @staticmethod
    def _recipient(application: Mapping[str, Any], channel: str) -> str:
        contact = application["contact"]
        if isinstance(contact, str):
            contact = json.loads(contact)
        return str(contact.get("phone" if channel == "sms" else "email"))

    @staticmethod
    def _consent(application: Mapping[str, Any], channel: str) -> str:
        consent = application["consent"]
        if isinstance(consent, str):
            consent = json.loads(consent)
        return str(consent.get(channel, "unknown"))

    @staticmethod
    def _required_string(value: Any, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ApplicationError(422, "INVALID_CALLBACK", f"{field} is required")
        return value.strip()

    @staticmethod
    def _interview_mapping(row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "applicationId": row["application_id"],
            "interviewTypeId": row["interview_type_id"],
            "slotId": row["slot_id"],
            "calendarProvider": row["calendar_provider"],
            "externalEventId": row["external_event_id"],
            "startsAt": row["start_at"],
            "endsAt": row["end_at"],
            "timeZone": row["time_zone"],
            "status": row["status"],
            "bookingKey": row["booking_key"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    @staticmethod
    def _message_mapping(row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "applicationId": row["application_id"],
            "interviewId": row["interview_id"],
            "channel": row["channel"],
            "templateVersion": row["template_version"],
            "recipientReference": row["recipient_reference"],
            "consentState": row["consent_state"],
            "providerResult": row["provider_result"],
            "status": row["status"],
            "idempotencyKey": row["idempotency_key"],
            "attempts": row["attempts"],
            "lastErrorCode": row["last_error_code"],
            "createdAt": row["created_at"],
        }
