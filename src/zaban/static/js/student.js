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
    Z.show($("tab-accent"), name === "accent");
    Z.show($("tab-report"), name === "report");
    if (name === "accent") renderAccents();
    if (name === "report") loadReport();
  }

  // ----- Accent -----

  let accentCode = "en-US";

  async function loadAccent() {
    try {
      const data = await Z.request("GET", "/v1/web/student/accent");
      accentCode = data.accent;
    } catch (_) {
      accentCode = "en-US";
    }
    Accents.setCurrent(accentCode);
  }

  // Recorded samples uploaded by the administrator. The newest sample for an accent is the one played.
  let samples = [];

  async function loadSamples() {
    try {
      samples = await Z.request("GET", "/v1/web/student/voice-samples");
    } catch (_) {
      samples = [];
    }
  }

  function playAccent(code) {
    const sample = samples.find((s) => s.accent === code);
    if (sample) {
      new Audio(`/v1/web/student/voice-samples/${sample.id}/audio`).play().catch(() => {
        Z.showError($("accentNotice"), "نمونه‌ی صوتی پخش نشد. دوباره تلاش کنید.");
      });
      return;
    }
    if (!Accents.speakSample(code)) {
      Z.showError($("accentNotice"), "صدای این لهجه روی این دستگاه پیدا نشد.");
    }
  }

  async function renderAccents() {
    await loadSamples();
    const list = $("accentList");
    list.replaceChildren();
    const hasSound = (code) => samples.some((s) => s.accent === code) || Accents.voiceFor(code);
    const missing = Accents.LIST.filter((a) => !hasSound(a.code));
    Z.show($("accentNotice"), missing.length > 0);
    $("accentNotice").textContent = missing.length
      ? "این دستگاه بعضی لهجه‌ها را ندارد. برای همه‌ی لهجه‌ها، Chrome یا Edge را با صدای انگلیسی نصب‌شده امتحان کنید."
      : "";
    Accents.LIST.forEach((accent) => {
      const selected = accent.code === accentCode;
      const card = Z.el("div", "accent-card" + (selected ? " is-selected" : ""));
      card.appendChild(Z.el("strong", null, `${accent.name} (${accent.nameEn})`));
      card.appendChild(Z.el("p", "sample", accent.sample));
      const recorded = samples.find((s) => s.accent === accent.code);
      if (recorded) card.appendChild(Z.el("p", "muted", `نمونه‌ی ضبط‌شده: ${recorded.name}`));
      const actions = Z.el("div", "actions");
      const play = Z.el("button", "ghost", "پخش نمونه");
      play.type = "button";
      play.addEventListener("click", () => playAccent(accent.code));
      const choose = Z.el("button", "", selected ? "انتخاب‌شده" : "انتخاب این لهجه");
      choose.type = "button";
      choose.disabled = selected;
      choose.addEventListener("click", () => chooseAccent(accent.code));
      actions.append(play, choose);
      card.appendChild(actions);
      list.appendChild(card);
    });
  }

  async function chooseAccent(code) {
    Z.showError($("accentNotice"), "");
    try {
      await Z.request("POST", "/v1/web/student/accent", { accent: code });
      accentCode = code;
      Accents.setCurrent(code);
      renderAccents();
    } catch (err) {
      Z.showError($("accentNotice"), err.message);
    }
  }

  async function enterApp() {
    showView("app");
    showLevel();
    loadAccent();
    // Lessons need the plan of the adult who owns this profile. Without it, the learner is told why and cannot start.
    if (me.has_active_plan === false) {
      $("startBtn").disabled = true;
      Z.showError($("startError"), "پلن والدتان فعال نیست، بنابراین جلسه فعلاً شروع نمی‌شود. لطفاً به والدتان بگویید پلن را فعال کنند.");
    }
    selectTab("lesson");
    const { session } = await Z.request("GET", `/v1/students/${me.id}/sessions/active`);
    loadProgram();
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
    Z.show($("programBox"), !on);
    if (!on) loadProgram();
  }

  // The learner's place in their program: the lesson they are on, and the whole list with what is done.
  async function loadProgram() {
    const data = await Z.request("GET", "/v1/web/student/program").catch(() => null);
    if (!data || !data.program) {
      Z.show($("programBox"), false);
      return;
    }
    const program = data.program;
    Z.show($("programBox"), true);
    $("programName").textContent = `${program.name}: ${program.done} از ${program.total} جلسه انجام شده`;
    const notice = $("programNotice");
    if (program.status === "waiting_approval") {
      notice.textContent = "این بخش از برنامه تمام شد. برنامه‌ی بعدی بعد از تأیید والدین یا معلم ادامه پیدا می‌کند.";
    } else if (program.status === "finished") {
      notice.textContent = "برنامه‌ی شما تمام شد. آفرین!";
    }
    Z.show(notice, Boolean(notice.textContent));
    Z.show($("programCurrent"), Boolean(data.current));
    if (data.current) {
      $("programTitle").textContent = `جلسه ${data.current.number}: ${data.current.title}`;
      $("programActivity").textContent = data.current.activity;
      $("programPhrases").textContent = data.current.phrases.join("  ·  ");
    }
    const list = $("programList");
    list.innerHTML = "";
    data.items.forEach((item) => {
      const mark = item.state === "done" ? "✓ " : item.state === "current" ? "➜ " : "";
      const li = Z.el("li", item.state === "next" ? "muted" : null, `${mark}${item.title}`);
      list.appendChild(li);
    });
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


  // The learner sees their level before a lesson. Without one, they can take a short check or ask a parent.
  async function showLevel() {
    try {
      const student = await Z.request("GET", `/v1/students/${me.id}`);
      const notice = $("levelNotice");
      if (student.cefr_level) {
        notice.textContent = `سطح شما: ${student.cefr_level} (${Z.LEVEL_FA[student.cefr_level]})`;
        Z.show($("levelTestBox"), false);
      } else {
        notice.textContent = "سطح شما هنوز تعیین نشده است. با ۶ سؤال کوتاه سطحتان را پیدا کنید، یا والدتان می‌توانند آن را انتخاب کنند. تا آن زمان Niko از سطح مقدماتی شروع می‌کند.";
        Z.show($("levelTestBox"), true);
      }
      Z.show(notice, true);
    } catch (_) {
      Z.show($("levelNotice"), false);
    }
  }

  async function startLevelTest() {
    Z.showError($("levelTestError"), "");
    try {
      const questions = await Z.request("GET", "/v1/web/student/level-test");
      const box = $("levelQuestions");
      box.replaceChildren();
      questions.forEach((question, i) => {
        const fieldset = document.createElement("fieldset");
        fieldset.appendChild(Z.el("legend", null, `${i + 1}. ${question.text}`));
        question.options.forEach((option, j) => {
          const label = Z.el("label", "inline");
          const input = document.createElement("input");
          input.type = "radio";
          input.name = `q${i}`;
          input.value = String(j);
          input.required = true;
          label.append(input, document.createTextNode(` ${option}`));
          fieldset.appendChild(label);
        });
        box.appendChild(fieldset);
      });
      Z.show($("levelTestStart"), false);
      Z.show($("levelTestForm"), true);
    } catch (err) {
      Z.showError($("levelTestError"), err.message);
    }
  }

  async function submitLevelTest(event) {
    event.preventDefault();
    const form = event.target;
    Z.showError($("levelTestError"), "");
    const count = $("levelQuestions").querySelectorAll("fieldset").length;
    const answers = [];
    for (let i = 0; i < count; i++) {
      answers.push(Number(form.querySelector(`input[name="q${i}"]:checked`).value));
    }
    try {
      const result = await Z.request("POST", "/v1/web/student/level-test", { answers });
      Z.show($("levelTestForm"), false);
      Z.show($("levelTestStart"), false);
      $("levelNotice").textContent = `سطح شما تعیین شد: ${result.level} (${Z.LEVEL_FA[result.level]}). ${result.score} از ${result.total} پاسخ درست بود.`;
      Z.show($("levelTestBox"), false);
    } catch (err) {
      Z.showError($("levelTestError"), err.message);
    }
  }

  async function boot() {
    Z.initLang();
    Lesson.init({ onEnded: () => { showLesson(false); } });
    $("loginForm").addEventListener("submit", login);
    $("startBtn").addEventListener("click", startLesson);
    $("levelTestStart").addEventListener("click", startLevelTest);
    $("levelTestForm").addEventListener("submit", submitLevelTest);
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
