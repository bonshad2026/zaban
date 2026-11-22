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

  // The plan and token warnings the learner sees at the top of every tab (no plan, plan ending, tokens running low).
  function planAlertText(alert) {
    if (alert.kind === "no_plan") return Z.pick("شما پلن فعال ندارید. برای شروع جلسه ابتدا یک پلن انتخاب و پرداخت کنید.", "You do not have an active plan. Choose and pay for a plan before you start a lesson.");
    if (alert.kind === "expired") return Z.pick("اعتبار پلن شما تمام شده است. برای ادامه‌ی جلسه‌ها پلن تازه بخرید.", "Your plan has expired. Buy a new plan to keep learning.");
    if (alert.kind === "tokens_used") return Z.pick("توکن‌های پلن شما تمام شده است. برای جلسه‌ی بعدی پلن تازه بخرید.", "Your plan tokens are used up. Buy a new plan for the next lesson.");
    if (alert.kind === "tokens") return Z.pick(`فقط ${alert.remaining_percent}٪ از توکن‌های پلن شما باقی مانده است.`, `Only ${alert.remaining_percent}% of your plan tokens are left.`);
    if (alert.kind === "expiry") {
      if (alert.days_left <= 0) return Z.pick("پلن شما امروز اعتبارش را از دست می‌دهد.", "Your plan expires today.");
      return Z.pick(`پلن شما ${alert.days_left} روز دیگر اعتبارش را از دست می‌دهد.`, `Your plan expires in ${alert.days_left} days.`);
    }
    return "";
  }

  async function loadPlanAlert() {
    const box = $("planAlert");
    try {
      const status = await Z.request("GET", "/v1/web/student/plan-status");
      box.replaceChildren();
      const texts = (status.alerts || []).map(planAlertText).filter(Boolean);
      if (!texts.length) {
        box.hidden = true;
        return;
      }
      texts.forEach((text) => box.appendChild(Z.el("p", "", text)));
      const link = Z.el("a", "pill", Z.pick("دیدن پلن و اعتبار", "View plan and tokens"));
      link.href = Z.url("/plan");
      box.appendChild(link);
      box.hidden = false;
    } catch (_) {
      box.hidden = true;
    }
  }

  async function enterApp() {
    showView();
    showLevel();
    loadAccent();
    await loadPlanAlert();
    // Lessons need the plan of the adult who owns this profile. Without it, the learner is told why and cannot start.
    if (me.has_active_plan === false) {
      $("startBtn").disabled = true;
      $("freeStartBtn").disabled = true;
      Z.showError($("startError"), Z.tr("پلن شما فعال نیست، بنابراین جلسه فعلاً شروع نمی‌شود. لطفاً پلن خود را فعال کنید."));
    }
    selectTab("lesson");
    const { session } = await Z.request("GET", `/v1/students/${me.id}/sessions/active`);
    if (session) {
      lastKind = session.session_kind === "free" ? "free" : "lesson";
      showSetup("running");
      Lesson.resume(session);
    } else if (new URLSearchParams(location.search).get("free") === "1") {
      // The free talk waits for its start button. Nothing starts by itself.
      showSetup("free");
    } else {
      showSetup("lesson");
    }
    // A header link can open a tool directly, for example ?tab=progress or ?tab=payments.
    const wanted = new URLSearchParams(location.search).get("tab");
    const tool = wanted && wanted !== "lesson" ? document.querySelector(`.tab[data-tab="${wanted}"]`) : null;
    if (tool) tool.click();
  }

  // Which card is shown: "lesson" (choose a lesson), "free" (choose a free talk) or "running" (the chat).
  let lastKind = "lesson";
  function showSetup(kind) {
    Z.show($("setupBox"), kind === "lesson");
    Z.show($("freeSetupBox"), kind === "free");
    Z.show($("lessonBox"), kind === "running");
  }

  // Free conversation (section 4.1): the same chat, without a rhythm. The length is the one chosen in the list;
  // "no time limit" (0) sends no length, so the talk ends when the learner ends it.
  // The start button stays off until both a length and a topic are chosen. A learner without an active plan never gets it on.
  function updateFreeStart() {
    const ready = $("freeMinutes").value !== "" && $("freeTopic").value.trim() !== "";
    $("freeStartBtn").disabled = !ready || me?.has_active_plan === false;
  }

  // The partner's suggested topic, filled in only when the learner presses "پیشنهاد ما". Nothing is filled in by itself.
  async function loadTopicSuggestion() {
    endTopicMic(true); // the suggestion replaces what the learner was saying
    try {
      const data = await Z.request("GET", "/v1/web/student/free-topic");
      $("freeTopic").value = data.suggestion;
    } catch (_) { /* the field stays empty; the learner can type a topic */ }
    updateFreeStart();
  }

  // The learner says the topic. The suggestion leaves the field at once, and the words spoken take its place as they are heard.
  // The microphone is blue while it listens, with the level bars beside it. A second tap stops it.
  let topicRec = null;
  let topicMeter = null;

  function setTopicMicOn(on) {
    $("freeTopicVoice").setAttribute("aria-pressed", String(on));
    $("freeTopicVoice").classList.toggle("is-recording", on);
  }

  // Ends the listening at once: the microphone turns plain and the bars hide. Abort also drops words not yet heard.
  function endTopicMic(abort) {
    const rec = topicRec;
    if (!rec) return;
    topicRec = null;
    setTopicMicOn(false);
    topicMeter.stop();
    if (abort) rec.abort();
    else rec.stop();
  }

  function speakTopic() {
    if (topicRec) {
      endTopicMic(false);
      return;
    }
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) return;
    $("freeTopic").value = "";
    updateFreeStart();
    const rec = new SpeechRec();
    rec.lang = Accents.current;
    rec.continuous = true;
    rec.interimResults = true;
    rec.onresult = (event) => {
      $("freeTopic").value = Array.from(event.results).map((r) => r[0].transcript).join(" ").trim();
      updateFreeStart();
    };
    rec.onend = () => {
      if (topicRec === rec) endTopicMic(false);
    };
    topicRec = rec;
    topicMeter = Z.levelMeter($("topicVoiceMeter"));
    setTopicMicOn(true);
    topicMeter.start();
    try {
      rec.start();
    } catch (_) {
      topicRec = null;
      setTopicMicOn(false);
      topicMeter.stop();
    }
  }

  async function startFree() {
    Z.showError($("freeStartError"), "");
    if (!$("freeMinutes").value || !$("freeTopic").value.trim()) {
      Z.showError($("freeStartError"), Z.tr("لطفاً موضوع گفتگو و مدت آن را انتخاب کنید."));
      return;
    }
    const minutes = Number($("freeMinutes").value);
    const topic = $("freeTopic").value.trim();
    const body = { topic };
    if (minutes) body.duration_minutes = minutes;
    $("freeStartBtn").disabled = true;
    try {
      const session = await Z.request("POST", `/v1/students/${me.id}/free-conversation`, body);
      lastKind = "free";
      showSetup("running");
      Lesson.start(session);
    } catch (err) {
      showStartError($("freeStartError"), err);
    } finally {
      updateFreeStart();
    }
  }

  // A start that needs the age and gender says so, and links to the personal details where they are entered.
  function showStartError(box, err) {
    if (!err.profileIncomplete) {
      Z.showError(box, err.message);
      return;
    }
    Z.showError(box, Z.pick("برای شروع، سن و جنسیت را در اطلاعات شخصی وارد کنید.", "To start, enter your age and gender in your personal details."));
    const link = Z.el("button", "ghost", Z.pick("ورود به اطلاعات شخصی", "Go to personal details"));
    link.type = "button";
    link.addEventListener("click", () => Z.openPersonalDetails());
    box.appendChild(link);
  }

  async function startLesson() {
    Z.showError($("startError"), "");
    $("startBtn").disabled = true;
    const minutes = Number($("duration").value);
    try {
      // "No time limit" starts a free talk: a lesson has a rhythm and a set length, a free talk has neither.
      const session = minutes
        ? await Z.request("POST", `/v1/students/${me.id}/sessions`, { duration_minutes: minutes })
        : await Z.request("POST", `/v1/students/${me.id}/free-conversation`);
      lastKind = minutes ? "lesson" : "free";
      showSetup("running");
      Lesson.start(session);
    } catch (err) {
      showStartError($("startError"), err);
    } finally {
      $("startBtn").disabled = false;
    }
  }

  // The reports of one kind open inside the card that starts that kind. "بستن" hides them again.
  // A running report resumes here; an unevaluated one is evaluated from its row, and the list reloads.
  async function resumeReport() {
    const data = await Z.request("GET", `/v1/students/${me.id}/sessions/active`);
    if (!data.session) return;
    lastKind = data.session.session_kind === "free" ? "free" : "lesson";
    showSetup("running");
    Lesson.resume(data.session);
  }

  async function showReportList(kind, box) {
    box.hidden = false;
    box.replaceChildren(Z.el("p", "muted", Z.tr("در حال بارگذاری گزارش…")));
    const back = () => { box.hidden = true; box.replaceChildren(); };
    try {
      const data = await Z.request("GET", `/v1/students/${me.id}/reports/items?kind=${kind}`);
      ReportView.list(box, {
        kind,
        items: data.items,
        onBack: back,
        studentId: me.id,
        onResume: resumeReport,
        onReload: () => showReportList(kind, box),
      });
      return data.items;
    } catch (err) {
      box.replaceChildren(Z.el("p", "error", err.message));
      return [];
    }
  }

  async function loadReport() {
    const box = $("reportBox");
    box.innerHTML = "";
    box.appendChild(Z.el("p", "muted", Z.tr("در حال بارگذاری گزارش…")));
    try {
      const [progress, partner, analysis] = await Promise.all([
        Z.request("GET", "/v1/web/student/progress"),
        Z.request("GET", "/v1/web/student/partner"),
        Z.request("GET", "/v1/web/student/analysis"),
      ]);
      ReportView.render($("reportBox"), {
        progress,
        partner,
        analysis,
        // The full progress view is the progress tab, which stays as it is for now.
        onShowProgress: () => document.querySelector('.tab[data-tab="progress"]').click(),
      });
    } catch (err) {
      box.innerHTML = "";
      box.appendChild(Z.el("p", "error", err.message));
    }
  }

  // The report view is in report-view.js (ReportView). This page only loads the report data.

  // The learner sees their level before a lesson. Without one, they can take a short check or choose it themselves.
  async function showLevel() {
    try {
      const student = await Z.request("GET", `/v1/students/${me.id}`);
      const notice = $("levelNotice");
      const speaking = student.levels?.speaking;
      if (speaking) {
        notice.textContent = Z.pick(`سطح گفتاری شما: ${speaking} (${Z.LEVEL_FA[speaking]})`, `Your speaking level: ${speaking} (${Z.LEVEL_FA[speaking]})`);
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
    // A free talk that ends or is cancelled returns to the free talk card, not to the lesson card.
    Lesson.init({ onEnded: (wasFree) => { showSetup(wasFree ? "free" : "lesson"); } });
    $("startBtn").addEventListener("click", startLesson);
    $("freeStartBtn").addEventListener("click", startFree);
    $("freeTopicNew").addEventListener("click", loadTopicSuggestion);
    $("lessonReportBtn").addEventListener("click", () => showReportList("lesson", $("lessonReports")));
    $("freeReportBtn").addEventListener("click", () => showReportList("talk", $("freeReports")));
    $("freeTopicVoice").addEventListener("click", speakTopic);
    $("freeTopicVoice").hidden = !(window.SpeechRecognition || window.webkitSpeechRecognition);
    $("freeTopic").placeholder = Z.pick("موضوعی که دوست داری درباره‌اش حرف بزنی", "The subject you want to talk about");
    $("freeTopic").addEventListener("input", updateFreeStart);
    $("freeMinutes").addEventListener("change", updateFreeStart);
    updateFreeStart();
    document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => selectTab(tab.dataset.tab)));

    try {
      me = await Z.request("GET", "/v1/web/me");
    } catch (_) {
      me = null;
    }
    if (!me) {
      Z.go("/login", true);
      return;
    }
    if (!me.has_own_learning) {
      // A signed-in adult without a learner profile gets one now, once a plan is active. Without a plan, the plan page opens.
      try {
        await Z.request("POST", "/v1/web/user/self");
        me = await Z.request("GET", "/v1/web/me");
      } catch (_) {
        Z.go("/plan", true);
        return;
      }
    }
    await Z.initSiteHeader();
    await enterApp();
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
