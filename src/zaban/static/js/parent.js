(() => {
  const $ = (id) => document.getElementById(id);
  let me = null;
  let students = [];
  let selectedId = null;

  function showView(name) {
    Z.show($("loginView"), name === "login");
    Z.show($("appView"), name === "app");
  }

  async function enterApp() {
    $("who").textContent = `سلام ${me.name}`;
    showView("app");
    await loadStudents();
  }

  // ----- Student list and creation -----

  async function loadStudents() {
    students = await Z.request("GET", "/v1/students");
    renderStudents();
    if (selectedId && students.some((s) => s.id === selectedId)) {
      await showStudent(selectedId);
    } else {
      selectedId = null;
      Z.show($("detailBox"), false);
    }
  }

  function renderStudents() {
    const list = $("studentList");
    list.innerHTML = "";
    if (!students.length) {
      list.appendChild(Z.el("p", "muted", "هنوز فرزندی ثبت نشده است. از فرم زیر یک حساب برای فرزندتان بسازید."));
      return;
    }
    for (const s of students) {
      const card = Z.el("button", "student-card" + (s.id === selectedId ? " is-selected" : ""));
      card.type = "button";
      card.appendChild(Z.el("strong", null, s.display_name || s.username || "بدون نام"));
      card.appendChild(Z.el("span", "muted", s.cefr_level ? `سطح ${s.cefr_level} (${Z.LEVEL_FA[s.cefr_level]})` : "سطح هنوز تعیین نشده"));
      card.addEventListener("click", () => showStudent(s.id));
      list.appendChild(card);
    }
  }

  async function addStudent(event) {
    event.preventDefault();
    const form = event.target;
    Z.showError($("addError"), "");
    Z.show($("addOk"), false);
    if (!form.consent.checked) {
      Z.showError($("addError"), "برای ساخت حساب، باید رضایت والد را تأیید کنید.");
      return;
    }
    try {
      const created = await Z.request("POST", "/v1/students", {
        display_name: form.display_name.value.trim(),
        age_band: form.age_band.value,
        username: form.username.value.trim().toLowerCase(),
        password: form.password.value,
      });
      await Z.request("POST", `/v1/students/${created.id}/consent`, { accepted: true, text_version: "v1" });
      form.reset();
      selectedId = created.id;
      $("addOk").textContent = "حساب فرزندتان ساخته شد. حالا می‌تواند با نام کاربری و رمز وارد شود.";
      Z.show($("addOk"), true);
      await loadStudents();
    } catch (err) {
      Z.showError($("addError"), err.message);
    }
  }

  // ----- Selected student -----

  async function showStudent(id) {
    selectedId = id;
    renderStudents();
    const s = await Z.request("GET", `/v1/students/${id}`);
    Z.show($("detailBox"), true);
    $("detailTitle").textContent = s.display_name || s.username || "فرزند";
    $("infoName").value = s.display_name || "";
    $("infoAge").value = s.age_band;
    $("levelNow").textContent = s.cefr_level ? `${s.cefr_level} (${Z.LEVEL_FA[s.cefr_level]})` : "هنوز تعیین نشده";
    $("planNow").textContent = s.active_plan ? `${s.active_plan.goal} — پایان: ${Z.fmtDate(s.active_plan.end_date)}` : "برنامه‌ای فعال نیست";
    Z.show($("consentBox"), !s.has_consent);
    Z.show($("placementForm"), s.has_consent);
    Z.show($("planForm"), s.has_consent);
    $("loginNow").textContent = s.username ? `نام کاربری: ${s.username}` : "این فرزند ورود جداگانه ندارد";
    Z.show($("passwordForm"), Boolean(s.username));
    await Promise.all([loadReports(id)]);
  }

  async function loadReports(id) {
    const [report, usage] = await Promise.all([
      Z.request("GET", `/v1/students/${id}/reports/parent`),
      Z.request("GET", `/v1/students/${id}/usage`),
    ]);
    const box = $("reportBox");
    box.innerHTML = "";
    box.appendChild(Z.el("p", "suggestion", report.summary_fa));

    const stats = Z.el("div", "stats");
    stats.append(
      stat("وضعیت پیشرفت", Z.STATUS_FA[report.status]),
      stat("جلسه‌های کامل", String(usage.lessons_completed)),
      stat("مدت کل جلسه‌ها", `${usage.minutes_used} دقیقه`),
      stat("آخرین جلسه", usage.last_lesson_at ? Z.fmtDateTime(usage.last_lesson_at) : "هنوز نداشته"),
    );
    box.appendChild(stats);

    if (report.planned_percent !== null) {
      box.appendChild(bar("طبق برنامه", report.planned_percent, true));
    }
    if (report.actual_percent !== null) {
      box.appendChild(bar("میزان یادگیری", report.actual_percent, false));
    }
    box.appendChild(Z.el("p", "muted", Z.SUGGESTION_FA[report.status]));
    if (report.milestones && report.milestones.length) {
      const list = Z.el("ul", "plain");
      for (const m of report.milestones) {
        list.appendChild(Z.el("li", null, `ماه ${m.month}: هدف ${m.target_percent}٪`));
      }
      box.appendChild(list);
    }
  }

  function stat(label, value) {
    const box = Z.el("div", "stat");
    box.append(Z.el("div", "label", label), Z.el("div", "value", value));
    return box;
  }

  function bar(label, percent, planned) {
    const wrap = Z.el("div");
    const top = Z.el("div", "bar-label");
    top.append(Z.el("span", null, label), Z.el("span", null, `${percent}٪`));
    const track = Z.el("div", "bar");
    const fill = Z.el("span", planned ? "planned" : "");
    fill.style.width = `${Math.min(100, Math.max(0, percent))}%`;
    track.appendChild(fill);
    wrap.append(top, track);
    return wrap;
  }

  async function saveInfo(event) {
    event.preventDefault();
    Z.showError($("infoError"), "");
    try {
      await Z.request("PATCH", `/v1/students/${selectedId}`, {
        display_name: $("infoName").value.trim(),
        age_band: $("infoAge").value,
      });
      await loadStudents();
      flash("infoOk", "اطلاعات ذخیره شد.");
    } catch (err) {
      Z.showError($("infoError"), err.message);
    }
  }

  async function giveConsent() {
    try {
      await Z.request("POST", `/v1/students/${selectedId}/consent`, { accepted: true, text_version: "v1" });
      await showStudent(selectedId);
    } catch (err) {
      alert(err.message);
    }
  }

  async function savePlacement(event) {
    event.preventDefault();
    Z.showError($("placementError"), "");
    try {
      await Z.request("POST", `/v1/students/${selectedId}/placement`, { score: Number($("placementScore").value) });
      await showStudent(selectedId);
      flash("placementOk", "سطح ذخیره شد.");
    } catch (err) {
      Z.showError($("placementError"), err.message);
    }
  }

  async function savePlan(event) {
    event.preventDefault();
    Z.showError($("planError"), "");
    try {
      await Z.request("POST", `/v1/students/${selectedId}/plans`, {
        goal: $("planGoal").value.trim(),
        months: Number($("planMonths").value),
        sessions_per_week: Number($("planPerWeek").value),
        minutes_per_session: Number($("planMinutes").value),
      });
      await showStudent(selectedId);
      flash("planOk", "برنامه ساخته شد.");
    } catch (err) {
      Z.showError($("planError"), err.message);
    }
  }

  async function savePassword(event) {
    event.preventDefault();
    Z.showError($("passwordError"), "");
    try {
      await Z.request("POST", `/v1/students/${selectedId}/password`, { password: $("newPasswordForChild").value });
      $("newPasswordForChild").value = "";
      flash("passwordOk", "رمز ورود تغییر کرد.");
    } catch (err) {
      Z.showError($("passwordError"), err.message);
    }
  }

  async function removeStudent() {
    if (!confirm("همه‌ی اطلاعات و جلسه‌های این فرزند پاک شود؟ این کار برگشت ندارد.")) return;
    try {
      await Z.request("DELETE", `/v1/students/${selectedId}`);
      selectedId = null;
      await loadStudents();
    } catch (err) {
      alert(err.message);
    }
  }

  function flash(id, text) {
    const node = $(id);
    node.textContent = text;
    Z.show(node, true);
    setTimeout(() => Z.show(node, false), 3500);
  }

  // ----- Sign-in with a mobile number and an SMS code -----

  // The number the code was sent to. Changing the number starts the steps again.
  let phoneSent = null;

  function resetCodeStep() {
    phoneSent = null;
    Z.show($("codeStep"), false);
    $("parentCode").value = "";
  }

  async function sendCode() {
    Z.showError($("loginError"), "");
    const phone = $("parentPhone").value.trim();
    try {
      await Z.request("POST", "/v1/web/user/otp/request", { phone });
      phoneSent = phone;
      Z.show($("codeStep"), true);
      $("parentCode").focus();
    } catch (err) {
      Z.showError($("loginError"), err.message);
    }
  }

  async function login(event) {
    event.preventDefault();
    // Enter on the phone field sends the code first. The code and name are entered on the next step.
    if (!phoneSent) return sendCode();
    const form = event.target;
    Z.showError($("loginError"), "");
    try {
      await Z.request("POST", "/v1/web/user/otp/verify", {
        phone: phoneSent,
        code: form.code.value.trim(),
        full_name: form.full_name.value.trim() || null,
      });
      me = await Z.request("GET", "/v1/web/me?role=parent");
      form.code.value = "";
      await enterApp();
    } catch (err) {
      Z.showError($("loginError"), err.message);
    }
  }

  // ----- Learning for myself -----

  async function startOwnLearning() {
    Z.showError($("selfError"), "");
    try {
      await Z.request("POST", "/v1/web/user/self");
      location.href = "/student";
    } catch (err) {
      Z.showError($("selfError"), err.message);
    }
  }

  async function logout() {
    await Z.request("POST", "/v1/web/logout?role=parent").catch(() => {});
    location.reload();
  }

  async function logoutEverywhere() {
    if (!confirm("از همه‌ی دستگاه‌ها خارج شوید؟ دوباره باید با کد پیامکی وارد شوید.")) return;
    await Z.request("POST", "/v1/web/user/logout-all").catch(() => {});
    location.reload();
  }

  async function boot() {
    Z.initLang();
    $("loginForm").addEventListener("submit", login);
    $("sendCodeBtn").addEventListener("click", sendCode);
    $("resendBtn").addEventListener("click", sendCode);
    $("parentPhone").addEventListener("input", resetCodeStep);
    $("selfBtn").addEventListener("click", startOwnLearning);
    $("logoutBtn").addEventListener("click", logout);
    $("logoutAllBtn").addEventListener("click", logoutEverywhere);
    $("addForm").addEventListener("submit", addStudent);
    $("infoForm").addEventListener("submit", saveInfo);
    $("consentBtn").addEventListener("click", giveConsent);
    $("placementForm").addEventListener("submit", savePlacement);
    $("planForm").addEventListener("submit", savePlan);
    $("passwordForm").addEventListener("submit", savePassword);
    $("deleteBtn").addEventListener("click", removeStudent);

    try {
      me = await Z.request("GET", "/v1/web/me?role=parent");
    } catch (_) {
      me = null;
    }
    if (me && me.role === "parent") {
      await enterApp();
    } else {
      showView("login");
    }
  }

  Z.pageRole.value = "parent";
  document.addEventListener("DOMContentLoaded", boot);
})();
