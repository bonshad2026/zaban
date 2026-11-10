(() => {
  const $ = (id) => document.getElementById(id);
  const english = () => document.documentElement.lang === "en";
  const LEVELS = ["A1", "A2", "B1", "B2", "C1"];

  // The four levels, in the order the page shows them. Listening, reading and grammar have a test; speaking and writing are set by hand for now.
  const SKILLS = [
    { key: "listening", fa: "شنیداری", en: "Listening", test: true, column: "listening" },
    { key: "reading", fa: "خواندن", en: "Reading", test: true, column: "reading" },
    { key: "grammar", fa: "دستور و واژگان", en: "Grammar and vocabulary", test: true, column: "grammar" },
    { key: "speaking_writing", fa: "گفتار و نوشتار", en: "Speaking and writing", test: false, column: "speaking_writing" },
  ];

  let levels = {};
  let running = null; // the skill whose test is on the screen

  function label(fa, en) {
    return english() ? en : fa;
  }

  async function call(method, path, body) {
    return Z.request(method, path, body);
  }

  // The learner sign-in is needed for the level test. An adult with a plan gets it here; without one the reason is shown.
  async function ensureLearner() {
    try {
      return await call("GET", "/v1/web/placement/state");
    } catch (_) { /* not signed in as the learner yet */ }
    await call("POST", "/v1/web/user/self");
    return call("GET", "/v1/web/placement/state");
  }

  function skillRow(skill) {
    const row = Z.el("div", "skill-row");
    const head = Z.el("div", "skill-head");
    head.appendChild(Z.el("strong", "", label(skill.fa, skill.en)));
    head.appendChild(Z.el("span", "level-chip", levels[skill.key] || "A1"));
    row.appendChild(head);

    const set = Z.el("div", "skill-set");
    const select = document.createElement("select");
    select.setAttribute("aria-label", label(skill.fa, skill.en));
    LEVELS.forEach((lvl) => {
      const option = Z.el("option", "", lvl);
      option.value = lvl;
      option.selected = lvl === (levels[skill.key] || "A1");
      select.appendChild(option);
    });
    const save = Z.el("button", "ghost", label("ذخیره‌ی سطح", "Save level"));
    save.type = "button";
    save.addEventListener("click", () => saveLevel(skill.key, select.value));
    set.append(select, save);
    if (skill.test) {
      const test = Z.el("button", "", label("تعیین سطح با آزمون", "Take the level test"));
      test.type = "button";
      test.addEventListener("click", () => startTest(skill));
      set.appendChild(test);
    }
    row.appendChild(set);
    return row;
  }

  function renderRows() {
    $("skillRows").replaceChildren(...SKILLS.map(skillRow));
  }

  async function saveLevel(key, value) {
    Z.showError($("levelError"), "");
    try {
      const body = {};
      body[key] = value;
      await call("PUT", "/v1/web/student/skill-levels", body);
      levels[key] = value;
      renderRows();
      $("levelNotice").hidden = false;
      $("levelNotice").textContent = label("سطح ذخیره شد.", "Level saved.");
    } catch (err) {
      Z.showError($("levelError"), err.message);
    }
  }

  function showQuestion(view) {
    const q = view.question;
    const skill = SKILLS.find((s) => s.key === view.skill);
    $("testCard").hidden = false;
    $("testTitle").textContent = label(`آزمون ${skill.fa}`, `${skill.en} test`);
    $("testProgress").textContent = label(`سؤال ${q.number}`, `Question ${q.number}`);
    $("testText").textContent = skill.key === "listening" ? label("گوش کنید و جواب را انتخاب کنید.", "Listen and choose the answer.") : q.text;
    const listen = $("testListen");
    listen.hidden = skill.key !== "listening";
    if (skill.key === "listening") speak(q.audio);
    const options = $("testOptions");
    options.replaceChildren(...q.options.map((text, index) => {
      const button = Z.el("button", "test-option", text);
      button.type = "button";
      button.addEventListener("click", () => answer(view, q.id, index));
      return button;
    }));
    $("testSkip").onclick = () => skip(view.skill);
    listen.onclick = () => speak(q.audio);
    if (skill.key === "listening") {
      // The question of a listening item is shown under the text, after the sound has been played.
      $("testText").textContent = `${label("گوش کنید.", "Listen.")} ${q.text}`;
    }
  }

  function speak(text) {
    if (!text || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    window.speechSynthesis.speak(utterance);
  }

  function finishView(view) {
    const skill = SKILLS.find((s) => s.key === view.skill);
    $("testCard").hidden = false;
    $("testTitle").textContent = label(`آزمون ${skill.fa}`, `${skill.en} test`);
    $("testProgress").textContent = "";
    $("testText").textContent = view.status === "skipped"
      ? label("این بخش رد شد و سطح مقدماتی (A1) ثبت شد.", "This part was skipped and the beginner level (A1) was saved.")
      : label(`سطح شما در این بخش: ${view.level}`, `Your level in this part: ${view.level}`);
    $("testListen").hidden = true;
    $("testOptions").replaceChildren();
    $("testSkip").hidden = true;
  }

  function resetTestCard() {
    $("testSkip").hidden = false;
    $("testCard").hidden = true;
    $("testOptions").replaceChildren();
    running = null;
  }

  function applyView(view) {
    if (view.status === "in_progress" && view.question) {
      running = view.skill;
      $("testSkip").hidden = false;
      showQuestion(view);
      return;
    }
    if (view.status === "done" || view.status === "skipped") {
      running = null;
      finishView(view);
      refresh();
      return;
    }
    resetTestCard();
  }

  async function refresh() {
    const state = await call("GET", "/v1/web/placement/state");
    levels = state.levels;
    renderRows();
  }

  async function startTest(skill) {
    Z.showError($("levelError"), "");
    try {
      const view = await call("POST", `/v1/web/placement/${skill.key}/start`);
      $("testSkip").hidden = false;
      applyView(view);
    } catch (err) {
      Z.showError($("levelError"), err.message);
    }
  }

  async function answer(view, questionId, option) {
    try {
      const next = await call("POST", `/v1/web/placement/${view.skill}/answer`, { question_id: questionId, option });
      applyView(next);
    } catch (err) {
      Z.showError($("levelError"), err.message);
    }
  }

  async function skip(skillKey) {
    try {
      const view = await call("POST", `/v1/web/placement/${skillKey}/skip`);
      applyView(view);
    } catch (err) {
      Z.showError($("levelError"), err.message);
    }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    Z.initLang();
    try {
      const state = await ensureLearner();
      levels = state.levels;
      renderRows();
      // A test that was left half way is continued where it stopped.
      const open = state.skills.find((s) => s.status === "in_progress");
      if (open) applyView(open);
    } catch (err) {
      Z.showError($("levelError"), err.message);
      renderRows();
    }
  });
})();
