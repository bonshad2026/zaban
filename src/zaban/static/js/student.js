(() => {
  const $ = (id) => document.getElementById(id);
  let me = null;

  function showView(name) {
    Z.show($("loginView"), name === "login");
    Z.show($("appView"), name === "app");
  }

  function selectTab(name) {
    document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("is-active", tab.dataset.tab === name));
    Z.show($("tab-lesson"), name === "lesson");
    Z.show($("tab-report"), name === "report");
    if (name === "report") loadReport();
  }

  async function enterApp() {
    $("who").textContent = `سلام ${me.name}`;
    showView("app");
    selectTab("lesson");
    const { session } = await Z.request("GET", `/v1/students/${me.id}/sessions/active`);
    if (session) {
      showLesson(true);
      Lesson.resume(session);
    } else {
      showLesson(false);
    }
  }

  function showLesson(on) {
    Z.show($("setupBox"), !on);
    Z.show($("lessonBox"), on);
  }

  async function startLesson() {
    Z.showError($("startError"), "");
    $("startBtn").disabled = true;
    try {
      const session = await Z.request("POST", `/v1/students/${me.id}/sessions`, {
        duration_minutes: Number($("duration").value),
      });
      showLesson(true);
      Lesson.start(session);
    } catch (err) {
      Z.showError($("startError"), err.message);
    } finally {
      $("startBtn").disabled = false;
    }
  }

  async function loadReport() {
    const box = $("reportBox");
    box.innerHTML = "";
    box.appendChild(Z.el("p", "muted", "در حال بارگذاری گزارش…"));
    try {
      const [report, detail] = await Promise.all([
        Z.request("GET", `/v1/students/${me.id}/reports/progress`),
        Z.request("GET", `/v1/students/${me.id}`),
      ]);
      renderReport(report, detail);
    } catch (err) {
      box.innerHTML = "";
      box.appendChild(Z.el("p", "error", err.message));
    }
  }

  function bar(label, percent, planned) {
    const wrap = Z.el("div");
    const top = Z.el("div", "bar-label");
    top.appendChild(Z.el("span", null, label));
    top.appendChild(Z.el("span", null, percent === null ? "—" : `${percent}٪`));
    const track = Z.el("div", "bar");
    const fill = Z.el("span", planned ? "planned" : "");
    fill.style.width = `${Math.min(100, Math.max(0, percent || 0))}%`;
    track.appendChild(fill);
    wrap.append(top, track);
    return wrap;
  }

  function stat(label, value) {
    const box = Z.el("div", "stat");
    box.append(Z.el("div", "label", label), Z.el("div", "value", value));
    return box;
  }

  function renderReport(report, detail) {
    const box = $("reportBox");
    box.innerHTML = "";
    const level = detail.cefr_level;
    const levelText = level ? `${level} (${Z.LEVEL_FA[level]})` : "هنوز تعیین نشده";
    const completed = report.sessions.filter((s) => s.status === "completed").length;

    box.appendChild(Z.el("h2", null, "گزارش یادگیری من"));
    const stats = Z.el("div", "stats");
    stats.append(
      stat("سطح من", levelText),
      stat("وضعیت من", Z.STATUS_FA[report.status]),
      stat("جلسه‌های کامل", String(completed)),
    );
    box.appendChild(stats);

    if (report.plan) {
      box.appendChild(Z.el("h2", null, "پیشرفت نسبت به برنامه"));
      box.appendChild(bar("طبق برنامه", report.planned_percent, true));
      box.appendChild(bar("میزان یادگیری تو", report.actual_percent, false));
      box.appendChild(Z.el("p", "muted", `پایان برنامه: ${Z.fmtDate(report.plan.end_date)}`));
    }

    box.appendChild(Z.el("h2", null, "پیشنهاد برای ادامه"));
    box.appendChild(Z.el("p", "suggestion", Z.SUGGESTION_FA[report.status]));

    if (report.sessions.length) {
      box.appendChild(Z.el("h2", null, "جلسه‌های من"));
      const table = document.createElement("table");
      const head = Z.el("tr");
      ["تاریخ", "مدت", "امتیاز", "وضعیت"].forEach((title) => head.appendChild(Z.el("th", null, title)));
      table.appendChild(head);
      for (const s of report.sessions) {
        const row = Z.el("tr");
        row.appendChild(Z.el("td", null, Z.fmtDateTime(s.started_at)));
        row.appendChild(Z.el("td", null, `${s.duration_minutes} دقیقه`));
        row.appendChild(Z.el("td", null, s.score === null ? "—" : String(Math.round(s.score))));
        row.appendChild(Z.el("td", null, Z.SESSION_FA[s.status] || s.status));
        table.appendChild(row);
      }
      const scroll = Z.el("div");
      scroll.style.overflowX = "auto";
      scroll.appendChild(table);
      box.appendChild(scroll);
    } else {
      box.appendChild(Z.el("p", "muted", "هنوز جلسه‌ای ثبت نشده است. از تب «جلسه» شروع کن."));
    }
  }

  async function login(event) {
    event.preventDefault();
    const form = event.target;
    Z.showError($("loginError"), "");
    try {
      await Z.request("POST", "/v1/web/student/login", {
        username: form.username.value,
        password: form.password.value,
      });
      me = await Z.request("GET", "/v1/web/me?role=student");
      form.password.value = "";
      await enterApp();
    } catch (err) {
      Z.showError($("loginError"), err.message);
    }
  }

  async function logout() {
    await Z.request("POST", "/v1/web/logout?role=student").catch(() => {});
    location.reload();
  }

  async function boot() {
    Z.initLang();
    Lesson.init({ onEnded: () => { showLesson(false); } });
    $("loginForm").addEventListener("submit", login);
    $("logoutBtn").addEventListener("click", logout);
    $("startBtn").addEventListener("click", startLesson);
    document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => selectTab(tab.dataset.tab)));

    try {
      me = await Z.request("GET", "/v1/web/me?role=student");
    } catch (_) {
      me = null;
    }
    if (me && me.role === "student") {
      await enterApp();
    } else {
      showView("login");
    }
  }

  Z.pageRole.value = "student";
  document.addEventListener("DOMContentLoaded", boot);
})();
