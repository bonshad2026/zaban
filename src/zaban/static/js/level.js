(() => {
  const $ = (id) => document.getElementById(id);
  const english = () => document.documentElement.lang === "en";
  const LEVELS = ["A1", "A2", "B1", "B2", "C1"];

  // The four skills, in the order the page shows them. Speaking and writing have no test yet; its level is chosen by hand.
  const SKILLS = [
    { key: "listening", fa: "شنیداری", en: "Listening", test: true },
    { key: "reading", fa: "خواندن", en: "Reading", test: true },
    { key: "grammar", fa: "دستور و واژگان", en: "Grammar and vocabulary", test: true },
    { key: "speaking_writing", fa: "گفتار و نوشتار", en: "Speaking and writing", test: false },
  ];

  // Plain line icons, one per skill. They take the text colour, so they follow the theme.
  const SKILL_ICONS = {
    listening: '<svg viewBox="0 0 24 24"><path d="M4 9v6h4l5 4V5L8 9H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/></svg>',
    reading: '<svg viewBox="0 0 24 24"><path d="M2 5h7a3 3 0 0 1 3 3v12a2 2 0 0 0-2-2H2z"/><path d="M22 5h-7a3 3 0 0 0-3 3v12a2 2 0 0 1 2-2h8z"/></svg>',
    grammar: '<svg viewBox="0 0 24 24"><path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16z"/><path d="M14 6l4 4"/></svg>',
    speaking_writing: '<svg viewBox="0 0 24 24"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/></svg>',
  };

  let levels = {};
  let statuses = {}; // the latest attempt status of each skill: new, in_progress, done or skipped
  let totals = {}; // how many questions each skill has in the bank

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

  function applyState(state) {
    levels = state.levels;
    statuses = {};
    state.skills.forEach((view) => {
      statuses[view.skill] = view.status;
      totals[view.skill] = view.total;
    });
  }

  function testButtonLabel(skill) {
    const tested = statuses[skill.key] === "done" || statuses[skill.key] === "skipped";
    if (tested) return label("تعیین مجدد سطح", "Set level again");
    return label("تعیین سطح", "Set level");
  }

  // One box per skill: its icon and current level, the level chooser with its save button, then the test button.
  function skillCard(skill) {
    const card = Z.el("article", "skill-card");

    const head = Z.el("div", "skill-head");
    const icon = Z.el("span", "skill-icon");
    icon.setAttribute("aria-hidden", "true");
    icon.innerHTML = SKILL_ICONS[skill.key];
    head.append(icon, Z.el("strong", "skill-name", label(skill.fa, skill.en)), Z.el("span", "level-chip", levels[skill.key] || "A1"));
    card.appendChild(head);

    const set = Z.el("div", "skill-set");
    const select = document.createElement("select");
    select.setAttribute("aria-label", label(skill.fa, skill.en));
    LEVELS.forEach((lvl) => {
      const option = Z.el("option", "", lvl);
      option.value = lvl;
      option.selected = lvl === (levels[skill.key] || "A1");
      select.appendChild(option);
    });
    const save = Z.el("button", "ghost skill-btn", label("ذخیره‌ی سطح", "Save level"));
    save.type = "button";
    save.addEventListener("click", () => saveLevel(skill.key, select.value));
    set.append(select, save);
    card.appendChild(set);

    if (skill.test) {
      const test = Z.el("button", "skill-btn skill-test", testButtonLabel(skill));
      test.type = "button";
      test.addEventListener("click", () => openTest(skill));
      card.appendChild(test);
    } else {
      card.appendChild(Z.el("p", "skill-note muted", label("این مهارت آزمون ندارد. سطح آن را خودتان انتخاب کنید.", "This skill has no test. Choose its level yourself.")));
    }
    return card;
  }

  function renderRows() {
    $("skillRows").replaceChildren(...SKILLS.map(skillCard));
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

  // ---- The test dialog: intro, questions one by one, then the result. The page stays under it. ----

  function showOnly(section) {
    ["testIntro", "testCard", "testResult"].forEach((id) => {
      $(id).hidden = id !== section;
    });
  }

  function openDialog() {
    const dialog = $("testDialog");
    if (!dialog.open) dialog.showModal();
  }

  function showIntro(skill) {
    const total = totals[skill.key] || 0;
    const minutes = Math.max(1, Math.ceil(total / 2));
    const listening = skill.key === "listening"
      ? label(" در بخش شنیداری می‌توانید صدا را دوباره پخش کنید.", " In the listening part you can play the sound again.")
      : "";
    $("testIntroText").textContent = label(
      `این آزمون ${total} سؤال دارد و حدود ${minutes} دقیقه طول می‌کشد. سؤال‌ها از سطح A1 شروع می‌شوند. اگر به اندازه‌ی کافی درست جواب دهید، به سطح بعد می‌روید. آزمون در اولین سطحی که به اندازه‌ی کافی درست جواب ندهید متوقف می‌شود.${listening} اگر بخشی را رد کنید، سطح A1 ثبت می‌شود.`,
      `This test has ${total} questions and takes about ${minutes} minutes. The questions start at level A1. If you answer enough correctly, you move to the next level. The test stops at the first level you do not pass.${listening} If you skip this part, level A1 is saved.`,
    );
    showOnly("testIntro");
  }

  function openTest(skill) {
    Z.showError($("testError"), "");
    $("testTitle").textContent = label(`آزمون ${skill.fa}`, `${skill.en} test`);
    $("testDialog").dataset.skill = skill.key;
    openDialog();
    if (statuses[skill.key] === "in_progress") {
      // A test that was left half way is continued where it stopped.
      startTest(skill);
      return;
    }
    showIntro(skill);
  }

  function showQuestion(view) {
    const q = view.question;
    const skill = SKILLS.find((s) => s.key === view.skill);
    showOnly("testCard");
    $("testProgress").textContent = label(`سؤال ${q.number} از ${totals[view.skill] || "؟"}`, `Question ${q.number} of ${totals[view.skill] || "?"}`);
    $("testText").textContent = q.text;
    const listen = $("testListen");
    listen.hidden = skill.key !== "listening";
    if (skill.key === "listening") {
      $("testText").textContent = `${label("گوش کنید.", "Listen.")} ${q.text}`;
      speak(q.audio);
    }
    listen.onclick = () => speak(q.audio);
    const options = $("testOptions");
    options.replaceChildren(...q.options.map((text, index) => {
      const button = Z.el("button", "test-option", text);
      button.type = "button";
      button.addEventListener("click", () => answer(view, q.id, index));
      return button;
    }));
    $("testSkip").onclick = () => skip(view.skill);
  }

  function speak(text) {
    if (!text || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    window.speechSynthesis.speak(utterance);
  }

  function showResult(view) {
    $("testResultText").textContent = view.status === "skipped"
      ? label("این بخش رد شد و سطح مقدماتی (A1) ثبت شد.", "This part was skipped and the beginner level (A1) was saved.")
      : label(`سطح شما در این بخش: ${view.level}`, `Your level in this part: ${view.level}`);
    showOnly("testResult");
  }

  function applyView(view) {
    if (view.status === "in_progress" && view.question) {
      showQuestion(view);
      return;
    }
    if (view.status === "done" || view.status === "skipped") {
      showResult(view);
      refresh();
      return;
    }
    const skill = SKILLS.find((s) => s.key === view.skill);
    showIntro(skill);
  }

  async function refresh() {
    applyState(await call("GET", "/v1/web/placement/state"));
    renderRows();
  }

  async function startTest(skill) {
    Z.showError($("testError"), "");
    try {
      const view = await call("POST", `/v1/web/placement/${skill.key}/start`);
      applyView(view);
    } catch (err) {
      Z.showError($("testError"), err.message);
    }
  }

  async function answer(view, questionId, option) {
    try {
      const next = await call("POST", `/v1/web/placement/${view.skill}/answer`, { question_id: questionId, option });
      applyView(next);
    } catch (err) {
      Z.showError($("testError"), err.message);
    }
  }

  async function skip(skillKey) {
    try {
      const view = await call("POST", `/v1/web/placement/${skillKey}/skip`);
      applyView(view);
    } catch (err) {
      Z.showError($("testError"), err.message);
    }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    Z.initLang();
    const dialog = $("testDialog");
    $("testBegin").addEventListener("click", () => {
      const skill = SKILLS.find((s) => s.key === dialog.dataset.skill);
      startTest(skill);
    });
    dialog.querySelectorAll("[data-close]").forEach((button) => {
      button.addEventListener("click", () => dialog.close());
    });
    // Closing the dialog by any way (Escape, the button) refreshes the rows, so a test left half way shows its state.
    dialog.addEventListener("close", () => refresh());
    try {
      applyState(await ensureLearner());
      renderRows();
    } catch (err) {
      Z.showError($("levelError"), err.message);
      renderRows();
    }
  });
})();
