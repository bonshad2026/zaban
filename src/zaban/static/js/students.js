(() => {
  const $ = (id) => document.getElementById(id);
  const english = () => document.documentElement.lang === "en";
  const label = (fa, en) => (english() ? en : fa);
  const el = (tag, className, text) => Z.el(tag, className, text);

  let current = null; // the student whose profile is open
  let view = "report"; // "report" or "progress"

  function showGlobalError(message) {
    Z.showError($("studentsError"), message);
  }

  // One box per student: name, level, and the button that opens their profile.
  function studentCard(student) {
    const card = el("article", "student-card");
    const level = student.level
      ? `${student.level} (${Z.LEVEL_FA[student.level]})`
      : label("سطح هنوز تعیین نشده", "Level not set yet");
    const button = el("button", "", label("مشاهده‌ی پروفایل دانش‌آموز", "View student profile"));
    button.type = "button";
    button.addEventListener("click", () => openProfile(student));
    card.append(el("strong", "student-name", student.name), el("span", "level-chip", level), button);
    return card;
  }

  async function loadStudents() {
    try {
      const students = await Z.request("GET", "/v1/web/user/students");
      $("studentsGrid").replaceChildren(...students.map(studentCard));
      Z.show($("studentsEmpty"), students.length === 0);
    } catch (err) {
      showGlobalError(err.message);
    }
  }

  function highlightTab() {
    $("studentTabReport").classList.toggle("is-current", view === "report");
    $("studentTabProgress").classList.toggle("is-current", view === "progress");
    $("studentTabReport").setAttribute("aria-selected", String(view === "report"));
    $("studentTabProgress").setAttribute("aria-selected", String(view === "progress"));
  }

  function openProfile(student) {
    current = student;
    $("studentTitle").textContent = student.name;
    view = "report";
    highlightTab();
    $("studentDialog").showModal();
    loadView();
  }

  function pickView(next) {
    view = next;
    highlightTab();
    loadView();
  }

  async function loadView() {
    const body = $("studentBody");
    Z.showError($("studentError"), "");
    body.replaceChildren(el("p", "muted", label("در حال بارگذاری…", "Loading…")));
    try {
      const data = await Z.request("GET", `/v1/web/user/students/${current.id}/${view}`);
      if (view === "report") renderReport(data);
      else renderProgress(data);
    } catch (err) {
      body.replaceChildren();
      Z.showError($("studentError"), err.message);
    }
  }

  function stat(labelText, value) {
    const box = el("div", "stat");
    box.append(el("div", "label", labelText), el("div", "value", value));
    return box;
  }

  function sessionTitle(session) {
    return session.lesson_title || label("گفتگوی آزاد با معلم", "Free talk with the teacher");
  }

  function renderReport(report) {
    const body = $("studentBody");
    body.replaceChildren();
    if (!report.started) {
      body.appendChild(el("p", "muted", label("این دانش‌آموز هنوز یادگیری را شروع نکرده است.", "This student has not started learning yet.")));
      return;
    }
    const completed = report.sessions.filter((s) => s.status === "completed").length;
    const stats = el("div", "stats");
    stats.append(
      stat(label("سطح", "Level"), report.cefr_level ? `${report.cefr_level} (${Z.LEVEL_FA[report.cefr_level]})` : label("هنوز تعیین نشده", "Not set yet")),
      stat(label("وضعیت", "Status"), Z.STATUS_FA[report.status] || report.status),
      stat(label("جلسه‌های کامل", "Completed lessons"), String(completed)),
    );
    body.appendChild(stats);
    body.appendChild(el("p", "suggestion", Z.SUGGESTION_FA[report.status] || ""));
    if (report.sessions.length === 0) {
      body.appendChild(el("p", "muted", label("هنوز جلسه‌ای ثبت نشده است.", "No lessons yet.")));
      return;
    }
    const list = el("div", "student-sessions");
    report.sessions.forEach((session) => {
      const row = el("article", "attempt");
      const score = session.score === null ? label("نمره ثبت نشده", "No score") : label(`نمره: ${session.score} از ۱۰۰`, `Score: ${session.score} of 100`);
      row.append(
        el("strong", "", Z.fmtDateTime(session.started_at)),
        el("p", "", sessionTitle(session)),
        el("p", "muted", `${session.duration_minutes} ${label("دقیقه", "min")} — ${score} — ${Z.SESSION_FA[session.status] || session.status}`),
      );
      list.appendChild(row);
    });
    body.appendChild(list);
  }

  // The learner's path, read only: a teacher can look at it and cannot change it.
  function renderProgress(progress) {
    const body = $("studentBody");
    body.replaceChildren();
    if (!progress.started) {
      body.appendChild(el("p", "muted", label("این دانش‌آموز هنوز یادگیری را شروع نکرده است.", "This student has not started learning yet.")));
      return;
    }
    const summary = el("div", "progress-top");
    summary.append(
      el("strong", "progress-step", label(`مرحله‌ی ${progress.current} از ${progress.total}`, `Step ${progress.current} of ${progress.total}`)),
      el("span", "progress-percent", `${progress.percent}٪`),
    );
    const meter = el("div", "bar");
    const fill = el("span");
    fill.style.width = `${Math.min(100, Math.max(0, progress.percent))}%`;
    meter.appendChild(fill);
    summary.append(meter);
    body.appendChild(summary);

    const track = el("div", "path-track");
    let picked = progress.current;
    const detail = el("article", "lesson-detail");
    const showDetail = () => {
      const lesson = progress.lessons.find((item) => item.number === picked);
      track.querySelectorAll(".path-node").forEach((node, index) => {
        node.setAttribute("aria-pressed", String(index + 1 === picked));
      });
      detail.replaceChildren(...lessonBody(lesson, progress.total));
    };
    track.replaceChildren(...progress.lessons.map((lesson, index) => {
      const next = progress.lessons[index + 1];
      const linked = lesson.done && next && next.done ? " link-done" : "";
      const step = el("div", `path-step ${lesson.status}${linked}`);
      const node = el("button", "path-node", lesson.done ? "✓" : String(lesson.number));
      node.type = "button";
      node.setAttribute("aria-label", `${lesson.number}. ${lesson.title}`);
      node.addEventListener("click", () => {
        picked = lesson.number;
        showDetail();
      });
      step.append(node, el("span", "path-label", lesson.title));
      return step;
    }));
    body.append(track, detail);
    showDetail();
  }

  function lessonBody(lesson, total) {
    const statusText = lesson.status === "done"
      ? label("انجام شد", "Done")
      : lesson.status === "current" ? label("در این جلسه است", "On this lesson") : label("هنوز نرسیده", "Not yet");
    const head = el("div", "lesson-head");
    head.append(el("span", "lesson-no", label(`جلسه‌ی ${lesson.number} از ${total}`, `Lesson ${lesson.number} of ${total}`)), el("span", `lesson-chip ${lesson.status}`, statusText));
    const stats = el("div", "lesson-stats");
    stats.append(
      stat(label("دفعات", "Times"), String(lesson.visits)),
      stat(label("میانگین نمره", "Average score"), lesson.average === null ? "—" : String(lesson.average)),
      stat(label("میانگین مدت", "Average time"), lesson.average_minutes === null ? "—" : label(`${lesson.average_minutes} دقیقه`, `${lesson.average_minutes} min`)),
    );
    const nodes = [head, el("h3", "", lesson.title), stats];
    if (lesson.status !== "done") {
      nodes.push(el("p", "muted", label("این جلسه هنوز انجام نشده است.", "This lesson has not been done yet.")));
      return nodes;
    }
    nodes.push(el("h3", "", label("همه‌ی دفعات", "All attempts")));
    lesson.attempts.forEach((attempt) => {
      const card = el("article", "attempt");
      const minutes = attempt.minutes === null ? label("مدت ثبت نشده", "Time not recorded") : label(`${attempt.minutes} دقیقه`, `${attempt.minutes} min`);
      const score = attempt.score === null ? label("نمره ثبت نشده", "No score") : label(`نمره: ${attempt.score}`, `Score: ${attempt.score}`);
      card.append(
        el("strong", "", Z.fmtDateTime(attempt.started_at)),
        el("p", "muted", `${minutes} — ${score}`),
        el("p", "", attempt.evaluation || label("ارزیابی هنوز نوشته نشده است.", "The evaluation is not written yet.")),
      );
      nodes.push(card);
    });
    return nodes;
  }

  document.addEventListener("DOMContentLoaded", async () => {
    Z.initLang();
    $("studentTabReport").addEventListener("click", () => pickView("report"));
    $("studentTabProgress").addEventListener("click", () => pickView("progress"));
    $("studentDialog").querySelectorAll("[data-close]").forEach((button) => {
      button.addEventListener("click", () => $("studentDialog").close());
    });
    await loadStudents();
  });
})();
