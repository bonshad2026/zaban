(() => {
  const $ = (id) => document.getElementById(id);

  // The learner's own tools: profile, progress, help content, self-test and payments.
  // Each tool has its own section. Any other tab hides them, so the lesson tabs work as before.
  const SECTIONS = {
    progress: "tab-progress",
    help: "tab-help",
    test: "tab-test",
    payments: "tab-payments",
  };

  const CATEGORY_LABELS = {
    podcast: Z.tr("پادکست"),
    story: Z.tr("داستان"),
    animation: Z.tr("انیمیشن"),
    video: Z.tr("ویدئو"),
    sample: Z.tr("نمونه"),
    other: Z.tr("دیگر"),
  };

  const STATUS_LABELS = { paid: Z.tr("منتظر تأیید"), confirmed: Z.tr("تأیید شده"), pending: Z.tr("در انتظار پرداخت"), failed: Z.tr("ناموفق") };

  function toolTab(name) {
    Object.entries(SECTIONS).forEach(([key, id]) => Z.show($(id), key === name));
    if (name === "progress") loadProgress();
    if (name === "help") {
      renderHelpTabs();
      loadHelp();
    }
    if (name === "payments") loadPayments();
    if (name === "test") {
      showTestRun(false);
      loadTests();
    }
  }

  function nullIfEmpty(value) {
    const trimmed = (value || "").trim();
    return trimmed === "" ? null : trimmed;
  }

  // ----- Profile and level -----

  // ----- Progress: one step per lesson, a path to scroll through, and the details of the lesson picked on it -----

  let progress = null;
  let picked = null; // the lesson number whose details are shown

  function el(tag, className, text) {
    return Z.el(tag, className, text);
  }

  function isRtl() {
    return document.documentElement.dir === "rtl";
  }

  function statusText(status) {
    if (status === "done") return Z.pick("انجام شد", "Done");
    if (status === "current") return Z.pick("در این جلسه هستی", "You are here");
    return Z.pick("هنوز نرسیده", "Not yet");
  }

  // Asks for a finished lesson to be played again in the next session. The place in the program stays the same.
  async function requestRepeat(itemId) {
    try {
      await Z.request("POST", "/v1/web/student/progress/repeat", { item_id: itemId });
      await loadProgress();
    } catch (err) {
      Z.showError($("progressNotice"), err.message);
    }
  }

  function renderSummary() {
    const data = progress;
    $("progressSummary").textContent = data.program ? data.program.name : "";
    $("progressStep").textContent = Z.pick(`مرحله‌ی ${data.current} از ${data.total}`, `Step ${data.current} of ${data.total}`);
    $("progressPercent").textContent = `${data.percent}٪`;
    $("progressBar").style.width = `${Math.min(100, Math.max(0, data.percent))}%`;
    $("progressAverage").textContent = data.average_score === null || data.average_score === undefined
      ? Z.tr("هنوز نمره‌ای ثبت نشده است.")
      : Z.pick(`میانگین نمره‌ی همه‌ی جلسه‌ها: ${data.average_score} از ۱۰۰`, `Average score of all lessons: ${data.average_score} of 100`);
    $("progressHowto").textContent = Z.pick(
      "درصد پیشرفت یعنی میانگین نمره‌ی جلسه‌های انجام‌شده تقسیم بر تعداد کل جلسه‌ها. تکرار یک جلسه، میانگین آن را تغییر می‌دهد و جای شما در مسیر را عوض نمی‌کند.",
      "Progress is the average score of the finished lessons divided by the number of lessons. Repeating a lesson changes its average, not your place on the path.",
    );
    $("pathBefore").textContent = Z.pick(`${data.current - 1} جلسه‌ی قبلی  ·  `, `${data.current - 1} earlier  ·  `);
    $("pathAfter").textContent = Z.pick(`${data.total - data.current} جلسه‌ی بعدی`, `${data.total - data.current} later`);
    $("pathPrev").setAttribute("aria-label", Z.pick("جلسه‌های قبلی", "Earlier lessons"));
    $("pathNext").setAttribute("aria-label", Z.pick("جلسه‌های بعدی", "Later lessons"));
  }

  function renderPath() {
    const track = $("pathTrack");
    const lessons = progress.lessons;
    track.replaceChildren(...lessons.map((lesson, index) => {
      const next = lessons[index + 1];
      const linked = lesson.done && next && next.done ? " link-done" : "";
      const step = el("div", `path-step ${lesson.status}${linked}`);
      const node = el("button", "path-node", lesson.done ? "✓" : String(lesson.number));
      node.type = "button";
      node.setAttribute("aria-label", `${lesson.number}. ${lesson.title} — ${statusText(lesson.status)}`);
      node.setAttribute("aria-pressed", lesson.number === picked ? "true" : "false");
      node.addEventListener("click", () => pick(lesson.number));
      step.append(node, el("span", "path-label", lesson.title));
      return step;
    }));
  }

  function scrollPathTo(number) {
    const node = $("pathTrack").querySelectorAll(".path-node")[number - 1];
    if (node) node.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
  }

  function miniStat(label, value) {
    const box = el("div", "stat");
    box.append(el("div", "label", label), el("div", "value", value));
    return box;
  }

  function attemptCard(attempt) {
    const card = el("article", "attempt");
    const meta = [
      attempt.minutes === null ? Z.pick("مدت ثبت نشده", "Time not recorded") : Z.pick(`${attempt.minutes} دقیقه`, `${attempt.minutes} min`),
      attempt.score === null ? Z.pick("نمره ثبت نشده", "No score") : Z.pick(`نمره: ${attempt.score}`, `Score: ${attempt.score}`),
    ];
    card.append(
      el("strong", "", Z.fmtDateTime(attempt.started_at)),
      el("p", "muted", meta.join(" — ")),
      el("p", "", attempt.evaluation || Z.tr("ارزیابی هنوز نوشته نشده است.")),
    );
    return card;
  }

  function renderDetail() {
    const box = $("lessonDetail");
    const lesson = progress.lessons.find((item) => item.number === picked);
    if (!lesson) {
      box.replaceChildren(el("p", "muted", Z.tr("هنوز برنامه‌ای برای شما تعیین نشده است.")));
      return;
    }
    const head = el("div", "lesson-head");
    head.append(
      el("span", "lesson-no", Z.pick(`جلسه‌ی ${lesson.number} از ${progress.total}`, `Lesson ${lesson.number} of ${progress.total}`)),
      el("span", `lesson-chip ${lesson.status}`, statusText(lesson.status)),
    );
    const stats = el("div", "lesson-stats");
    stats.append(
      miniStat(Z.pick("دفعات", "Times"), String(lesson.visits)),
      miniStat(Z.pick("میانگین نمره", "Average score"), lesson.average === null ? "—" : String(lesson.average)),
      miniStat(Z.pick("میانگین مدت", "Average time"), lesson.average_minutes === null ? "—" : Z.pick(`${lesson.average_minutes} دقیقه`, `${lesson.average_minutes} min`)),
    );
    box.replaceChildren(head, el("h3", "", lesson.title));
    if (lesson.goal) box.appendChild(el("p", "muted", lesson.goal));
    box.appendChild(stats);

    if (lesson.status === "done") {
      const action = el("div", "lesson-action");
      const button = el("button", "ghost", lesson.repeat ? Z.tr("لغو تکرار") : Z.tr("تکرار این جلسه در جلسه‌ی بعد"));
      button.type = "button";
      button.addEventListener("click", () => requestRepeat(lesson.repeat ? null : lesson.item_id));
      action.appendChild(button);
      if (lesson.repeat) action.appendChild(el("p", "notice", Z.tr("در جلسه‌ی بعد این درس دوباره گرفته می‌شود.")));
      box.appendChild(action);
      box.appendChild(el("h3", "", Z.pick("همه‌ی دفعات", "All attempts")));
      lesson.attempts.forEach((attempt) => box.appendChild(attemptCard(attempt)));
      const link = el("a", "", Z.pick("دیدن گزارش کامل در صفحه‌ی گزارش من", "See the full report on My report"));
      link.href = "/student?tab=report";
      box.appendChild(el("p", "", "")).appendChild(link);
    } else if (lesson.status === "current") {
      box.appendChild(el("p", "notice", Z.tr("این جلسه‌ی فعلی توست. جلسه‌ی بعدی همین درس است.")));
    } else {
      box.appendChild(el("p", "muted", Z.tr("این جلسه هنوز نرسیده. اول جلسه‌های قبلی را طی کن. فعلاً فقط می‌توانی آن را ببینی.")));
    }
  }

  function pick(number) {
    picked = number;
    $("pathTrack").querySelectorAll(".path-node").forEach((node, index) => {
      node.setAttribute("aria-pressed", index + 1 === number ? "true" : "false");
    });
    renderDetail();
  }

  // Scrolls the path by most of a screen. In a right-to-left page the later lessons are on the left.
  function scrollPath(forward) {
    const track = $("pathTrack");
    const direction = forward ? 1 : -1;
    track.scrollBy({ left: direction * (isRtl() ? -1 : 1) * track.clientWidth * 0.8, behavior: "smooth" });
  }

  async function loadProgress() {
    try {
      progress = await Z.request("GET", "/v1/web/student/progress");
      Z.showError($("progressNotice"), "");
      if (!progress.program) {
        $("progressStep").textContent = "";
        $("progressPercent").textContent = "";
        $("progressSummary").textContent = Z.tr("هنوز برنامه‌ای برای شما تعیین نشده است.");
        $("progressBar").style.width = "0%";
        $("pathTrack").replaceChildren();
        $("lessonDetail").replaceChildren();
        return;
      }
      if (picked === null) picked = progress.current;
      renderSummary();
      renderPath();
      renderDetail();
      scrollPathTo(picked);
    } catch (err) {
      Z.showError($("progressNotice"), err.message);
    }
  }

  // ----- Help content -----

  function helpItem(item) {
    const card = el("article", "help-item");
    card.append(el("h3", "", item.title), el("p", "muted", Z.pick(`${CATEGORY_LABELS[item.category] || item.category} — سطح ${item.level}`, `${CATEGORY_LABELS[item.category] || item.category} — level ${item.level}`)));
    if (item.tags && item.tags.length) card.append(el("p", "muted", Z.pick(`برچسب‌ها: ${item.tags.join("، ")}`, `Tags: ${item.tags.join(", ")}`)));
    if (item.has_file) {
      const src = `/v1/web/student/help-content/${item.id}/file`;
      if (item.mime && item.mime.startsWith("audio/")) {
        const audio = el("audio");
        audio.controls = true;
        audio.src = src;
        card.appendChild(audio);
      } else if (item.mime && item.mime.startsWith("image/")) {
        const img = el("img", "help-image");
        img.src = src;
        img.alt = item.title;
        card.appendChild(img);
      } else if (item.mime && item.mime.startsWith("video/")) {
        const video = el("video");
        video.controls = true;
        video.src = src;
        video.className = "help-video";
        card.appendChild(video);
      }
      const download = el("a", "btn-link", Z.tr("دانلود"));
      download.href = src;
      download.setAttribute("download", item.title);
      card.appendChild(download);
    }
    if (item.url) {
      const link = el("a", "btn-link", Z.tr("باز کردن"));
      link.href = item.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      card.appendChild(link);
    }
    return card;
  }

  // The category tabs. "" means every category. The tabs use their own class, so the main tab handlers do not catch them.
  const HELP_TABS = [["", Z.tr("همه")], ...Object.entries(CATEGORY_LABELS)];
  let helpCategory = "";

  function renderHelpTabs() {
    const box = $("helpTabs");
    box.replaceChildren(
      ...HELP_TABS.map(([value, label]) => {
        const tab = el("button", "filter-tab" + (value === helpCategory ? " is-active" : ""), label);
        tab.type = "button";
        tab.setAttribute("role", "tab");
        tab.setAttribute("aria-selected", String(value === helpCategory));
        tab.addEventListener("click", () => {
          helpCategory = value;
          renderHelpTabs();
          loadHelp();
        });
        return tab;
      }),
    );
  }

  // The filter dialog. The category tabs stay on the page; the other filters are chosen here, one value each.
  // The dialog works on a copy, so nothing changes until «اعمال».
  const NO_FILTERS = { level: "", gender: "", tags: {} };
  let helpFilters = { level: "", gender: "", tags: {} };
  let helpDraft = null;

  function activeHelpFilterCount() {
    return [helpFilters.level, helpFilters.gender, ...Object.values(helpFilters.tags)].filter(Boolean).length;
  }

  function helpFilterOption(value, text) {
    const o = el("option", "", text);
    o.value = value;
    return o;
  }

  // One select for one filter: «همه» first, then each value with how many items have it.
  function helpFilterField(label, options, value, onChange) {
    const wrap = el("div", "help-filter-field");
    const select = el("select", "");
    select.setAttribute("aria-label", label);
    select.appendChild(helpFilterOption("", Z.tr("همه")));
    options.forEach((o) => select.appendChild(helpFilterOption(o.value, `${o.label} (${o.count})`)));
    select.value = value;
    select.addEventListener("change", () => onChange(select.value));
    wrap.append(el("label", "", label), select);
    return wrap;
  }

  function renderHelpFilterFields(data) {
    const fields = [];
    if (data.level.options.length > 1) {
      fields.push(helpFilterField(Z.tr("سطح"), data.level.options, helpDraft.level, (v) => { helpDraft.level = v; }));
    }
    if (data.gender.options.length > 1) {
      fields.push(helpFilterField(Z.tr("جنسیت"), data.gender.options, helpDraft.gender, (v) => { helpDraft.gender = v; }));
    }
    data.facets.forEach((facet) => {
      fields.push(helpFilterField(facet.label, facet.options, helpDraft.tags[facet.key] || "", (v) => { helpDraft.tags[facet.key] = v; }));
    });
    const box = $("helpFilterFields");
    box.replaceChildren(...fields);
    Z.show($("helpFilterEmpty"), fields.length === 0);
  }

  async function openHelpFilters() {
    const params = new URLSearchParams();
    if (helpCategory) params.set("category", helpCategory);
    try {
      const data = await Z.request("GET", `/v1/web/student/help-content/filters?${params.toString()}`);
      helpDraft = JSON.parse(JSON.stringify(helpFilters));
      renderHelpFilterFields(data);
      Z.showError($("helpFilterError"), "");
      $("helpFilterDialog").showModal();
    } catch (err) {
      Z.showError($("helpNotice"), err.message);
    }
  }

  function applyHelpFilters() {
    helpFilters = helpDraft;
    $("helpFilterDialog").close();
    loadHelp();
  }

  function clearHelpFilters() {
    helpDraft = JSON.parse(JSON.stringify(NO_FILTERS));
    helpFilters = helpDraft;
    $("helpFilterDialog").close();
    loadHelp();
  }

  async function loadHelp() {
    const params = new URLSearchParams();
    if (helpCategory) params.set("category", helpCategory);
    if ($("helpSearch").value.trim()) params.set("q", $("helpSearch").value.trim());
    if (helpFilters.level) params.set("level", helpFilters.level);
    if (helpFilters.gender) params.set("gender", helpFilters.gender);
    Object.values(helpFilters.tags).filter(Boolean).forEach((id) => params.append("tag", id));
    $("helpFilterOpen").textContent = activeHelpFilterCount() ? Z.tr(`فیلترها (${activeHelpFilterCount()})`) : Z.tr("فیلترها");
    try {
      const rows = await Z.request("GET", `/v1/web/student/help-content?${params.toString()}`);
      const list = $("helpList");
      list.replaceChildren();
      Z.show($("helpNotice"), rows.length === 0);
      $("helpNotice").textContent = rows.length === 0 ? Z.tr("برای این سطح و جست‌وجو محتوایی پیدا نشد.") : "";
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

  // The score Niko gives at the end of a test, out of 100. Older tests have none.
  function scoreText(score) {
    return score === null || score === undefined ? Z.tr("نمره ندارد") : Z.pick(`نمره ${Math.round(score).toLocaleString(Z.locale())} از ۱۰۰`, `Score ${Math.round(score)} of 100`);
  }

  // The test run card shows one test at a time: a running test, or a finished one read back from the list.
  function showTestRun(on) {
    Z.show($("testSetup"), !on);
    Z.show($("testRun"), on);
  }

  function renderTest(test) {
    testId = test.id;
    showTestRun(true);
    $("testStatus").textContent = test.status === "finished"
      ? Z.pick(`آزمون تمام شد — ${scoreText(test.score)}`, `Test finished — ${scoreText(test.score)}`)
      : Z.pick(`سطح ${test.level || "؟"} — ${test.minutes} دقیقه`, `Level ${test.level || "?"} — ${test.minutes} min`);
    $("testChat").replaceChildren(...test.messages.map(bubble));
    const finished = test.status === "finished";
    Z.show(document.querySelector("#testRun .composer"), !finished);
    $("testFinish").hidden = finished;
    Z.show($("testResult"), finished);
    if (finished) $("testResult").textContent = test.result || "";
    $("testChat").scrollTop = $("testChat").scrollHeight;
  }

  const KIND_LABELS = { qa: Z.tr("سؤال و جواب"), conversation: Z.tr("مکالمه"), mixed: Z.tr("ترکیبی"), suggested: Z.tr("پیشنهاد سیستم") };
  const SKILL_LABELS = { writing: Z.tr("نوشتن"), listening: Z.tr("شنیداری"), speaking: Z.tr("گفتاری"), mixed: Z.tr("چند مهارت") };

  async function loadTests() {
    try {
      const rows = await Z.request("GET", "/v1/web/student/self-tests");
      const list = $("testList");
      list.replaceChildren();
      Z.show($("testListNotice"), rows.length === 0);
      $("testListNotice").textContent = rows.length === 0 ? Z.tr("هنوز آزمونی نداده‌اید. از پایین شروع کنید.") : "";
      rows.forEach((t) => {
        const card = el("article", "help-item");
        const status = t.status === "finished" ? Z.tr("تمام شده") : Z.tr("در حال انجام");
        const view = el("button", "ghost", t.status === "finished" ? Z.tr("مشاهده‌ی آزمون") : Z.tr("ادامه‌ی آزمون"));
        view.type = "button";
        view.addEventListener("click", () => openTest(t.id));
        card.append(
          el("h3", "", `${KIND_LABELS[t.kind] || t.kind} — ${SKILL_LABELS[t.skill] || t.skill}`),
          el("p", "muted", Z.pick(`${Z.fmtDateTime(t.created_at)} — ${t.minutes} دقیقه — سطح ${t.level || "؟"} — ${status}`, `${Z.fmtDateTime(t.created_at)} — ${t.minutes} min — level ${t.level || "?"} — ${status}`)),
          el("p", "muted", t.status === "finished" ? scoreText(t.score) : ""),
          el("p", "", t.result || Z.tr("ارزیابی هنوز نوشته نشده است.")),
          view,
        );
        list.appendChild(card);
      });
    } catch (err) {
      Z.showError($("testListNotice"), err.message);
    }
  }

  // Opens an earlier test with its whole conversation and its evaluation. A running test can be continued.
  async function openTest(id) {
    Z.showError($("testError"), "");
    try {
      const test = await Z.request("GET", `/v1/web/student/self-tests/${id}`);
      renderTest(test);
    } catch (err) {
      Z.showError($("testListNotice"), err.message);
    }
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
      loadTests();
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
      [Z.tr("تاریخ"), Z.tr("پلن"), Z.tr("مبلغ (تومان)"), Z.tr("وضعیت")].forEach((h) => head.appendChild(el("th", "", h)));
      table.appendChild(head);
      rows.forEach((p) => {
        const tr = el("tr");
        [
          Z.fmtDate(p.created_at),
          p.plan_name ? Z.pick(p.plan_name, p.plan_name_en || p.plan_name) : "—",
          p.amount_toman.toLocaleString(Z.locale()),
          STATUS_LABELS[p.status] || p.status,
        ].forEach((v) => tr.appendChild(el("td", "", v)));
        table.appendChild(tr);
      });
    } catch (err) {
      Z.showError($("progressNotice"), err.message);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => toolTab(tab.dataset.tab)));
    $("helpGo").addEventListener("click", loadHelp);
    $("helpFilterOpen").addEventListener("click", openHelpFilters);
    $("helpFilterApply").addEventListener("click", applyHelpFilters);
    $("helpFilterClear").addEventListener("click", clearHelpFilters);
    $("helpFilterClose").addEventListener("click", () => $("helpFilterDialog").close());
    $("helpSearch").addEventListener("keydown", (event) => {
      if (event.key === "Enter") loadHelp();
    });
    $("pathPrev").addEventListener("click", () => scrollPath(false));
    $("pathNext").addEventListener("click", () => scrollPath(true));
    $("testStart").addEventListener("click", startTest);
    $("testSend").addEventListener("click", sendAnswer);
    $("testFinish").addEventListener("click", finishTest);
    $("testBack").addEventListener("click", () => {
      showTestRun(false);
      loadTests();
    });
  });
})();
