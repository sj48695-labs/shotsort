const releaseUrl = "https://github.com/sj48695-labs/shotsort/releases/latest?source=landing";

document.querySelectorAll("[data-download-cta]").forEach((link) => {
  link.href = releaseUrl;
});

document.querySelector("#feedback-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const version = document.querySelector("#installed-version").value.trim() || "not-provided";
  const status = document.querySelector("#installation-status").value;
  const feedback = document.querySelector("#feedback-text").value.trim() || "(no additional feedback)";
  const body = `installed-version: ${version}\ninstallation-status: ${status}\n\n${feedback}`;
  const params = new URLSearchParams({ title: "Feedback: shotsort installation", body, labels: "feedback" });
  window.location.href = `https://github.com/sj48695-labs/shotsort/issues/new?${params}`;
});
