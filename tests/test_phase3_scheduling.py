import json
import threading
from contextlib import contextmanager
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from apps.api.server import create_demo_server


@contextmanager
def running_demo(tmp_path, monkeypatch=None, *, calendar_mode="fixture"):
    if monkeypatch is not None:
        monkeypatch.setenv("RECRUITING_DEMO_CALENDAR_MODE", calendar_mode)
    server = create_demo_server(tmp_path / "phase3.sqlite3")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield base_url
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
        server.demo_store.close()


def request_json(url: str, method: str = "GET", payload: object | None = None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body else {},
    )
    try:
        with urlopen(request) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def passing_payload():
    return {
        "contact": {"name": "Jordan Lee", "email": "jordan@example.com"},
        "consent": {"sms": "granted", "email": "denied"},
        "resume": {"status": "complete", "fileId": "resume-schedule-001"},
        "answers": {
            "work_authorization": True,
            "availability": ["weekends"],
            "location": "Chicago",
            "experience": 3,
            "interview_slot": {"slotId": "slot-001"},
        },
    }


def ready_application(base_url):
    status, application = request_json(
        f"{base_url}/api/apply/retail-operations/applications",
        method="POST",
        payload=passing_payload(),
    )
    assert status == 201
    status, screened = request_json(
        f"{base_url}/api/applications/{application['id']}/screen",
        method="POST",
    )
    assert status == 200
    assert screened["nextAction"] == "ready_to_schedule"
    return application


def test_fixture_booking_is_idempotent_and_rescheduling_replaces_old_slot(tmp_path):
    with running_demo(tmp_path) as base_url:
        application = ready_application(base_url)
        application_id = application["id"]

        status, slots = request_json(
            f"{base_url}/api/applications/{application_id}/slots"
        )
        assert status == 200
        assert [slot["id"] for slot in slots["slots"]] == ["slot-001", "slot-002", "slot-003"]

        booking = {"slotId": "slot-001", "channel": "sms"}
        status, booked = request_json(
            f"{base_url}/api/applications/{application_id}/interviews",
            method="POST",
            payload=booking,
        )
        assert status == 200
        first_interview_id = booked["interview"]["id"]
        assert booked["interview"]["status"] == "confirmed"
        assert booked["interview"]["calendarProvider"] == "fixture"
        assert booked["messages"][0]["providerResult"] == "sent"

        status, replay = request_json(
            f"{base_url}/api/applications/{application_id}/interviews",
            method="POST",
            payload=booking,
        )
        assert status == 200
        assert replay == booked

        status, moved = request_json(
            f"{base_url}/api/applications/{application_id}/reschedule",
            method="POST",
            payload={"slotId": "slot-002", "channel": "sms"},
        )
        assert status == 200
        assert moved["interview"]["id"] != first_interview_id
        assert moved["interview"]["slotId"] == "slot-002"

        status, detail = request_json(
            f"{base_url}/api/recruiter/applications/{application_id}"
        )
        assert status == 200
        assert len([item for item in detail["interviews"] if item["status"] == "confirmed"]) == 1
        assert len(detail["messages"]) == 2

        callback = {
            "providerEventId": "fixture-callback-002",
            "externalEventId": moved["interview"]["externalEventId"],
            "eventType": "confirmed",
        }
        status, first_callback = request_json(
            f"{base_url}/api/integrations/calendar/callback",
            method="POST",
            payload=callback,
        )
        assert status == 200
        assert first_callback["duplicate"] is False
        status, duplicate_callback = request_json(
            f"{base_url}/api/integrations/calendar/callback",
            method="POST",
            payload=callback,
        )
        assert status == 200
        assert duplicate_callback["duplicate"] is True


def test_calendar_provider_failure_preserves_state_and_creates_retryable_work(tmp_path, monkeypatch):
    with running_demo(tmp_path, monkeypatch, calendar_mode="outage") as base_url:
        application = ready_application(base_url)
        application_id = application["id"]

        status, failure = request_json(
            f"{base_url}/api/applications/{application_id}/interviews",
            method="POST",
            payload={"slotId": "slot-001", "channel": "sms"},
        )
        assert status == 503
        assert failure["code"] == "PROVIDER_DEGRADED"

        status, detail = request_json(
            f"{base_url}/api/recruiter/applications/{application_id}"
        )
        assert status == 200
        assert detail["status"] == "ready_to_schedule"
        assert detail["interviews"] == []
        retryable = [item for item in detail["workItems"] if item["kind"] == "book_interview"]
        assert len(retryable) == 1
        assert retryable[0]["status"] == "retryable"
