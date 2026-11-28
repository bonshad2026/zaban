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
    if (name === "test") showTestRun(false);
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

  // The path shows a window of lessons: 9 on a computer, 5 on a phone. The window is centred on `center`,
  // which starts at the current lesson. The arrows move `center` one lesson at a time.
  let center = null;
  const phoneQuery = window.matchMedia("(max-width: 560px)");

  function windowSize() {
    return phoneQuery.matches ? 5 : 9;
  }

  function windowRange() {
    const total = progress.lessons.length;
    const size = Math.min(windowSize(), total);
    const start = Math.min(Math.max(0, center - Math.floor(size / 2)), total - size);
    return [start, start + size];
  }

  function renderPath() {
    const track = $("pathTrack");
    const lessons = progress.lessons;
    const [start, end] = windowRange();
    track.replaceChildren(...lessons.slice(start, end).map((lesson, offset) => {
      const index = start + offset;
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
    $("pathPrev").disabled = center <= 0;
    $("pathNext").disabled = center >= lessons.length - 1;
  }

  // Moves the window by one lesson. Negative goes back, positive goes forward.
  function moveCenter(delta) {
    const last = progress.lessons.length - 1;
    center = Math.min(Math.max(0, center + delta), last);
    renderPath();
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
      const link = el("a", "", Z.pick("دیدن گزارش کامل در داشبورد", "See the full report on the dashboard"));
      link.href = Z.url("/student?tab=report");
      box.appendChild(el("p", "", "")).appendChild(link);
    } else if (lesson.status === "current") {
      box.appendChild(el("p", "notice", Z.tr("این جلسه‌ی فعلی توست. جلسه‌ی بعدی همین درس است.")));
    } else {
      box.appendChild(el("p", "muted", Z.tr("این جلسه هنوز نرسیده. اول جلسه‌های قبلی را طی کن. فعلاً فقط می‌توانی آن را ببینی.")));
    }
  }

  // Clicking a lesson on the path opens its details in a dialog.
  function pick(number) {
    picked = number;
    $("pathTrack").querySelectorAll(".path-node").forEach((node, index) => {
      node.setAttribute("aria-pressed", index + 1 === number ? "true" : "false");
    });
    renderDetail();
    $("lessonDialog").showModal();
  }

  // Scrolls the path by most of a screen. In a right-to-left page the later lessons are on the left.

  // The conversation partner's part of the progress tab: the five criteria (view only) and the phrases with their status.
  const PARTNER_CRITERIA = { range: "دامنه", accuracy: "دقت", fluency: "روانی", interaction: "تعامل", coherence: "انسجام" };
  const PARTNER_PHRASE_STATUS = { seen: "دیده‌شده", used: "به‌کار رفته", mastered: "متسلط" };

  const SKILL_NAMES = { listening: "شنیداری", reading: "خواندن", grammar: "دستور و واژگان", writing: "نوشتاری", speaking: "گفتاری" };

  async function loadPartnerProgress() {
    const data = await Z.request("GET", "/v1/web/student/partner");
    $("skillLevels").replaceChildren(...Object.entries(SKILL_NAMES).map(([key, label]) =>
      el("li", "", `${Z.tr(label)}: ${data.levels?.[key] || "A1"}`)));
    $("partnerCriteria").replaceChildren(...Object.entries(PARTNER_CRITERIA).map(([key, label]) =>
      el("li", "", `${Z.tr(label)}: ${data.criteria[key] || "—"}`)));
    const phrases = data.phrases.map((p) => el("li", "", `${p.text} — ${Z.tr(PARTNER_PHRASE_STATUS[p.status] || p.status)}`));
    $("partnerPhrases").replaceChildren(...(phrases.length ? phrases : [el("li", "muted", Z.tr("هنوز عبارتی ثبت نشده است."))]));
  }

  async function loadProgress() {
    loadPartnerProgress().catch(() => {});
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
      if (center === null) center = picked;
      renderSummary();
      renderPath();
      // An open lesson dialog shows the fresh data, for example after a repeat is asked for.
      if ($("lessonDialog").open) renderDetail();
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
      const src = Z.url(`/v1/web/student/help-content/${item.id}/file`);
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
      download.href = Z.url(src);
      download.setAttribute("download", item.title);
      card.appendChild(download);
    }
    if (item.url) {
      const link = el("a", "btn-link", Z.tr("باز کردن"));
      link.href = Z.url(item.url);
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
    if (!on) {
      stopTestClock();
      stopTestMic();
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    }
  }

  // Dictation for a self-test answer: the spoken words go into the answer box. Only the send button sends the answer.
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  let testRecognizer = null;
  let testTyped = "";
  const testMeter = Z.levelMeter($("testVoiceMeter"));

  // The microphone is blue while it records, the same as in the lesson.
  function setTestMicOn(on) {
    $("testMicBtn").setAttribute("aria-pressed", String(on));
    $("testMicBtn").classList.toggle("is-recording", on);
  }

  function stopTestMic() {
    if (testRecognizer) testRecognizer.stop();
  }

  // The teacher's reply is spoken aloud, in the same accent voice as the lesson.
  function speakReply(text) {
    if (!("speechSynthesis" in window) || !text) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = Accents.current;
    utterance.rate = 0.95;
    const voice = Accents.voiceFor(Accents.current);
    if (voice) utterance.voice = voice;
    window.speechSynthesis.speak(utterance);
  }

  // Speaks the newest reply of the teacher (the messages that are not the learner's).
  function speakLatestReply(test) {
    const reply = [...test.messages].reverse().find((m) => m.role !== "user");
    if (reply) speakReply(reply.content);
  }

  // The clock of a running test. When the time is up, the test is closed and its evaluation is written.
  let testClockTimer = null;
  let testEndsAt = 0;

  function stopTestClock() {
    clearInterval(testClockTimer);
    testClockTimer = null;
  }

  function startTestClock(secondsLeft) {
    stopTestClock();
    testEndsAt = Date.now() + secondsLeft * 1000;
    const tick = () => {
      const left = Math.max(0, Math.ceil((testEndsAt - Date.now()) / 1000));
      const minutes = String(Math.floor(left / 60)).padStart(2, "0");
      const seconds = String(left % 60).padStart(2, "0");
      $("testClock").textContent = Z.pick(`زمان باقی‌مانده: ${minutes}:${seconds}`, `Time left: ${minutes}:${seconds}`);
      if (left === 0) {
        stopTestClock();
        closeTestForTime();
      }
    };
    $("testClock").hidden = false;
    tick();
    if (testEndsAt > Date.now()) testClockTimer = setInterval(tick, 1000);
  }

  // The time is up: the learner sees a notice next to the answer box, the test is closed, and its evaluation is shown.
  async function closeTestForTime() {
    const id = testId;
    if (!id) return;
    stopTestMic();
    $("testClock").hidden = true;
    Z.show(document.querySelector("#testRun .composer"), false);
    $("testTimeUp").textContent = Z.pick(
      "زمان آزمون به پایان رسید و آزمون بسته شد. ارزیابی شما در حال نوشتن است.",
      "The test time is over and the test is closed. Your evaluation is being written.",
    );
    Z.show($("testTimeUp"), true);
    $("testTimeUp").scrollIntoView({ behavior: "smooth", block: "center" });
    try {
      const test = await Z.request("POST", `/v1/web/student/self-tests/${id}/finish`);
      renderTest(test);
      $("testTimeUp").textContent = Z.pick(
        "زمان آزمون به پایان رسید و آزمون بسته شد. ارزیابی شما پایین صفحه است.",
        "The test time is over and the test is closed. Your evaluation is below.",
      );
      $("testResult").scrollIntoView({ behavior: "smooth", block: "center" });
    } catch (err) {
      Z.showError($("testError"), err.message);
    }
  }

  function toggleTestMic() {
    if (testRecognizer) {
      stopTestMic();
      return;
    }
    Z.showError($("testError"), "");
    if (!SpeechRec) {
      Z.showError($("testError"), Z.tr("این مرورگر میکروفون را برای تبدیل گفتار به متن پشتیبانی نمی‌کند."));
      return;
    }
    // The teacher stops talking when the learner starts to speak.
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    const rec = new SpeechRec();
    rec.lang = "en-US";
    rec.continuous = true;
    rec.interimResults = true;
    testTyped = $("testInput").value.trimEnd();
    rec.onresult = (event) => {
      const spoken = Array.from(event.results).map((r) => r[0].transcript).join(" ").trim();
      $("testInput").value = `${testTyped ? `${testTyped} ` : ""}${spoken}`.trimStart();
    };
    rec.onerror = (event) => {
      if (event.error === "not-allowed") Z.showError($("testError"), Z.tr("مرورگر اجازه‌ی استفاده از میکروفون را نداده است."));
      else if (event.error !== "aborted" && event.error !== "no-speech") Z.showError($("testError"), Z.tr("میکروفون در دسترس نیست. می‌توانی تایپ کنی."));
    };
    rec.onend = () => {
      testRecognizer = null;
      setTestMicOn(false);
      testMeter.stop();
    };
    testRecognizer = rec;
    setTestMicOn(true);
    testMeter.start();
    try {
      rec.start();
    } catch (_) {
      testRecognizer = null;
      setTestMicOn(false);
      testMeter.stop();
    }
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
    $("testCancel").hidden = finished;
    Z.show($("testResult"), finished);
    if (finished) $("testResult").textContent = test.result || "";
    // A running test counts down from the time the server still gives it. A finished one has no clock.
    if (finished) {
      stopTestClock();
      $("testClock").hidden = true;
    } else {
      startTestClock(test.seconds_left);
    }
    $("testChat").scrollTop = $("testChat").scrollHeight;
  }


  // Opens an earlier test with its whole conversation and its evaluation. A running test can be continued.
  async function openTest(id) {
    Z.showError($("testError"), "");
    Z.show($("testTimeUp"), false);
    try {
      const test = await Z.request("GET", `/v1/web/student/self-tests/${id}`);
      renderTest(test);
    } catch (err) {
      Z.showError($("testError"), err.message);
    }
  }

  // The test reports open inside the test card, like the lesson and talk reports. "بستن" hides them again.
  // A running test resumes from its row; an unevaluated one is evaluated there, and the list reloads.
  async function showTestReports() {
    const box = $("testReports");
    box.hidden = false;
    box.replaceChildren(Z.el("p", "muted", Z.tr("در حال بارگذاری گزارش…")));
    const back = () => { box.hidden = true; box.replaceChildren(); };
    try {
      const me = await Z.request("GET", "/v1/web/me");
      const data = await Z.request("GET", `/v1/students/${me.id}/reports/items?kind=test`);
      ReportView.list(box, {
        kind: "test",
        items: data.items,
        onBack: back,
        studentId: me.id,
        onResume: (item) => openTest(item.id),
        onReload: showTestReports,
      });
      return data.items;
    } catch (err) {
      box.replaceChildren(Z.el("p", "error", err.message));
      return [];
    }
  }

  async function startTest() {
    Z.showError($("testError"), "");
    try {
      Z.show($("testTimeUp"), false);
      const test = await Z.request("POST", "/v1/web/student/self-tests", {
        kind: $("testKind").value,
        skill: $("testSkill").value,
        minutes: Number($("testMinutes").value),
      });
      renderTest({ ...test, minutes: $("testMinutes").value });
      speakLatestReply(test);
    } catch (err) {
      Z.showError($("testError"), err.message);
    }
  }

  async function sendAnswer() {
    stopTestMic();
    const text = $("testInput").value.trim();
    if (!text || !testId) return;
    $("testInput").value = "";
    try {
      const test = await Z.request("POST", `/v1/web/student/self-tests/${testId}/messages`, { content: text });
      renderTest(test);
      speakLatestReply(test);
    } catch (err) {
      Z.showError($("testError"), err.message);
    }
  }

  // Cancels the open test after a second confirmation. It is not evaluated and leaves the list and the reports.
  async function cancelTest() {
    if (!testId) return;
    const yes = await Z.confirmDialog(
      Z.pick("آیا از لغو این آزمون اطمینان دارید؟", "Are you sure you want to cancel this test?"),
      Z.pick("بله، لغو کن", "Yes, cancel"),
      Z.pick("نه، ادامه می‌دهم", "No, keep going"),
    );
    if (!yes) return;
    try {
      await Z.request("POST", `/v1/web/student/self-tests/${testId}/cancel`);
      testId = null;
      showTestRun(false);
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
    $("lessonDialogClose").addEventListener("click", () => $("lessonDialog").close());
    $("helpSearch").addEventListener("keydown", (event) => {
      if (event.key === "Enter") loadHelp();
    });
    $("pathPrev").addEventListener("click", () => moveCenter(-1));
    $("pathNext").addEventListener("click", () => moveCenter(1));
    phoneQuery.addEventListener("change", () => {
      if (progress && progress.program) renderPath();
    });
    $("testStart").addEventListener("click", startTest);
    $("testReportBtn").addEventListener("click", showTestReports);
    $("testSend").addEventListener("click", sendAnswer);
    $("testMicBtn").addEventListener("click", toggleTestMic);
    $("testFinish").addEventListener("click", finishTest);
    $("testCancel").addEventListener("click", cancelTest);
    $("testBack").addEventListener("click", () => showTestRun(false));
  });
})();
