const { test, expect } = require("@playwright/test");

async function submitPassingCandidate(page) {
  await page.goto("/");
  await page.getByLabel("Name").fill("Jordan Lee");
  await page.getByRole("textbox", { name: "Email", exact: true }).fill("jordan@example.com");
  await page.getByLabel("Are you authorized to work in the job location?").selectOption("true");
  await page.getByLabel("Which days and times are you available to work?").fill("weekends");
  await page.getByLabel("Are you located in or able to commute to Chicago?").fill("Chicago");
  await page.getByLabel("How many years of relevant customer-facing experience do you have?").fill("3");
  await page.getByLabel("Which available interview slot works best for you?").selectOption("slot-001");
  await page.getByLabel("Resume status").selectOption("complete");
  await page.getByRole("button", { name: "Submit application" }).click();
  await expect(page.getByRole("heading", { name: "Screening state: ready_to_schedule" })).toBeVisible();
}

test("candidate-to-recruiter demo records scheduling, reasoned disposition, and analytics", async ({ page }) => {
  await submitPassingCandidate(page);
  await page.getByLabel("Choose a Chicago-time-zone slot").selectOption("slot-001");
  await page.getByRole("button", { name: "Confirm interview slot" }).click();
  await expect(page.getByRole("status")).toContainText("Interview confirmed");
  await page.getByLabel("Choose a Chicago-time-zone slot").selectOption("slot-002");
  await page.getByRole("button", { name: "Replace confirmed slot" }).click();
  await expect(page.getByRole("status")).toContainText("Interview replaced");

  await page.getByRole("tab", { name: "Recruiter" }).click();
  await page.getByRole("button", { name: "Open evidence" }).click();
  await expect(page.getByLabel("Candidate evidence detail")).toContainText("6 evidence records");
  await expect(page.getByLabel("Candidate evidence detail")).toContainText("2 interview records");
  await expect(page.getByLabel("Candidate evidence detail")).toContainText("2 message records");
  await page.getByLabel("Final disposition").selectOption("advance");
  await page.getByLabel("Disposition reason").fill("Explicit evidence and interview availability reviewed by a human.");
  await page.getByRole("button", { name: "Record human disposition" }).click();

  await expect(page.getByLabel("Candidate evidence detail")).toContainText("advance");
  await expect(page.getByLabel("Candidate evidence detail")).toContainText("fixture-recruiter");
  await expect(page.getByLabel("Recruiting funnel analytics")).toContainText("Human-recorded final dispositions");
  await expect(page.getByLabel("Recruiting funnel analytics")).toContainText("1");
});

test("keyboard users can operate critical candidate and recruiter actions with visible focus", async ({ page }) => {
  await page.goto("/");
  const candidateTab = page.getByRole("tab", { name: "Candidate" });
  const recruiterTab = page.getByRole("tab", { name: "Recruiter" });
  await candidateTab.focus();
  await page.keyboard.press("End");
  await expect(recruiterTab).toBeFocused();
  await expect(page.getByRole("tabpanel", { name: "Recruiter" })).toBeVisible();
  await page.keyboard.press("Home");
  await expect(candidateTab).toBeFocused();
  await expect(page.getByRole("tabpanel", { name: "Candidate" })).toBeVisible();

  const humanHelp = page.getByRole("button", { name: "Request human help" });
  await humanHelp.focus();
  await expect(humanHelp).toHaveCSS("outline-style", "solid");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("status")).toContainText("Submit the application first");

  await page.getByLabel("Name").fill("Keyboard Candidate");
  await page.getByRole("textbox", { name: "Email", exact: true }).fill("keyboard@example.com");
  await page.getByLabel("Are you authorized to work in the job location?").selectOption("true");
  await page.getByLabel("Which days and times are you available to work?").fill("weekends");
  await page.getByLabel("Are you located in or able to commute to Chicago?").fill("Chicago");
  await page.getByLabel("How many years of relevant customer-facing experience do you have?").fill("4");
  await page.getByLabel("Which available interview slot works best for you?").selectOption("slot-001");
  const submit = page.getByRole("button", { name: "Submit application" });
  await submit.focus();
  await expect(submit).toHaveCSS("outline-style", "solid");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Screening state: ready_to_schedule" })).toBeVisible();

  const confirm = page.getByRole("button", { name: "Confirm interview slot" });
  await confirm.focus();
  await expect(confirm).toHaveCSS("outline-style", "solid");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("status")).toContainText("Interview confirmed");

  await humanHelp.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("status")).toContainText("Human help requested");

  await candidateTab.focus();
  await page.keyboard.press("ArrowRight");
  await expect(recruiterTab).toBeFocused();
  await page.getByRole("button", { name: "Open evidence" }).last().focus();
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("Candidate evidence detail")).toContainText("Keyboard Candidate");
});

test("candidate primary flow fits a 320px viewport without document overflow", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await submitPassingCandidate(page);
  const dimensions = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);
  await expect(page.getByRole("button", { name: "Confirm interview slot" })).toBeVisible();
});
