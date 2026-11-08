(() => {
  const $ = (id) => document.getElementById(id);
  let childId = null;

  // A parent reads and edits the profile and progress of the child whose detail box is open.
  // parent.js sets data-student-id on the detail box when a child is opened.
  function nullIfEmpty(value) {
    const trimmed = (value || "").trim();
    return trimmed === "" ? null : trimmed;
  }

  function fill(details) {
    $("cdAge").value = details.age ?? "";
    $("cdGender").value = details.gender || "";
    $("cdGrade").value = details.grade || "";
    $("cdAttributes").value = details.attributes || "";
    $("cdConversation").value = details.conversation_style || "";
    $("cdResponse").value = details.response_style || "";
    $("cdSample").value = details.level_sample || "";
    $("cdFree").value = details.free_text || "";
  }

  async function loadChild(id) {
    childId = id;
    try {
      const [info, progress] = await Promise.all([
        Z.request("GET", `/v1/web/parent/children/${id}/details`),
        Z.request("GET", `/v1/web/parent/children/${id}/progress`),
      ]);
      fill(info.details);
      renderProgress(progress);
    } catch (err) {
      Z.showError($("cdNotice"), err.message);
    }
  }

  function renderProgress(data) {
    const stages = $("cdStages");
    const sessions = $("cdSessions");
    stages.replaceChildren();
    sessions.replaceChildren();
    if (!data.program) {
      $("cdProgress").textContent = "هنوز برنامه‌ای برای این کودک تعیین نشده است.";
      return;
    }
    $("cdProgress").textContent =
      `${data.program.name} — ${data.program.duration_months} ماه — جلسه‌ی ${data.session_number} — ${data.percent}٪ کامل شده`;
    data.stages.forEach((stage) => {
      const p = Z.el("p", "", `${stage.name}: ${stage.done} از ${stage.total} (${stage.percent}٪)`);
      stages.appendChild(p);
    });
    if (data.sessions.length === 0) sessions.appendChild(Z.el("p", "muted", "هنوز جلسه‌ای کامل نشده است."));
    data.sessions.forEach((s) => {
      sessions.appendChild(Z.el("p", "", `${Z.fmtDateTime(s.started_at)}: ${s.evaluation || "ارزیابی هنوز نوشته نشده است."}`));
    });
  }

  async function saveChild(event) {
    event.preventDefault();
    if (!childId) return;
    try {
      await Z.request("PUT", `/v1/web/parent/children/${childId}/details`, {
        age: $("cdAge").value ? Number($("cdAge").value) : null,
        gender: nullIfEmpty($("cdGender").value),
        grade: nullIfEmpty($("cdGrade").value),
        attributes: $("cdAttributes").value.trim(),
        conversation_style: nullIfEmpty($("cdConversation").value),
        response_style: nullIfEmpty($("cdResponse").value),
        level_sample: $("cdSample").value.trim(),
        free_text: $("cdFree").value.trim(),
      });
      $("cdNotice").hidden = false;
      $("cdNotice").textContent = "اطلاعات کودک ذخیره شد.";
    } catch (err) {
      Z.showError($("cdNotice"), err.message);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const box = $("detailBox");
    if (box) {
      // Watch the data attribute that parent.js sets when another child is opened.
      new MutationObserver(() => {
        const id = box.dataset.studentId;
        if (id && id !== childId) loadChild(id);
      }).observe(box, { attributes: true, attributeFilter: ["data-student-id"] });
    }
    $("cdForm").addEventListener("submit", saveChild);
  });
})();
