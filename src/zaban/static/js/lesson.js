// Turn-taking voice lesson. Only one side talks at a time:
// the student speaks or types, then presses Send -> معلم thinks and speaks -> the student's turn again.
const Lesson = (() => {
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  const canSpeak = "speechSynthesis" in window;
  const OPENING = "Hi, I am ready.";
  const GUARD_NOTE = Z.tr("این موضوع خارج از درس است. دوباره به انگلیسی و درباره‌ی درس حرف بزن.");

  const CHIP = {
    your_turn: [Z.tr("نوبت توست. بنویس یا میکروفون را بزن"), "turn-you"],
    recording: [Z.tr("در حال ضبط صدای تو… وقتی تمام شد «ارسال» را بزن"), "turn-recording"],
    waiting: [Z.tr("معلم در حال فکر کردن است…"), "turn-niko"],
    speaking: [Z.tr("معلم در حال صحبت است… لطفاً صبر کن"), "turn-niko"],
    ended: [Z.tr("جلسه تمام شد"), "turn-ended"],
    idle: ["", "turn-ended"],
  };
  const HINT = {
    your_turn: Z.tr("برای ارسال، روی دکمه‌ی «ارسال» بزن. Enter فقط خط جدید می‌سازد."),
    recording: Z.tr("حرف بزن. هر وقت تمام شد، روی «ارسال» بزن."),
    waiting: Z.tr("منتظر جواب معلم باش."),
    speaking: Z.tr("وقت معلم است. بعد از تمام شدن جواب، نوبت تو می‌شود."),
    ended: "",
  };

  const $ = (id) => document.getElementById(id);
  const S = {
    sessionId: null,
    phase: "idle",
    recognizer: null,
    pendingSend: false,
    base: "",
    lastError: "",
    endsAt: 0,
    tickTimer: null,
    onEnded: null,
  };

  function render() {
    const phase = S.phase;
    const writable = phase === "your_turn" || phase === "recording";
    const [chipText, chipClass] = CHIP[phase] || CHIP.ended;
    $("turnChip").textContent = chipText;
    $("turnChip").className = `chip ${chipClass}`;

    $("micBtn").disabled = !SpeechRec || !writable;
    $("micBtn").classList.toggle("is-recording", phase === "recording");
    $("micBtn").setAttribute("aria-pressed", String(phase === "recording"));

    $("msgInput").disabled = !writable;
    $("msgInput").readOnly = phase === "recording";

    const hasText = $("msgInput").value.trim().length > 0;
    $("sendBtn").disabled = !(phase === "recording" || (phase === "your_turn" && hasText));

    $("endBtn").disabled = phase === "ended" || phase === "idle";
    $("composerHint").textContent = S.lastError || HINT[phase] || "";
  }

  function setPhase(phase) {
    S.phase = phase;
    render();
  }

  function bubble(role, text) {
    const node = Z.el("div", `bubble ${role}`);
    node.appendChild(Z.el("span", "who-label", role === "user" ? Z.tr("شما") : Z.tr("معلم")));
    node.appendChild(document.createTextNode(text));
    $("chat").appendChild(node);
    $("chat").scrollTop = $("chat").scrollHeight;
    return node;
  }

  // The partner's correction and new phrase, shown under its reply. The English text is left to right, the Persian labels follow the page.
  function partnerCards(partner) {
    if (!partner || !partner.valid) return;
    if (partner.feedback) {
      const card = Z.el("div", "bubble note partner-card");
      card.dir = "ltr";
      card.append(
        Z.el("strong", "", Z.tr("جمله‌ی شما")), document.createTextNode(`: ${partner.feedback.original}`), document.createElement("br"),
        Z.el("strong", "", Z.tr("نسخه‌ی درست‌تر")), document.createTextNode(`: ${partner.feedback.better}`),
      );
      $("chat").appendChild(card);
    }
    if (partner.new_phrase) {
      const card = Z.el("div", "bubble note partner-card");
      card.dir = "ltr";
      card.append(
        Z.el("strong", "", Z.tr("عبارت تازه")), document.createTextNode(`: ${partner.new_phrase.text}`), document.createElement("br"),
        Z.el("strong", "", Z.tr("کاربرد")), document.createTextNode(`: ${partner.new_phrase.situation}`),
      );
      $("chat").appendChild(card);
    }
    $("chat").scrollTop = $("chat").scrollHeight;
  }

  // The part of the rhythm that is running (section 4.15). It is shown when the part changes, and the question about the next part is asked once when the time is up.
  const RHYTHM_LABELS = {
    conversation: "گفتگو", translation: "ترجمه‌ی ذهنی", review: "مرور عبارت‌ها", summary: "جمع‌بندی", shadowing: "شادوینگ",
    pronunciation: "تلفظ و آهنگ", task: "گفتگوی هدف‌دار", functions: "کارکردهای گفتاری", phrases: "عبارت‌ها و اصطلاحات",
    casual: "محاوره‌ای کردن", listening: "شنیدن", story: "داستان کوتاه", poetry: "شعر و ریتم", repeat: "تکرار زمان‌دار",
  };
  let shownRhythmMode = "";
  let askedAboutMode = "";
  const RHYTHM_EN = {
    conversation: "Conversation", translation: "Sentence translation", review: "Phrase review", summary: "Wrap-up",
    shadowing: "Shadowing", pronunciation: "Pronunciation and rhythm", task: "Goal task", functions: "Speech functions",
    phrases: "Phrases", casual: "Casual speech", listening: "Listening", story: "Short story", poetry: "Poem", repeat: "Timed repetition",
  };
  const rhythmLabel = (mode) => Z.pick(RHYTHM_LABELS[mode] || mode, RHYTHM_EN[mode] || mode);

  function rhythmNote(rhythm) {
    if (rhythm.mode !== shownRhythmMode) {
      shownRhythmMode = rhythm.mode;
      note(`${Z.tr("الان")}: ${rhythmLabel(rhythm.mode)}`);
    }
    if (rhythm.over && askedAboutMode !== rhythm.mode) {
      askedAboutMode = rhythm.mode;
      note(Z.tr("زمان این قسمت تمام شد. ادامه‌ی همین قسمت یا رفتن به قسمت بعد؟"));
      const row = Z.el("div", "bubble note rhythm-choice");
      const same = Z.el("button", "", Z.tr("ادامه‌ی همین قسمت"));
      same.type = "button";
      same.addEventListener("click", () => run(() => moveRhythm("current")));
      row.appendChild(same);
      if (rhythm.next_mode) {
        const next = Z.el("button", "ghost", Z.pick(`رفتن به ${rhythmLabel(rhythm.next_mode)}`, `Go to ${rhythmLabel(rhythm.next_mode)}`));
        next.type = "button";
        next.addEventListener("click", () => run(() => moveRhythm("next")));
        row.appendChild(next);
      }
      const edit = Z.el("button", "ghost", Z.tr("ویرایش ریتم"));
      edit.type = "button";
      edit.addEventListener("click", () => openRhythmEditor(rhythm.parts));
      row.appendChild(edit);
      $("chat").appendChild(row);
      $("chat").scrollTop = $("chat").scrollHeight;
    }
  }

  // Moves to another part of the rhythm, or starts the same part again. The server keeps the new state.
  async function moveRhythm(to) {
    const state = await Z.request("POST", `/v1/sessions/${S.sessionId}/rhythm/move`, { to });
    shownRhythmMode = "";
    askedAboutMode = "";
    rhythmNote(state);
  }

  // The rhythm editor: the order, the part and the minutes of each part (section 4.15). The server checks the total.
  function openRhythmEditor(parts) {
    const box = Z.el("div", "bubble note rhythm-editor");
    const rows = [];
    const addRow = (part) => {
      const line = Z.el("div", "rhythm-row");
      const mode = Z.el("select", "");
      Object.keys(RHYTHM_LABELS).forEach((key) => {
        const choice = Z.el("option", "", rhythmLabel(key));
        choice.value = key;
        mode.appendChild(choice);
      });
      mode.value = part ? part.mode : "conversation";
      const minutes = Z.el("input", "ltr-field");
      minutes.type = "number";
      minutes.min = "1";
      minutes.value = part ? String(part.minutes) : "5";
      line.append(mode, minutes);
      rows.push({ mode, minutes });
      box.insertBefore(line, box.lastChild);
    };
    (parts || []).forEach(addRow);
    const add = Z.el("button", "ghost", Z.tr("قسمت تازه"));
    add.type = "button";
    add.addEventListener("click", () => addRow(null));
    const save = Z.el("button", "", Z.tr("ذخیره‌ی ریتم"));
    save.type = "button";
    save.addEventListener("click", () => run(async () => {
      const body = { parts: rows.map((r) => ({ mode: r.mode.value, minutes: Number(r.minutes.value) })) };
      const state = await Z.request("PUT", `/v1/sessions/${S.sessionId}/rhythm`, body);
      box.remove();
      shownRhythmMode = "";
      rhythmNote(state);
    }));
    box.append(add, save);
    $("chat").appendChild(box);
    $("chat").scrollTop = $("chat").scrollHeight;
  }

  // The plan warnings the server sends with a reply (section 13.7).
  function warningText(warning) {
    if (warning.kind === "tokens") return `توکن‌های پلن شما به ${warning.percent}٪ رسیده است. بهتر است جلسه را جمع‌بندی کنید.`;
    if (warning.days_left === 0) return "امروز آخرین روز پلن شماست.";
    return `پلن شما ${warning.days_left} روز دیگر تمام می‌شود.`;
  }

  // Shadowing (section 4.3): the words the browser heard are checked against the sentence to repeat. The sample voice of the accent is played on request.
  let voiceSamples = null;
  async function sampleForAccent(accent) {
    if (voiceSamples === null) {
      try {
        voiceSamples = await Z.request("GET", "/v1/web/student/voice-samples");
      } catch (_) {
        voiceSamples = [];
      }
    }
    return voiceSamples.find((s) => s.accent === accent) || null;
  }

  async function playSample() {
    const sample = await sampleForAccent(Accents.current);
    if (!sample) {
      note(Z.tr("نمونه‌ی صوتی برای این لهجه ثبت نشده است."));
      return;
    }
    await new Audio(`/v1/web/student/voice-samples/${sample.id}/audio`).play();
  }

  function shadowingNote(shadowing) {
    if (!shadowing) return;
    if (shadowing.check) {
      const check = shadowing.check;
      const parts = [`${Z.tr("نمره‌ی کلمه‌ها")}: ${check.score}٪`];
      if (check.missing.length) parts.push(`${Z.tr("جا افتاد")}: ${check.missing.join(", ")}`);
      if (check.extra.length) parts.push(`${Z.tr("اضافه گفتی")}: ${check.extra.join(", ")}`);
      note(parts.join(" — "));
    }
    if (shadowing.target) {
      const card = Z.el("div", "bubble note shadow-target");
      card.dir = "ltr";
      const play = Z.el("button", "ghost", Z.tr("پخش نمونه"));
      play.type = "button";
      play.addEventListener("click", () => run(playSample));
      card.append(Z.el("strong", "", Z.tr("جمله‌ی تکرار")), document.createTextNode(`: ${shadowing.target}`), play);
      $("chat").appendChild(card);
      $("chat").scrollTop = $("chat").scrollHeight;
    }
  }

  // Runs an action from a button. A failure is shown in the chat instead of breaking the lesson.
  async function run(action) {
    try {
      await action();
    } catch (err) {
      note(err.message);
    }
  }

  function note(text) {
    $("chat").appendChild(Z.el("div", "bubble note", text));
    $("chat").scrollTop = $("chat").scrollHeight;
  }

  function setTimer(secondsLeft) {
    S.endsAt = Date.now() + secondsLeft * 1000;
    clearInterval(S.tickTimer);
    tick();
    S.tickTimer = setInterval(tick, 1000);
  }

  function tick() {
    const left = Math.max(0, Math.round((S.endsAt - Date.now()) / 1000));
    const minutes = String(Math.floor(left / 60)).padStart(2, "0");
    const seconds = String(left % 60).padStart(2, "0");
    $("timeLeft").textContent = Z.pick(`زمان باقی‌مانده: ${minutes}:${seconds}`, `Time left: ${minutes}:${seconds}`);
    if (left === 0 && S.sessionId && S.phase !== "ended" && !S.askedTimeUp) askTimeUp();
  }

  // When the time runs out the learner decides: go on without a time limit, or end the lesson (section 13.3).
  function askTimeUp() {
    S.askedTimeUp = true;
    clearInterval(S.tickTimer);
    note(Z.tr("زمان تمام شد، ادامه می‌دهی؟"));
    const row = Z.el("div", "bubble note time-up");
    const more = Z.el("button", "", Z.tr("ادامه بدون محدودیت"));
    more.type = "button";
    more.addEventListener("click", () => run(continueLesson));
    const finish = Z.el("button", "ghost", Z.tr("پایان جلسه"));
    finish.type = "button";
    finish.addEventListener("click", () => endLesson(false));
    row.append(more, finish);
    $("chat").appendChild(row);
    $("chat").scrollTop = $("chat").scrollHeight;
  }

  async function continueLesson() {
    await Z.request("POST", `/v1/sessions/${S.sessionId}/continue`);
    S.askedTimeUp = false;
    $("timeLeft").textContent = Z.pick("بدون محدودیت زمان", "No time limit");
    note(Z.tr("ادامه می‌دهیم. هر وقت خواستی، دکمه‌ی پایان را بزن."));
    setPhase("your_turn");
  }

  function speak(text) {
    return new Promise((resolve) => {
      if (!canSpeak || !$("autoSpeak").checked) return resolve();
      setPhase("speaking");
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = Accents.current;
      utterance.rate = 0.95;
      const voice = Accents.voiceFor(Accents.current);
      if (voice) utterance.voice = voice;
      let finished = false;
      const finish = () => {
        if (finished) return;
        finished = true;
        clearTimeout(fallback);
        resolve();
      };
      // Some browsers never fire "end". This timeout keeps the lesson from getting stuck.
      const fallback = setTimeout(finish, 3000 + text.length * 90);
      utterance.onend = finish;
      utterance.onerror = finish;
      window.speechSynthesis.speak(utterance);
    });
  }

  // Sends one message to the server and plays معلم's reply. Used for the opening line and for student turns.
  async function ask(text, showUser) {
    setPhase("waiting");
    if (showUser) bubble("user", text);
    $("msgInput").value = "";
    const thinking = bubble("assistant", "…");
    thinking.classList.add("thinking");
    try {
      const reply = await Z.request("POST", `/v1/sessions/${S.sessionId}/messages`, { content: text });
      thinking.remove();
      if (reply.guarded) note(GUARD_NOTE);
      bubble("assistant", reply.reply);
      partnerCards(reply.partner);
      shadowingNote(reply.shadowing);
      (reply.warnings || []).forEach((warning) => note(warningText(warning)));
      if (reply.rhythm) rhythmNote(reply.rhythm);
      if (reply.seconds_left !== null && reply.seconds_left !== undefined) setTimer(reply.seconds_left);
      await speak(reply.reply);
      if (reply.closed) {
        await endLesson(false, reply.notice);
        return;
      }
    } catch (err) {
      thinking.remove();
      note(err.message);
    }
    if (S.phase !== "ended") {
      setPhase("your_turn");
      if ($("autoListen").checked) startRecording();
    }
  }

  function submit(text) {
    if (!text || !S.sessionId || S.phase !== "your_turn") return;
    S.lastError = "";
    ask(text, true);
  }

  function send() {
    if (S.phase === "recording") {
      // Stop listening first. The final words arrive in onend, which then sends them.
      S.pendingSend = true;
      S.recognizer.stop();
      return;
    }
    submit($("msgInput").value.trim());
  }

  function startRecording() {
    if (!SpeechRec || S.phase !== "your_turn") return;
    S.lastError = "";
    const rec = new SpeechRec();
    const persian = $("persianMode").checked;
    rec.lang = persian ? "fa-IR" : Accents.current;
    $("msgInput").dir = persian ? "rtl" : "ltr";
    rec.continuous = true;
    rec.interimResults = true;
    const typed = $("msgInput").value.trimEnd();
    S.base = typed ? `${typed} ` : "";

    rec.onresult = (event) => {
      const spoken = Array.from(event.results).map((r) => r[0].transcript).join(" ").trim();
      $("msgInput").value = `${S.base}${spoken}`.trimStart();
      render();
    };
    rec.onerror = (event) => {
      if (event.error === "not-allowed") S.lastError = Z.tr("مرورگر اجازه‌ی استفاده از میکروفون را نداده است.");
      else if (event.error === "no-speech") S.lastError = Z.tr("صدایی شنیده نشد. دوباره میکروفون را بزن.");
      else if (event.error !== "aborted") S.lastError = Z.tr("میکروفون در دسترس نیست. می‌توانی تایپ کنی.");
    };
    rec.onend = () => {
      S.recognizer = null;
      stopMeter();
      if (S.phase !== "recording") return;
      setPhase("your_turn");
      if (S.pendingSend) {
        S.pendingSend = false;
        submit($("msgInput").value.trim());
      }
    };

    S.recognizer = rec;
    setPhase("recording");
    startMeter();
    try {
      rec.start();
    } catch (_) {
      S.recognizer = null;
      stopMeter();
      setPhase("your_turn");
    }
  }

  // Shows the sound level while the microphone is on, so the learner can see that something is being recorded.
  let meter = null;
  async function startMeter() {
    const box = $("voiceMeter");
    const bars = box.querySelectorAll("span");
    box.hidden = false;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const context = new (window.AudioContext || window.webkitAudioContext)();
      const analyser = context.createAnalyser();
      analyser.fftSize = 64;
      context.createMediaStreamSource(stream).connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);
      let frame = null;
      const draw = () => {
        analyser.getByteFrequencyData(data);
        bars.forEach((bar, i) => {
          const value = data[(i * 2) % data.length] / 255;
          bar.style.height = `${Math.max(6, Math.round(value * 34))}px`;
        });
        frame = requestAnimationFrame(draw);
      };
      draw();
      meter = { stream, context, stop: () => { cancelAnimationFrame(frame); stream.getTracks().forEach((t) => t.stop()); context.close(); } };
    } catch (_) {
      // Without the level bars the recording still works; the blue microphone shows that it is on.
    }
  }

  function stopMeter() {
    if (meter) meter.stop();
    meter = null;
    $("voiceMeter").hidden = true;
  }

  function toggleMic() {
    if (S.phase === "recording") S.recognizer.stop();
    else if (S.phase === "your_turn") startRecording();
  }

  async function endLesson(automatic, customNote) {
    if (!S.sessionId || S.phase === "ended") return;
    if (S.recognizer) S.recognizer.abort();
    stopMeter();
    if (canSpeak) window.speechSynthesis.cancel();
    clearInterval(S.tickTimer);
    const sessionId = S.sessionId;
    S.sessionId = null;
    note(Z.tr("در حال ساختن ارزیابی این جلسه… چند لحظه صبر کن."));
    let scoreText = "";
    try {
      const ended = await Z.request("POST", `/v1/sessions/${sessionId}/end`);
      if (ended.score !== null && ended.score !== undefined) {
        scoreText = Z.pick(` نمره‌ی این جلسه: ${ended.score} از ۱۰۰.`, ` Your score for this lesson: ${ended.score} of 100.`);
      }
    } catch (_) { /* the lesson still closes on screen; the score is made later */ }
    setPhase("ended");
    $("timeLeft").textContent = "";
    note((customNote || (automatic ? Z.tr("زمان جلسه تمام شد. کار خوبی بود!") : Z.tr("جلسه تمام شد. آفرین!"))) + scoreText);
    await showSummary(sessionId);
    if (S.onEnded) S.onEnded();
  }

  // The end-of-lesson page: the summary, the five criteria and the phrases of this lesson (section 15.5).
  const CRITERIA_LABELS = { range: "دامنه", accuracy: "دقت", fluency: "روانی", interaction: "تعامل", coherence: "انسجام" };
  const PHRASE_STATUS = { seen: "دیده‌شده", used: "به‌کار رفته", mastered: "متسلط" };
  async function showSummary(sessionId) {
    let data;
    try {
      data = await Z.request("GET", `/v1/sessions/${sessionId}/summary`);
    } catch (_) {
      return;
    }
    if (data.end_status !== "evaluated") return;
    const card = Z.el("div", "bubble note lesson-summary");
    card.dir = "auto";
    card.append(Z.el("strong", "", Z.tr("جمع‌بندی جلسه")), document.createElement("br"), document.createTextNode(data.summary));
    const list = Z.el("ul", "plain");
    Object.entries(CRITERIA_LABELS).forEach(([key, label]) => {
      list.appendChild(Z.el("li", "", `${Z.tr(label)}: ${data.criteria[key] || "—"}`));
    });
    card.append(list);
    if (data.phrases.length) {
      const phrases = Z.el("ul", "plain");
      data.phrases.forEach((p) => phrases.appendChild(Z.el("li", "", `${p.text} — ${Z.tr(PHRASE_STATUS[p.status] || p.status)}`)));
      card.append(Z.el("strong", "", Z.tr("عبارت‌های این جلسه")), phrases);
    }
    $("chat").appendChild(card);
    $("chat").scrollTop = $("chat").scrollHeight;
  }

  // Starts a fresh lesson. The server has already created the session.
  function start(session) {
    S.sessionId = session.id;
    S.askedTimeUp = false;
    S.lastError = "";
    $("chat").innerHTML = "";
    showClock(session);
    ask(OPENING, false);
  }

  // A lesson and a free talk with a length show the clock. A free talk with no time limit shows no clock; it ends when the learner ends it.
  function showClock(session) {
    S.free = Boolean(session.free);
    if (S.free && !session.duration_minutes) {
      clearInterval(S.tickTimer);
      $("timeLeft").textContent = Z.pick("بدون محدودیت زمان", "No time limit");
      return;
    }
    setTimer(session.seconds_left);
  }

  // Resumes a lesson that is still running, for example after a page reload.
  function resume(session) {
    S.sessionId = session.id;
    S.lastError = "";
    $("chat").innerHTML = "";
    for (const message of session.messages) {
      if (message.role === "user" && message.content === OPENING) continue;
      bubble(message.role === "user" ? "user" : "assistant", message.content);
    }
    showClock(session);
    setPhase("your_turn");
  }

  function init({ onEnded }) {
    S.onEnded = onEnded;
    if (!SpeechRec) {
      $("voiceNotice").textContent = Z.tr("این مرورگر میکروفون ندارد. از Chrome یا Edge استفاده کنید. تایپ همچنان کار می‌کند.");
      Z.show($("voiceNotice"), true);
    }
    $("micBtn").addEventListener("click", toggleMic);
    $("sendBtn").addEventListener("click", send);
    $("endBtn").addEventListener("click", () => endLesson(false));
    $("helpUnderstood").addEventListener("click", () => {
      if (S.phase === "your_turn") ask("I did not understand. Please explain it again, more simply.", true);
    });
    $("msgInput").addEventListener("input", render);
    // Enter only makes a new line. A message is sent only by the send button.
    render();
  }

  return { init, start, resume, isActive: () => S.sessionId !== null };
})();
