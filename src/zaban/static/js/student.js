(() => {
  const $ = (id) => document.getElementById(id);
  let me = null;

  function showView() {
    Z.show($("appView"), true);
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
        Z.showError($("accentNotice"), Z.tr("نمونه‌ی صوتی پخش نشد. دوباره تلاش کنید."));
      });
      return;
    }
    if (!Accents.speakSample(code)) {
      Z.showError($("accentNotice"), Z.tr("صدای این لهجه روی این دستگاه پیدا نشد."));
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
      ? Z.tr("این دستگاه بعضی لهجه‌ها را ندارد. برای همه‌ی لهجه‌ها، Chrome یا Edge را با صدای انگلیسی نصب‌شده امتحان کنید.")
      : "";
    Accents.LIST.forEach((accent) => {
      const selected = accent.code === accentCode;
      const card = Z.el("div", "accent-card" + (selected ? " is-selected" : ""));
      card.appendChild(Z.el("strong", null, `${accent.name} (${accent.nameEn})`));
      card.appendChild(Z.el("p", "sample", accent.sample));
      const recorded = samples.find((s) => s.accent === accent.code);
      if (recorded) card.appendChild(Z.el("p", "muted", Z.pick(`نمونه‌ی ضبط‌شده: ${recorded.name}`, `Recorded sample: ${recorded.name}`)));
      const actions = Z.el("div", "actions");
      const play = Z.el("button", "ghost", Z.tr("پخش نمونه"));
      play.type = "button";
      play.addEventListener("click", () => playAccent(accent.code));
      const choose = Z.el("button", "", selected ? Z.tr("انتخاب‌شده") : Z.tr("انتخاب این لهجه"));
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
    showView();
    showLevel();
    loadAccent();
    // Lessons need the plan of the adult who owns this profile. Without it, the learner is told why and cannot start.
    if (me.has_active_plan === false) {
      $("startBtn").disabled = true;
      Z.showError($("startError"), Z.tr("پلن والدتان فعال نیست، بنابراین جلسه فعلاً شروع نمی‌شود. لطفاً به والدتان بگویید پلن را فعال کنند."));
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
    // A header link can open a tool directly, for example ?tab=progress or ?tab=payments.
    const wanted = new URLSearchParams(location.search).get("tab");
    const tool = wanted && wanted !== "lesson" ? document.querySelector(`.tab[data-tab="${wanted}"]`) : null;
    if (tool) tool.click();
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
    $("programName").textContent = Z.pick(`${program.name}: ${program.done} از ${program.total} جلسه انجام شده`, `${program.name}: ${program.done} of ${program.total} lessons done`);
    const notice = $("programNotice");
    if (program.status === "finished") {
      notice.textContent = Z.tr("برنامه‌ی شما تمام شد. آفرین!");
    }
    Z.show(notice, Boolean(notice.textContent));
    Z.show($("programCurrent"), Boolean(data.current));
    if (data.current) {
      const currentTitle = Z.pick(data.current.title, data.current.title_en || data.current.title);
      $("programTitle").textContent = Z.pick(`جلسه ${data.current.number}: ${data.current.title}`, `Lesson ${data.current.number}: ${currentTitle}`);
      $("programActivity").textContent = data.current.activity;
      $("programPhrases").textContent = data.current.phrases.join("  ·  ");
    }
    programItems = data.items;
    showFullProgram(false);
    renderProgramWindow();
    renderProgramList();
  }

  // The learner's path: a few lessons before the current one, the current one, and the next few.
  // Done lessons are green, the current lesson is gold, and the rest are grey.
  const PROGRAM_BEFORE = 2;
  const PROGRAM_AFTER = 3;
  let programItems = [];

  function programRow(item) {
    const mark = item.state === "done" ? "✓ " : item.state === "current" ? "➜ " : "";
    const title = Z.pick(item.title, item.title_en || item.title);
    const row = Z.el("li", `plan-item is-${item.state}`, `${mark}${Z.pick("جلسه", "Lesson")} ${item.number}: ${title}`);
    // How many times this lesson was played, and its average score when the AI has scored it.
    if (item.visits) {
      const times = Z.pick(`${item.visits} بار`, `${item.visits} time${item.visits === 1 ? "" : "s"}`);
      const score = item.average == null ? "" : Z.pick(` — میانگین ${item.average}`, ` — average ${item.average}`);
      row.appendChild(Z.el("span", "plan-meta muted", ` (${times}${score})`));
    }
    return row;
  }

  function renderProgramWindow() {
    const list = $("programWindow");
    list.replaceChildren();
    if (programItems.length === 0) return;
    const current = programItems.findIndex((item) => item.state === "current");
    // A finished program has no current lesson, so the window ends at the last lesson.
    const index = current === -1 ? programItems.length - 1 : current;
    const start = Math.max(0, index - PROGRAM_BEFORE);
    const end = Math.min(programItems.length, index + PROGRAM_AFTER + 1);
    programItems.slice(start, end).forEach((item) => list.appendChild(programRow(item)));
  }

  function renderProgramList() {
    const list = $("programList");
    list.replaceChildren(...programItems.map(programRow));
  }

  function showFullProgram(on) {
    Z.show($("programWindow"), !on);
    Z.show($("programShowAll"), !on);
    Z.show($("programFullBox"), on);
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
    box.appendChild(Z.el("p", "muted", Z.tr("در حال بارگذاری گزارش…")));
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
    const levelText = level ? `${level} (${Z.LEVEL_FA[level]})` : Z.tr("هنوز تعیین نشده");
    const completed = report.sessions.filter((s) => s.status === "completed").length;

    box.appendChild(Z.el("h2", null, Z.tr("گزارش یادگیری من")));
    const stats = Z.el("div", "stats");
    stats.append(
      stat(Z.tr("سطح من"), levelText),
      stat(Z.tr("وضعیت من"), Z.STATUS_FA[report.status]),
      stat(Z.tr("جلسه‌های کامل"), String(completed)),
    );
    box.appendChild(stats);

    if (report.plan) {
      box.appendChild(Z.el("h2", null, Z.tr("پیشرفت نسبت به برنامه")));
      box.appendChild(bar(Z.tr("طبق برنامه"), report.planned_percent, true));
      box.appendChild(bar(Z.tr("میزان یادگیری تو"), report.actual_percent, false));
      box.appendChild(Z.el("p", "muted", Z.pick(`پایان برنامه: ${Z.fmtDate(report.plan.end_date)}`, `The plan ends: ${Z.fmtDate(report.plan.end_date)}`)));
    }

    box.appendChild(Z.el("h2", null, Z.tr("پیشنهاد برای ادامه")));
    box.appendChild(Z.el("p", "suggestion", Z.SUGGESTION_FA[report.status]));

    if (report.sessions.length) {
      box.appendChild(Z.el("h2", null, Z.tr("جلسه‌های من")));
      const table = document.createElement("table");
      const head = Z.el("tr");
      [Z.tr("تاریخ"), Z.tr("عنوان جلسه"), Z.tr("مدت"), Z.tr("امتیاز"), Z.tr("وضعیت")].forEach((title) => head.appendChild(Z.el("th", null, title)));
      table.appendChild(head);
      for (const s of report.sessions) {
        const row = Z.el("tr");
        row.appendChild(Z.el("td", null, Z.fmtDateTime(s.started_at)));
        const title = s.lesson_number
          ? `${Z.pick("جلسه", "Lesson")} ${s.lesson_number}: ${Z.pick(s.lesson_title, s.lesson_title_en || s.lesson_title)}`
          : Z.tr("گفتگوی آزاد با معلم");
        row.appendChild(Z.el("td", null, title));
        row.appendChild(Z.el("td", null, Z.pick(`${s.duration_minutes} دقیقه`, `${s.duration_minutes} min`)));
        row.appendChild(Z.el("td", null, s.score === null ? "—" : String(Math.round(s.score))));
        row.appendChild(Z.el("td", null, Z.SESSION_FA[s.status] || s.status));
        table.appendChild(row);
      }
      const scroll = Z.el("div");
      scroll.style.overflowX = "auto";
      scroll.appendChild(table);
      box.appendChild(scroll);
    } else {
      box.appendChild(Z.el("p", "muted", Z.tr("هنوز جلسه‌ای ثبت نشده است. از تب «جلسه» شروع کن.")));
    }
  }

  // The learner sees their level before a lesson. Without one, they can take a short check or ask a parent.
  async function showLevel() {
    try {
      const student = await Z.request("GET", `/v1/students/${me.id}`);
      const notice = $("levelNotice");
      if (student.cefr_level) {
        notice.textContent = Z.pick(`سطح شما: ${student.cefr_level} (${Z.LEVEL_FA[student.cefr_level]})`, `Your level: ${student.cefr_level} (${Z.LEVEL_FA[student.cefr_level]})`);
        Z.show($("levelTestBox"), false);
      } else {
        notice.textContent = Z.tr("سطح شما هنوز تعیین نشده است. از صفحه‌ی تعیین سطح آزمون بدهید یا سطحتان را انتخاب کنید. تا آن زمان معلم از سطح مقدماتی شروع می‌کند.");
        Z.show($("levelTestBox"), true);
      }
      Z.show(notice, true);
    } catch (_) {
      Z.show($("levelNotice"), false);
    }
  }

  async function boot() {
    Z.initLang();
    Lesson.init({ onEnded: () => { showLesson(false); } });
    $("startBtn").addEventListener("click", startLesson);
    $("programShowAll").addEventListener("click", () => showFullProgram(true));
    $("programHideAll").addEventListener("click", () => showFullProgram(false));
    document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => selectTab(tab.dataset.tab)));

    try {
      me = await Z.request("GET", "/v1/web/me?role=student");
    } catch (_) {
      me = null;
    }
    if (!me || me.role !== "student") {
      // An adult who has a plan learns for themself. Anyone else goes to sign-in.
      try {
        await Z.request("POST", "/v1/web/user/self");
        me = await Z.request("GET", "/v1/web/me?role=student");
      } catch (_) {
        location.replace("/parent");
        return;
      }
    }
    await Z.initSiteHeader();
    await enterApp();
  }

  Z.pageRole.value = "student";
  document.addEventListener("DOMContentLoaded", boot);
})();
