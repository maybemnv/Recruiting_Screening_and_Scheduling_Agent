const state = {
  preview: null,
  requirements: null,
  application: null,
  slots: null,
};

const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

const json = async (url, options = {}) => {
  const response = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.message || `Request failed: ${response.status}`);
  return body;
};

const questionControl = (question, index) => {
  const id = `question-${question.criterionId}`;
  let control = `<input id="${escapeHtml(id)}" name="${escapeHtml(question.criterionId)}" placeholder="Your answer" />`;
  if (question.criterionId === "work_authorization") {
    control = `<select id="${escapeHtml(id)}" name="${escapeHtml(question.criterionId)}">
      <option value="">Select an answer</option><option value="true">Yes</option><option value="false">No</option>
    </select>`;
  } else if (question.criterionId === "experience") {
    control = `<input id="${escapeHtml(id)}" name="${escapeHtml(question.criterionId)}" type="number" min="0" step="1" placeholder="3" />`;
  } else if (question.criterionId === "interview_slot") {
    control = `<select id="${escapeHtml(id)}" name="${escapeHtml(question.criterionId)}">
      <option value="">Choose later</option><option value="slot-001">Friday 9:00 AM CT</option>
      <option value="slot-002">Saturday 1:00 PM CT</option><option value="slot-003">Sunday 10:00 AM CT</option>
    </select>`;
  }
  return `<article class="question-card">
    <div class="question-meta"><span>${String(index + 1).padStart(2, "0")}</span><span>${escapeHtml(question.type)}</span>${question.knockout ? "<span>knockout</span>" : ""}</div>
    <label for="${escapeHtml(id)}">${escapeHtml(question.question)}${control}</label>
  </article>`;
};

const setCandidateStatus = (message, isError = false) => {
  const element = document.querySelector("#candidate-status");
  element.textContent = message;
  element.dataset.state = isError ? "error" : "ok";
};

const renderCandidate = () => {
  document.querySelector("#candidate-questions").innerHTML = state.preview.questions.map(questionControl).join("");
};

const renderScreening = (screened) => {
  const panel = document.querySelector("#candidate-results");
  panel.classList.remove("is-hidden");
  panel.innerHTML = `<h3>Screening state: ${escapeHtml(screened.nextAction)}</h3>
    <p class="small-copy">Each state is tied to the published requirement version and remains reviewable by a recruiter.</p>
    <ul class="result-list">${screened.results.map((result) => `<li><span>${escapeHtml(result.criterionId)}</span><span class="state-badge ${result.result === "pass" ? "state-active" : "state-neutral"}">${escapeHtml(result.result)}</span></li>`).join("")}</ul>`;
};

const renderRecruiter = () => {
  const version = state.requirements;
  document.querySelector("#criteria-table").innerHTML = version.criteria.map((criterion) => `<tr>
    <td><strong>${escapeHtml(criterion.label)}</strong><br><span class="rule-copy">${escapeHtml(criterion.id)}</span></td>
    <td>${escapeHtml(criterion.candidateQuestion)}</td>
    <td><span class="rule-copy">${escapeHtml(criterion.operator)} ${escapeHtml(JSON.stringify(criterion.expectedValue))}</span></td>
    <td><span class="state-badge ${criterion.knockout ? "state-active" : "state-neutral"}">${criterion.knockout ? "Knockout" : "Review"}</span></td>
  </tr>`).join("");
  document.querySelector("#job-version").textContent = version.requirementVersionId;
  document.querySelector("#recruiter-version").textContent = `Published v${version.version}`;
  document.querySelector("#version-copy").textContent = `${version.criteria.length} criteria are linked to ${version.requirementVersionId}.`;
};

const renderPipeline = (pipeline) => {
  const table = document.querySelector("#pipeline-table");
  if (!pipeline.rows.length) {
    table.innerHTML = '<tr><td colspan="4" class="loading-state">No applications yet.</td></tr>';
    return;
  }
  table.innerHTML = pipeline.rows.map((row) => `<tr>
    <td><strong>${escapeHtml(row.contact?.name || "Candidate")}</strong><br><span class="rule-copy">${escapeHtml(row.id)}</span></td>
    <td><span class="state-badge state-neutral">${escapeHtml(row.status)}</span></td>
    <td>${escapeHtml(row.requirementVersionId)}</td>
    <td><button class="button compact-button" type="button" data-application-id="${escapeHtml(row.id)}">Open evidence</button></td>
  </tr>`).join("");
};

const loadPipeline = async () => {
  const pipeline = await json("/api/recruiter/jobs/retail-job/pipeline");
  renderPipeline(pipeline);
};

const renderDetail = (detail) => {
  const panel = document.querySelector("#recruiter-detail");
  panel.classList.remove("is-hidden");
  panel.innerHTML = `<h3>${escapeHtml(detail.contact?.name || "Candidate")} / evidence</h3>
    <p class="small-copy">${escapeHtml(detail.status)} · ${escapeHtml(detail.requirementVersionId)} · ${detail.evidence.length} evidence records · ${detail.interviews.length} interview records</p>
    <ul class="result-list">${detail.evaluations.map((evaluation) => `<li><span>${escapeHtml(evaluation.criterionId)}<small> ${escapeHtml(evaluation.explanation)}</small></span><span class="state-badge ${evaluation.result === "pass" ? "state-active" : "state-neutral"}">${escapeHtml(evaluation.result)}</span></li>`).join("")}</ul>`;
};

