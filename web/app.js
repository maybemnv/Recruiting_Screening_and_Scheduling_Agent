const state = { preview: null, requirements: null };

const json = async (url) => {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
};

const questionControl = (question, index) => {
  const id = `question-${question.criterionId}`;
  return `<article class="question-card">
    <div class="question-meta"><span>${String(index + 1).padStart(2, "0")}</span><span>${question.type}</span>${question.knockout ? "<span>knockout</span>" : ""}</div>
    <label for="${id}">${question.question}<input id="${id}" name="${question.criterionId}" placeholder="Your answer" /></label>
  </article>`;
};

const renderCandidate = () => {
  const container = document.querySelector("#candidate-questions");
  container.innerHTML = state.preview.questions.map(questionControl).join("");
};

const renderRecruiter = () => {
  const version = state.requirements;
  document.querySelector("#criteria-table").innerHTML = version.criteria.map((criterion) => `<tr>
    <td><strong>${criterion.label}</strong><br><span class="rule-copy">${criterion.id}</span></td>
    <td>${criterion.candidateQuestion}</td>
    <td><span class="rule-copy">${criterion.operator} ${JSON.stringify(criterion.expectedValue)}</span></td>
    <td><span class="state-badge ${criterion.knockout ? "state-active" : "state-neutral"}">${criterion.knockout ? "Knockout" : "Review"}</span></td>
  </tr>`).join("");
  document.querySelector("#job-version").textContent = version.requirementVersionId;
  document.querySelector("#recruiter-version").textContent = `Published v${version.version}`;
  document.querySelector("#version-copy").textContent = `${version.criteria.length} criteria are linked to ${version.requirementVersionId}.`;
};

const load = async () => {
  const [preview, requirements] = await Promise.all([
    json("/api/apply/retail-operations"),
    json("/api/recruiter/jobs/retail-job/requirements"),
  ]);
  state.preview = preview;
  state.requirements = requirements;
  document.querySelector("#job-title").textContent = preview.job.title;
  renderCandidate();
  renderRecruiter();
};

document.querySelectorAll(".nav-button").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll(".nav-button").forEach((item) => {
    const active = item === button;
    item.classList.toggle("is-active", active);
    item.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll(".view-grid").forEach((view) => view.classList.toggle("is-hidden", view.id !== `${button.dataset.view}-view`));
}));

document.querySelector("#save-preview").addEventListener("click", () => {
  document.querySelector("#candidate-status").textContent = "Preview answer saved locally. Application capture is next.";
});
document.querySelector("#human-help").addEventListener("click", () => {
  document.querySelector("#candidate-status").textContent = "Human help requested in demo mode.";
});

load().catch((error) => {
  document.querySelector("#candidate-questions").innerHTML = `<p class="loading-state" role="alert">Unable to load the published job: ${error.message}</p>`;
});
