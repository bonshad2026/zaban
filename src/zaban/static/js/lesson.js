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
    your_turn: Z.tr("Enter یعنی ارسال. برای خط جدید Shift+Enter را بزن."),
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
    if (left === 0 && S.sessionId && S.phase !== "ended") endLesson(true);
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
    rec.lang = Accents.current;
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
      if (S.phase !== "recording") return;
      setPhase("your_turn");
      if (S.pendingSend) {
        S.pendingSend = false;
        submit($("msgInput").value.trim());
      }
    };

    S.recognizer = rec;
    setPhase("recording");
    try {
      rec.start();
    } catch (_) {
      S.recognizer = null;
      setPhase("your_turn");
    }
  }

  function toggleMic() {
    if (S.phase === "recording") S.recognizer.stop();
    else if (S.phase === "your_turn") startRecording();
  }

  async function endLesson(automatic, customNote) {
    if (!S.sessionId || S.phase === "ended") return;
    if (S.recognizer) S.recognizer.abort();
    if (canSpeak) window.speechSynthesis.cancel();
    clearInterval(S.tickTimer);
    const sessionId = S.sessionId;
    S.sessionId = null;
    try {
      await Z.request("POST", `/v1/sessions/${sessionId}/end`);
    } catch (_) { /* the lesson still closes on screen */ }
    setPhase("ended");
    $("timeLeft").textContent = "";
    note(customNote || (automatic ? Z.tr("زمان جلسه تمام شد. کار خوبی بود!") : Z.tr("جلسه تمام شد. آفرین!")));
    if (S.onEnded) S.onEnded();
  }

  // Starts a fresh lesson. The server has already created the session.
  function start(session) {
    S.sessionId = session.id;
    S.lastError = "";
    $("chat").innerHTML = "";
    setTimer(session.seconds_left);
    ask(OPENING, false);
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
    setTimer(session.seconds_left);
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
    $("msgInput").addEventListener("input", render);
    $("msgInput").addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        send();
      }
    });
    render();
  }

  return { init, start, resume, isActive: () => S.sessionId !== null };
})();