const collectApplication = () => {
  const form = document.querySelector("#candidate-form");
  const data = new FormData(form);
  const answers = {};
  state.preview.questions.forEach((question) => {
    const raw = data.get(question.criterionId);
    if (raw === "") return;
    if (question.criterionId === "work_authorization") answers[question.criterionId] = raw === "true";
    else if (question.criterionId === "experience") answers[question.criterionId] = Number(raw);
    else if (question.criterionId === "interview_slot") answers[question.criterionId] = { slotId: raw };
    else answers[question.criterionId] = raw;
  });
  const resumeStatus = data.get("resumeStatus");
  return {
    contact: { name: data.get("name"), email: data.get("email"), phone: null },
    consent: { sms: data.get("smsConsent") ? "granted" : "denied", email: data.get("emailConsent") ? "granted" : "denied" },
    resume: { status: resumeStatus, fileId: data.get("resumeFileId") || "resume-demo-001" },
    answers,
  };
};

const loadSlots = async () => {
  state.slots = await json(`/api/applications/${state.application.id}/slots`);
  const picker = document.querySelector("#slot-picker");
  const select = document.querySelector("#slot-select");
  select.innerHTML = state.slots.slots.filter((slot) => slot.status !== "booked").map((slot) => `<option value="${escapeHtml(slot.id)}">${escapeHtml(slot.startsAt)} (${escapeHtml(slot.timeZone)})</option>`).join("");
  picker.classList.remove("is-hidden");
};

document.querySelectorAll(".nav-button").forEach((button) => button.addEventListener("click", async () => {
  document.querySelectorAll(".nav-button").forEach((item) => {
    const active = item === button;
    item.classList.toggle("is-active", active);
    item.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll(".view-grid").forEach((view) => view.classList.toggle("is-hidden", view.id !== `${button.dataset.view}-view`));
  if (button.dataset.view === "recruiter") await loadPipeline().catch((error) => { document.querySelector("#pipeline-table").innerHTML = `<tr><td colspan="4" role="alert">${escapeHtml(error.message)}</td></tr>`; });
}));

document.querySelector("#candidate-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    state.application = await json("/api/apply/retail-operations/applications", { method: "POST", body: JSON.stringify(collectApplication()) });
    setCandidateStatus(`Application ${state.application.id} saved. Screening...`);
    const screened = await json(`/api/applications/${state.application.id}/screen`, { method: "POST", body: JSON.stringify({ idempotencyKey: `screen:${state.application.id}:${state.application.requirementVersionId}` }) });
    renderScreening(screened);
    setCandidateStatus(`Application ${state.application.id} is ${screened.nextAction}.`);
    if (screened.nextAction === "ready_to_schedule") await loadSlots();
    await loadPipeline();
  } catch (error) {
    setCandidateStatus(error.message, true);
  }
});

document.querySelector("#human-help").addEventListener("click", async () => {
  if (!state.application) {
    setCandidateStatus("Submit the application first, then human help can be queued.");
    return;
  }
  try {
    await json(`/api/applications/${state.application.id}/handoff`, { method: "POST", body: JSON.stringify({ reason: "candidate_requested_human" }) });
    setCandidateStatus("Human help requested. Automated screening is paused.");
  } catch (error) {
    setCandidateStatus(error.message, true);
  }
});

document.querySelector("#book-slot").addEventListener("click", async () => {
  try {
    const booked = await json(`/api/applications/${state.application.id}/interviews`, { method: "POST", body: JSON.stringify({ slotId: document.querySelector("#slot-select").value, channel: "sms" }) });
    setCandidateStatus(`Interview confirmed for ${booked.interview.startsAt}.`);
  } catch (error) {
    setCandidateStatus(error.message, true);
  }
});

document.querySelector("#reschedule-slot").addEventListener("click", async () => {
  try {
    const moved = await json(`/api/applications/${state.application.id}/reschedule`, { method: "POST", body: JSON.stringify({ slotId: document.querySelector("#slot-select").value, channel: "sms" }) });
    setCandidateStatus(`Interview replaced with ${moved.interview.startsAt}.`);
  } catch (error) {
    setCandidateStatus(error.message, true);
  }
});

document.querySelector("#pipeline-table").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-application-id]");
  if (!button) return;
  try {
    renderDetail(await json(`/api/recruiter/applications/${button.dataset.applicationId}`));
  } catch (error) {
    document.querySelector("#recruiter-detail").textContent = error.message;
  }
});

Promise.all([
  json("/api/apply/retail-operations"),
  json("/api/recruiter/jobs/retail-job/requirements"),
]).then(([preview, requirements]) => {
  state.preview = preview;
  state.requirements = requirements;
  document.querySelector("#job-title").textContent = preview.job.title;
  renderCandidate();
  renderRecruiter();
  return loadPipeline();
}).catch((error) => {
  document.querySelector("#candidate-questions").innerHTML = `<p class="loading-state" role="alert">Unable to load the published job: ${escapeHtml(error.message)}</p>`;
});
