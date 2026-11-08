(() => {
  const $ = (id) => document.getElementById(id);

  // The learner's own tools: profile, progress, help content, self-test and payments.
  // Each tool has its own section. Any other tab hides them, so the lesson tabs work as before.
  const SECTIONS = {
    profile: "tab-profile",
    progress: "tab-progress",
    help: "tab-help",
    test: "tab-test",
    payments: "tab-payments",
  };

  const CATEGORY_LABELS = {
    podcast: "پادکست",
    story: "داستان",
    animation: "انیمیشن",
    video: "ویدئو",
    sample: "نمونه",
    other: "دیگر",
  };

  const STATUS_LABELS = { paid: "منتظر تأیید", confirmed: "تأیید شده", pending: "در انتظار پرداخت", failed: "ناموفق" };

  function toolTab(name) {
    Object.entries(SECTIONS).forEach(([key, id]) => Z.show($(id), key === name));
    if (name === "profile") loadProfile();
    if (name === "progress") loadProgress();
    if (name === "help") loadHelp();
    if (name === "payments") loadPayments();
  }

  function nullIfEmpty(value) {
    const trimmed = (value || "").trim();
    return trimmed === "" ? null : trimmed;
  }

  // ----- Profile and level -----

  async function loadProfile() {
    try {
      const data = await Z.request("GET", "/v1/web/student/details");
      const d = data.details;
      $("pfLevel").value = data.cefr_level || "";
      $("pfAge").value = d.age ?? "";
      $("pfGender").value = d.gender || "";
      $("pfGrade").value = d.grade || "";
      $("pfAttributes").value = d.attributes || "";
      $("pfConversation").value = d.conversation_style || "";
      $("pfResponse").value = d.response_style || "";
      $("pfSample").value = d.level_sample || "";
      $("pfFree").value = d.free_text || "";
    } catch (err) {
      Z.showError($("profileError"), err.message);
    }
  }

  async function saveProfile(event) {
    event.preventDefault();
    Z.showError($("profileError"), "");
    const age = $("pfAge").value ? Number($("pfAge").value) : null;
    try {
      await Z.request("PUT", "/v1/web/student/details", {
        age,
        gender: nullIfEmpty($("pfGender").value),
        grade: nullIfEmpty($("pfGrade").value),
        attributes: $("pfAttributes").value.trim(),
        conversation_style: nullIfEmpty($("pfConversation").value),
        response_style: nullIfEmpty($("pfResponse").value),
        level_sample: $("pfSample").value.trim(),
        free_text: $("pfFree").value.trim(),
      });
      Z.showError($("profileNotice"), "");
      $("profileNotice").hidden = false;
      $("profileNotice").textContent = "اطلاعات شما ذخیره شد.";
    } catch (err) {
      Z.showError($("profileError"), err.message);
    }
  }

  async function saveLevel() {
    const level = $("pfLevel").value;
    if (!level) {
      Z.showError($("profileError"), "یک سطح را انتخاب کنید.");
      return;
    }
    try {
      await Z.request("PUT", "/v1/web/student/level", { cefr_level: level });
      $("profileNotice").hidden = false;
      $("profileNotice").textContent = `سطح ${level} ذخیره شد.`;
    } catch (err) {
      Z.showError($("profileError"), err.message);
    }
  }

  // ----- Progress -----

  function bar(percent) {
    const span = el("span", "progress-fill");
    span.style.width = `${Math.min(100, Math.max(0, percent))}%`;
    const wrap = el("div", "bar");
    wrap.appendChild(span);
    return wrap;
  }

  function el(tag, className, text) {
    return Z.el(tag, className, text);
  }

  async function loadProgress() {
    try {
      const data = await Z.request("GET", "/v1/web/student/progress");
      const stages = $("progressStages");
      const sessions = $("progressSessions");
      stages.replaceChildren();
      sessions.replaceChildren();
      if (!data.program) {
        $("progressSummary").textContent = "هنوز برنامه‌ای برای شما تعیین نشده است.";
        $("progressBar").style.width = "0%";
        return;
      }
      $("progressSummary").textContent =
        `${data.program.name} — ${data.program.duration_months} ماه — جلسه‌ی ${data.session_number} — ${data.percent}٪ کامل شده`;
      $("progressBar").style.width = `${data.percent}%`;
      data.stages.forEach((stage) => {
        const row = el("div", "stage");
        row.append(el("strong", "", `${stage.name}: ${stage.done} از ${stage.total}`), bar(stage.percent));
        stages.appendChild(row);
      });
      if (data.sessions.length === 0) {
        sessions.appendChild(el("p", "muted", "هنوز جلسه‌ای کامل نشده است."));
      }
      data.sessions.forEach((s) => {
        const row = el("div", "stage");
        row.append(el("strong", "", Z.fmtDateTime(s.started_at)), el("p", "", s.evaluation || "ارزیابی هنوز نوشته نشده است."));
        sessions.appendChild(row);
      });
    } catch (err) {
      Z.showError($("progressNotice"), err.message);
    }
  }

  // ----- Help content -----

  function helpItem(item) {
    const card = el("article", "help-item");
    card.append(el("h3", "", item.title), el("p", "muted", `${CATEGORY_LABELS[item.category] || item.category} — سطح ${item.level}`));
    if (item.interests) card.append(el("p", "muted", `موضوع: ${item.interests}`));
    if (item.has_file) {
      const src = `/v1/web/student/help-content/${item.id}/file`;
      if (item.mime && item.mime.startsWith("audio/")) {
        const audio = el("audio");
        audio.controls = true;
        audio.src = src;
        card.appendChild(audio);
      } else if (item.mime && item.mime.startsWith("video/")) {
        const video = el("video");
        video.controls = true;
        video.src = src;
        video.className = "help-video";
        card.appendChild(video);
      }
      const download = el("a", "btn-link", "دانلود");
      download.href = src;
      download.setAttribute("download", item.title);
      card.appendChild(download);
    }
    if (item.url) {
      const link = el("a", "btn-link", "باز کردن");
      link.href = item.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      card.appendChild(link);
    }
    return card;
  }

  async function loadHelp() {
    const params = new URLSearchParams();
    if ($("helpCategory").value) params.set("category", $("helpCategory").value);
    if ($("helpSearch").value.trim()) params.set("q", $("helpSearch").value.trim());
    try {
      const rows = await Z.request("GET", `/v1/web/student/help-content?${params.toString()}`);
      const list = $("helpList");
      list.replaceChildren();
      Z.show($("helpNotice"), rows.length === 0);
      $("helpNotice").textContent = rows.length === 0 ? "برای این سطح و جست‌وجو محتوایی پیدا نشد." : "";
      rows.forEach((item) => list.appendChild(helpItem(item)));
    } catch (err) {
      Z.showError($("helpNotice"), err.message);
    }
  }

  // ----- Self-test -----

  let testId = null;

  function bubble(message) {
    const node = el("p", message.role === "user" ? "bubble me" : "bubble niko", message.content);
    return node;
  }

  function renderTest(test) {
    testId = test.id;
    Z.show($("testSetup"), false);
    Z.show($("testRun"), true);
    $("testStatus").textContent = test.status === "finished" ? "آزمون تمام شد" : `سطح ${test.level || "؟"} — ${test.minutes || ""}`;
    $("testChat").replaceChildren(...test.messages.map(bubble));
    const finished = test.status === "finished";
    $("testInput").disabled = finished;
    $("testSend").disabled = finished;
    $("testFinish").hidden = finished;
    Z.show($("testResult"), finished);
    if (finished) $("testResult").textContent = test.result || "";
    $("testChat").scrollTop = $("testChat").scrollHeight;
  }

  async function startTest() {
    Z.showError($("testError"), "");
    try {
      const test = await Z.request("POST", "/v1/web/student/self-tests", {
        kind: $("testKind").value,
        skill: $("testSkill").value,
        minutes: Number($("testMinutes").value),
      });
      renderTest({ ...test, minutes: $("testMinutes").value });
    } catch (err) {
      Z.showError($("testError"), err.message);
    }
  }

  async function sendAnswer() {
    const text = $("testInput").value.trim();
    if (!text || !testId) return;
    $("testInput").value = "";
    try {
      const test = await Z.request("POST", `/v1/web/student/self-tests/${testId}/messages`, { content: text });
      renderTest(test);
    } catch (err) {
      Z.showError($("testError"), err.message);
    }
  }

  async function finishTest() {
    if (!testId) return;
    try {
      const test = await Z.request("POST", `/v1/web/student/self-tests/${testId}/finish`);
      renderTest(test);
    } catch (err) {
      Z.showError($("testError"), err.message);
    }
  }

  // ----- Payments -----

  async function loadPayments() {
    try {
      const rows = await Z.request("GET", "/v1/web/student/payments");
      const table = $("paymentTable");
      table.replaceChildren();
      const head = el("tr");
      ["تاریخ", "مبلغ (تومان)", "وضعیت"].forEach((h) => head.appendChild(el("th", "", h)));
      table.appendChild(head);
      rows.forEach((p) => {
        const tr = el("tr");
        [Z.fmtDate(p.created_at), p.amount_toman.toLocaleString("fa-IR"), STATUS_LABELS[p.status] || p.status].forEach((v) =>
          tr.appendChild(el("td", "", v)));
        table.appendChild(tr);
      });
    } catch (err) {
      Z.showError($("progressNotice"), err.message);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => toolTab(tab.dataset.tab)));
    $("profileForm").addEventListener("submit", saveProfile);
    $("pfLevelSave").addEventListener("click", saveLevel);
    $("helpGo").addEventListener("click", loadHelp);
    $("testStart").addEventListener("click", startTest);
    $("testSend").addEventListener("click", sendAnswer);
    $("testFinish").addEventListener("click", finishTest);
  });
})();
