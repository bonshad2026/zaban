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
      if (view === "report") {
        // The same report view as the learner's own «گزارش‌ها» page.
        const [report, progress, partner, items] = await Promise.all([
          Z.request("GET", `/v1/web/user/students/${current.id}/report`),
          Z.request("GET", `/v1/web/user/students/${current.id}/progress`),
          Z.request("GET", `/v1/web/user/students/${current.id}/partner`),
          Z.request("GET", `/v1/web/user/students/${current.id}/items`),
        ]);
        if (!report.started) {
          body.replaceChildren(el("p", "muted", label("این دانش‌آموز هنوز یادگیری را شروع نکرده است.", "This student has not started learning yet.")));
          return;
        }
        ReportView.render(body, { progress, partner, items: items.items, onShowProgress: () => pickView("progress") });
      } else {
        const [progress, partner] = await Promise.all([
          Z.request("GET", `/v1/web/user/students/${current.id}/progress`),
          Z.request("GET", `/v1/web/user/students/${current.id}/partner`),
        ]);
        renderProgress(progress, partner);
      }
    } catch (err) {
      body.replaceChildren();
      Z.showError($("studentError"), err.message);
    }
  }

  // The learner's path, read only: a teacher can look at it and cannot change it.
  function renderProgress(progress, partner) {
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
    if (partner.started) renderPartner(body, partner);
  }

  // The conversation partner's part of the progress tab, the same as the learner sees it: skill levels, criteria and phrases.
  const SKILL_NAMES = { listening: "شنیداری", reading: "خواندن", grammar: "دستور و واژگان", writing: "نوشتاری", speaking: "گفتاری" };
  const PARTNER_CRITERIA = { range: "دامنه", accuracy: "دقت", fluency: "روانی", interaction: "تعامل", coherence: "انسجام" };
  const PARTNER_PHRASE_STATUS = { seen: "دیده‌شده", used: "به‌کار رفته", mastered: "متسلط" };

  function renderPartner(body, partner) {
    const list = (items) => {
      const ul = el("ul", "plain");
      ul.append(...items);
      return ul;
    };
    const skills = Object.entries(SKILL_NAMES).map(([key, name]) => el("li", "", `${label(name, key)}: ${partner.levels?.[key] || "A1"}`));
    const criteria = Object.entries(PARTNER_CRITERIA).map(([key, name]) => el("li", "", `${label(name, key)}: ${partner.criteria[key] || "—"}`));
    const phrases = partner.phrases.map((p) => el("li", "", `${p.text} — ${label(PARTNER_PHRASE_STATUS[p.status] || p.status, p.status)}`));
    body.append(
      el("h3", "", label("سطح مهارت‌ها", "Skill levels")),
      list(skills),
      el("h3", "", label("پنج معیار گفتاری", "Five speaking criteria")),
      el("p", "muted", label("این سطح‌ها را گفتاریار بر اساس جلسه‌ها تغییر می‌دهد.", "The partner changes these levels after the lessons.")),
      list(criteria),
      el("h3", "", label("عبارت‌های من", "Phrases")),
      list(phrases.length ? phrases : [el("li", "muted", label("هنوز عبارتی ثبت نشده است.", "No phrases yet."))]),
    );
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
