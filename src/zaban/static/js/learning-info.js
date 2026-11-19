// Learning details: the goal, the levels, and how the teacher should talk. A page of its own, like the level page.
(() => {
  const $ = (id) => document.getElementById(id);
  const isEnglish = () => document.documentElement.lang === "en";
  const t = (fa, en) => (isEnglish() ? en : fa);

  // The learner details need the learner sign-in. The adult gets it by starting their own learning, which needs a plan.
  // Without one, the levels and the teacher settings stay hidden.
  async function learnerDetails() {
    try {
      return await Z.request("GET", "/v1/web/student/details");
    } catch (_) { /* not signed in as the learner yet */ }
    try {
      await Z.request("POST", "/v1/web/user/self");
      return await Z.request("GET", "/v1/web/student/details");
    } catch (_) {
      return null;
    }
  }

  let learnerReady = false;

  function fillLearner(data) {
    learnerReady = Boolean(data);
    $("learnerBox").hidden = !data;
    Z.show($("noLearner"), !data);
    if (!data) return;
    const d = data.details;
    const levels = data.skill_levels || {};
    $("levelListening").value = levels.listening || "A1";
    $("levelReading").value = levels.reading || "A1";
    $("levelGrammar").value = levels.grammar || "A1";
    $("levelWriting").value = levels.writing || "A1";
    $("levelSpeaking").value = levels.speaking || "A1";
    // The speaking and writing levels are chosen once, before the first lesson. After that they only show.
    $("levelWriting").disabled = Boolean(data.speaking_locked);
    $("levelSpeaking").disabled = Boolean(data.speaking_locked);
    const criteria = levels.criteria || {};
    $("criteria").textContent = t(
      `معیارهای گفتاری: دامنه ${criteria.range || "A1"}، دقت ${criteria.accuracy || "A1"}، روانی ${criteria.fluency || "A1"}، تعامل ${criteria.interaction || "A1"}، انسجام ${criteria.coherence || "A1"}`,
      `Speaking criteria: range ${criteria.range || "A1"}, accuracy ${criteria.accuracy || "A1"}, fluency ${criteria.fluency || "A1"}, interaction ${criteria.interaction || "A1"}, coherence ${criteria.coherence || "A1"}`,
    );
    Z.show($("speakingLocked"), Boolean(data.speaking_locked));
    $("attributes").value = d.attributes || "";
    $("conversation").value = d.conversation_style || "";
    $("response").value = d.response_style || "";
    $("sample").value = d.level_sample || "";
    $("free").value = d.free_text || "";
  }

  // Saves the learning text fields. The levels are not sent here: they come from the level test (and the level page).
  // Speaking and writing are sent only while they can still be chosen.
  async function saveLearner() {
    const nullIfEmpty = (value) => value || null;
    await Z.request("PUT", "/v1/web/student/details", {
      attributes: $("attributes").value.trim(),
      conversation_style: nullIfEmpty($("conversation").value),
      response_style: nullIfEmpty($("response").value),
      level_sample: $("sample").value.trim(),
      free_text: $("free").value.trim(),
    });
    if (!$("levelSpeaking").disabled) {
      await Z.request("PUT", "/v1/web/student/skill-levels", {
        speaking: $("levelSpeaking").value,
        writing: $("levelWriting").value,
      });
    }
  }

  async function save(event) {
    event.preventDefault();
    Z.showError($("infoError"), "");
    Z.show($("infoOk"), false);
    try {
      await Z.request("PUT", "/v1/web/user/profile", { goal: $("goal").value || null });
      if (learnerReady) await saveLearner();
      $("infoOk").textContent = t("ذخیره شد.", "Saved.");
      Z.show($("infoOk"), true);
    } catch (err) {
      Z.showError($("infoError"), err.message);
    }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    Z.initLang();
    $("infoForm").addEventListener("submit", save);
    let me = null;
    try {
      me = await Z.request("GET", "/v1/web/me");
    } catch (_) {
      me = null;
    }
    if (!me) {
      Z.show($("signedOutBox"), true);
      return;
    }
    Z.show($("infoForm"), true);
    try {
      const profile = await Z.request("GET", "/v1/web/user/profile");
      $("goal").value = profile.goal || "";
    } catch (err) {
      Z.showError($("infoError"), err.message);
    }
    fillLearner(await learnerDetails());
  });
})();
