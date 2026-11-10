(() => {
  const $ = (id) => document.getElementById(id);
  const API = "/v1/admin/api";

  function show(id, on) {
    Z.show($(id), on);
  }

  function setError(id, message) {
    Z.showError($(id), message);
  }

  // Builds a table from plain text values. Values go through textContent, never innerHTML.
  function fill(table, headers, rows) {
    table.innerHTML = "";
    const head = document.createElement("tr");
    headers.forEach((h) => head.appendChild(Z.el("th", null, h)));
    table.appendChild(head);
    if (!rows.length) {
      const empty = document.createElement("tr");
      const cell = Z.el("td", "muted", "موردی وجود ندارد.");
      cell.colSpan = headers.length;
      empty.appendChild(cell);
      table.appendChild(empty);
      return;
    }
    rows.forEach((cells) => {
      const tr = document.createElement("tr");
      cells.forEach((value) => {
        const td = document.createElement("td");
        if (value instanceof Node) td.appendChild(value);
        else td.textContent = value ?? "—";
        tr.appendChild(td);
      });
      table.appendChild(tr);
    });
  }

  function button(label, onClick) {
    const b = Z.el("button", label.startsWith("رد") ? "danger" : "ghost", label);
    b.type = "button";
    b.addEventListener("click", onClick);
    return b;
  }

  function actions(...buttons) {
    const box = Z.el("div", "actions");
    buttons.forEach((b) => box.appendChild(b));
    return box;
  }

  async function run(fn) {
    setError("adminError", "");
    try {
      await fn();
    } catch (err) {
      setError("adminError", err.message);
    }
  }

  // ----- Tabs -----

  const loaders = {
    consults: loadConsults,
    cooperations: loadCooperations,
    overview: loadOverview,
    helpcontent: loadHelpContent,
    settings: loadSettings,
    connections: loadConnections,
    sessions: loadSessions,
    promptgen: loadPromptGen,
    placementbank: loadBank,
    build: async () => {},
    adults: loadAdults,
    payments: loadPayments,
    plans: loadPlans,
    students: loadStudents,
    global: loadGlobalPrompt,
    voices: loadVoices,
    curriculum: loadCurriculum,
    programs: loadPrograms,
  };

  function openTab(name) {
    document.querySelectorAll(".admin-tabs .tab").forEach((t) => t.classList.toggle("is-active", t.dataset.tab === name));
    ["overview", "consults", "cooperations", "helpcontent", "settings", "connections", "sessions", "promptgen", "placementbank", "build", "adults", "payments", "plans", "students", "curriculum", "programs", "global", "voices"]
      .forEach((n) => show(`tab-${n}`, n === name));
    return run(loaders[name]);
  }

  // ----- Consultation requests -----

  async function loadConsults() {
    const rows = await Z.request("GET", `${API}/consults`);
    fill($("consultTable"), ["زمان", "نام", "موضوع", "شماره", "اجازه‌ی تماس", "زمان ترجیحی", "پیام", "وضعیت", "عملیات"],
      rows.map((r) => [
        Z.fmtDateTime(r.created_at),
        `${r.name} ${r.last_name || ""}`.trim(),
        r.subject || "—",
        r.phone,
        r.contact_permission ? "بله" : "نه",
        r.preferred_time,
        r.message,
        r.status,
        actions(
          button("بررسی شد", () => setConsultStatus(r.id, "reviewed")),
          button("تماس گرفته شد", () => setConsultStatus(r.id, "called")),
          button("تماس مجدد", () => setConsultStatus(r.id, "recall")),
          button("منتظر پاسخ", () => setConsultStatus(r.id, "awaiting_reply")),
          button("بسته شد", () => setConsultStatus(r.id, "closed")),
        ),
      ]));
  }

  function setConsultStatus(id, status) {
    return run(async () => {
      await Z.request("POST", `${API}/consults/${id}/status`, { status });
      await loadConsults();
    });
  }

  // ----- Cooperation requests -----

  async function loadCooperations() {
    const rows = await Z.request("GET", `${API}/cooperations`);
    fill($("cooperationTable"), ["زمان", "موضوع", "شماره", "ایمیل", "توضیحات", "وضعیت", "عملیات"],
      rows.map((r) => [
        Z.fmtDateTime(r.created_at),
        r.subject,
        r.phone,
        r.email,
        r.message,
        r.status,
        actions(
          button("تماس گرفته شد", () => setCooperationStatus(r.id, "contacted")),
          button("بسته شد", () => setCooperationStatus(r.id, "closed")),
        ),
      ]));
  }

  function setCooperationStatus(id, status) {
    return run(async () => {
      await Z.request("POST", `${API}/cooperations/${id}/status`, { status });
      await loadCooperations();
    });
  }

  // ----- Overview, learner detail, help content, settings and build -----

  function kv(label, value) {
    return Z.el("div", "kv", `${label}: ${value}`);
  }

  async function loadOverview() {
    const data = await Z.request("GET", `${API}/overview`);
    const box = $("overviewBox");
    box.replaceChildren(
      kv("ثبت‌نام‌کنندگان بزرگسال", data.users.adults),
      kv("دانش‌آموزان", data.users.learners),
      kv("پلن‌های فعال", data.active_plans),
      kv("پرداخت‌ها (بر اساس وضعیت)", JSON.stringify(data.payments)),
      kv("درخواست‌های مشاوره", JSON.stringify(data.consults)),
      kv("درخواست‌های همکاری", JSON.stringify(data.cooperations)),
      kv("جلسه‌ها (کل / کامل‌شده)", `${data.lessons.total} / ${data.lessons.completed}`),
      kv("آزمون‌های «خودت رو محک بزن»", data.self_tests),
    );
    data.tokens.forEach((t) => box.appendChild(kv(`توکن ${t.tenant}`,
      `مصرف ${t.used} از ${t.quota} (${t.percent_used}٪) — باقی‌مانده ${t.remaining}`
      + (t.expires_at ? ` — انقضا ${Z.fmtDate(t.expires_at)}` : ""))));
  }

  async function loadLearner(event) {
    event.preventDefault();
    const id = $("learnerId").value.trim();
    const box = $("learnerBox");
    box.replaceChildren();
    try {
      const d = await Z.request("GET", `${API}/learners/${encodeURIComponent(id)}`);
      box.append(
        kv("نام", d.display_name || "—"),
        kv("سن (گروه)", d.age_band),
        kv("سطح", d.cefr_level || "تعیین نشده"),
        kv("اطلاعات", JSON.stringify(d.details)),
        kv("برنامه", d.progress.program ? `${d.progress.program.name} — ${d.progress.percent}٪` : "بدون برنامه"),
        kv("ارزیابی‌ها", d.evaluations || "—"),
      );
    } catch (err) {
      box.appendChild(Z.el("p", "error", err.message));
    }
  }

  async function loadHelpContent() {
    const rows = await Z.request("GET", `${API}/help-content`);
    fill($("helpTable"), ["عنوان", "دسته", "گروه سنی", "سطح", "منبع", "عملیات"],
      rows.map((r) => [
        r.title,
        r.category,
        r.age_band,
        r.level,
        r.url || `فایل (${Math.round(r.size_bytes / 1024)} کیلوبایت)`,
        actions(button("حذف", () => deleteHelpContent(r.id))),
      ]));
  }

  function deleteHelpContent(id) {
    return run(async () => {
      if (!confirm("این محتوا حذف شود؟")) return;
      await Z.request("DELETE", `${API}/help-content/${id}`);
      await loadHelpContent();
    });
  }

  function readFileBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(",")[1]);
      reader.onerror = () => reject(new Error("فایل خوانده نشد"));
      reader.readAsDataURL(file);
    });
  }

  async function addHelpContent(event) {
    event.preventDefault();
    Z.showError($("hcError"), "");
    const file = $("hcFile").files[0];
    const url = $("hcUrl").value.trim();
    const body = {
      title: $("hcTitle").value.trim(),
      category: $("hcCategory").value,
      age_band: $("hcBand").value,
      level: $("hcLevel").value,
      gender: $("hcGender").value || null,
      interests: $("hcInterests").value.trim(),
      stage: $("hcStage").value.trim() || null,
    };
    if (file) {
      body.data_base64 = await readFileBase64(file);
      body.mime = file.type || "application/octet-stream";
    } else {
      body.url = url || null;
    }
    try {
      await Z.request("POST", `${API}/help-content`, body);
      event.target.reset();
      await loadHelpContent();
    } catch (err) {
      Z.showError($("hcError"), err.message);
    }
  }

  async function loadSettings() {
    const data = await Z.request("GET", `${API}/settings`);
    $("setMode").value = data.prompt_mode;
    $("setExpected").value = data.expected_output || "";
    $("setProvider").value = data.payment_provider;
    $("secretsList").replaceChildren(
      ...Object.entries(data.secrets).map(([k, v]) => Z.el("li", "", `${k}: ${v === true ? "تنظیم شده" : v === false ? "تنظیم نشده" : v}`)),
    );
    const prompt = await Z.request("GET", `${API}/self-test-prompt`);
    $("stPrompt").value = prompt.text;
  }

  function saveSettings() {
    return run(async () => {
      await Z.request("POST", `${API}/settings`, {
        prompt_mode: $("setMode").value,
        expected_output: $("setExpected").value,
        payment_provider: $("setProvider").value,
      });
      $("settingsNotice").hidden = false;
      $("settingsNotice").textContent = "تنظیمات ذخیره شد.";
    });
  }

  function saveSelfTestPrompt() {
    return run(async () => {
      await Z.request("POST", `${API}/self-test-prompt`, { text: $("stPrompt").value });
      $("settingsNotice").hidden = false;
      $("settingsNotice").textContent = "پرامپت آزمون ذخیره شد.";
    });
  }

  async function downloadBuild(event) {
    event.preventDefault();
    Z.showError($("buildError"), "");
    const since = $("buildSince").value.trim();
    const query = since ? `?since=${encodeURIComponent(since)}` : "";
    const response = await fetch(`${API}/build${query}`, { method: "POST", credentials: "same-origin" });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      Z.showError($("buildError"), typeof data.detail === "string" ? data.detail : "خروجی ساخته نشد.");
      return;
    }
    const blob = await response.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "zaban-build.zip";
    link.click();
    URL.revokeObjectURL(link.href);
  }

  // ----- Sign-ups -----

  async function loadAdults() {
    const rows = await Z.request("GET", `${API}/adults`);
    // Plans are extended only when a payment is confirmed in the payments tab, never by hand here.
    fill($("adultTable"), ["ثبت‌نام", "نام", "شماره", "هدف", "نوع پلن", "اعتبار پلن تا", "وضعیت", "عملیات"],
      rows.map((a) => [
        Z.fmtDate(a.created_at),
        a.name,
        a.phone,
        a.goal,
        a.plan_name || "—",
        a.plan_expires_at && new Date(a.plan_expires_at) > new Date() ? Z.fmtDate(a.plan_expires_at) : "بدون پلن فعال",
        a.suspended ? "تعلیق" : "فعال",
        button(a.suspended ? "فعال کردن" : "تعلیق کردن", () => setSuspension(a.id, !a.suspended)),
      ]));
  }

  // A suspended adult cannot sign in and cannot open any page until the suspension is lifted.
  function setSuspension(adultId, suspended) {
    const message = suspended
      ? "این کاربر تعلیق شود؟ ورود او بسته می‌شود و همه‌ی نشست‌های فعالش بسته می‌شوند."
      : "تعلیق این کاربر برداشته شود؟";
    if (!confirm(message)) return;
    return run(async () => {
      await Z.request("POST", `${API}/adults/${adultId}/suspension`, { suspended });
      await loadAdults();
    });
  }

  // ----- Payments -----

  async function loadPayments() {
    const rows = await Z.request("GET", `${API}/payments?status=paid`);
    // Confirming adds the plan's days to the adult's plan period, counted from today or from the current end date.
    fill($("paymentTable"), ["زمان", "نام", "شماره", "پلن", "مدت (روز)", "مبلغ (تومان)", "درگاه", "عملیات"],
      rows.map((p) => [
        Z.fmtDateTime(p.created_at),
        p.adult,
        p.phone,
        p.plan,
        p.days,
        p.amount_toman.toLocaleString("fa-IR"),
        p.gateway,
        actions(
          button("تأیید پرداخت", () => decide(p.id, true)),
          button("رد پرداخت", () => decide(p.id, false)),
        ),
      ]));
  }

  function decide(id, ok) {
    return run(async () => {
      await Z.request("POST", `${API}/payments/${id}/decision`, { ok });
      await loadPayments();
    });
  }

  // ----- Plans -----

  let plansCache = [];

  // The edit form shows the chosen plan. Saving changes only the fields that were filled in.
  function fillPlanEdit(plan) {
    $("planEditName").value = plan.name || "";
    $("planEditNameEn").value = plan.name_en || "";
    $("planEditPrice").value = plan.price_toman;
    $("planEditDays").value = plan.days;
    $("planEditTokens").value = plan.token_allowance;
    $("planEditDescription").value = plan.description || "";
  }

  function savePlanEdit(event) {
    event.preventDefault();
    const id = $("planEditSelect").value;
    if (!id) return;
    return run(async () => {
      show("planEditError", false);
      await Z.request("POST", `${API}/plans/${id}/update`, {
        name: $("planEditName").value.trim(),
        name_en: $("planEditNameEn").value.trim(),
        price_toman: Number($("planEditPrice").value),
        days: Number($("planEditDays").value),
        token_allowance: Number($("planEditTokens").value),
        description: $("planEditDescription").value.trim(),
      });
      $("planEditNotice").hidden = false;
      $("planEditNotice").textContent = "پلن ذخیره شد.";
      await loadPlans();
    });
  }

  async function loadPlans() {
    const rows = await Z.request("GET", `${API}/plans`);
    plansCache = rows;
    $("planEditSelect").replaceChildren(...rows.map((p) => {
      const option = Z.el("option", "", p.name);
      option.value = p.id;
      return option;
    }));
    if (rows.length) fillPlanEdit(rows[0]);
    fill($("planTable"), ["پلن", "قیمت (تومان)", "مدت (روز)", "وضعیت", "عملیات"],
      rows.map((p) => [
        p.name,
        p.price_toman.toLocaleString("fa-IR"),
        p.days,
        p.active ? "فعال" : "غیرفعال",
        actions(button(p.active ? "غیرفعال کردن" : "فعال کردن", () => setPlanActive(p.id, !p.active))),
      ]));
  }

  function setPlanActive(id, active) {
    return run(async () => {
      await Z.request("POST", `${API}/plans/${id}/active`, { active });
      await loadPlans();
    });
  }

  async function addPlan(event) {
    event.preventDefault();
    const form = event.target;
    setError("planError", "");
    try {
      await Z.request("POST", `${API}/plans`, {
        name: $("planName").value.trim(),
        name_en: $("planNameEn").value.trim(),
        price_toman: Number($("planPrice").value),
        days: Number($("planDays").value),
        description: "",
      });
      form.reset();
      await loadPlans();
    } catch (err) {
      setError("planError", err.message);
    }
  }

  // ----- Students and their lesson notes -----

  const PROFILE_LIMIT = 2000;
  let editingStudent = null;

  async function loadStudents() {
    const rows = await Z.request("GET", `${API}/students`);
    fill($("studentTable"), ["نام", "نوع", "نام کاربری", "سطح", "پرامپت", "عملیات"],
      rows.map((s) => [
        s.name || "—",
        s.kind === "self" ? "بزرگسال" : "کودک",
        s.username,
        s.cefr_level,
        s.instructions ? `${s.instructions.slice(0, 60)}…` : "بدون پرامپت",
        actions(button("ویرایش پرامپت", () => openProfile(s))),
      ]));
  }

  function openProfile(student) {
    editingStudent = student;
    setError("profileError", "");
    Z.show($("profileOk"), false);
    $("profileTitle").textContent = `پرامپت: ${student.name || student.username || "دانش‌آموز"}`;
    $("profileInterests").value = student.interests;
    $("profileMotivation").value = student.motivation;
    $("profileText").value = student.instructions;
    updateProfileCount();
    Z.show($("promptPreview"), false);
    show("profileForm", true);
    $("profileInterests").focus();
  }

  // The prompt a lesson for this learner starts with. Each part is shown with the source it comes from.
  const PROMPT_PARTS = [
    ["intro", "معرفی معلم"],
    ["accent", "لهجه‌ی تمرین"],
    ["admin", "۱. دستورهای کلی ادمین"],
    ["database", "۲. اطلاعات از دیتابیس"],
    ["learner", "۳. پرامپت اختصاصی این دانش‌آموز"],
    ["lesson", "۴. جلسه‌ی برنامه"],
    ["expected", "۵. انتظار ادمین از جلسه"],
    ["rules", "قوانین ایمنی"],
  ];

  async function previewPrompt() {
    setError("profileError", "");
    const data = await Z.request("GET", `${API}/students/${editingStudent.id}/start-prompt`);
    const box = $("promptPreview");
    box.replaceChildren();
    PROMPT_PARTS.forEach(([key, title]) => {
      const section = document.createElement("details");
      section.open = true;
      const heading = document.createElement("summary");
      heading.textContent = title;
      const body = document.createElement("pre");
      body.className = "prompt-part";
      body.textContent = data.parts[key] || "— این بخش در این دانش‌آموز خالی است —";
      section.append(heading, body);
      box.appendChild(section);
    });
    const final = document.createElement("details");
    const finalHeading = document.createElement("summary");
    finalHeading.textContent = "پرامپت نهایی؛ این متن اولین ورودی API در شروع جلسه است";
    const finalBody = document.createElement("pre");
    finalBody.className = "prompt-part";
    finalBody.textContent = data.prompt;
    final.append(finalHeading, finalBody);
    box.appendChild(final);
    Z.show(box, true);
  }

  // ----- Voice samples -----

  const VOICE_TYPES = { "audio/mpeg": "audio/mpeg", "audio/mp3": "audio/mpeg", "audio/wav": "audio/wav", "audio/x-wav": "audio/wav", "audio/wave": "audio/wav", "audio/ogg": "audio/ogg", "audio/mp4": "audio/mp4", "audio/x-m4a": "audio/mp4", "audio/m4a": "audio/mp4" };
  const VOICE_EXT = { mp3: "audio/mpeg", wav: "audio/wav", ogg: "audio/ogg", m4a: "audio/mp4", mp4: "audio/mp4" };
  const VOICE_LIMIT = 3 * 1024 * 1024;

  async function loadVoices() {
    const rows = await Z.request("GET", `${API}/voice-samples`);
    fill($("voiceTable"), ["نام", "لهجه", "حجم", "افزوده شده", "عملیات"],
      rows.map((s) => [
        s.name,
        s.accent,
        `${Math.round(s.size_bytes / 1024)} KB`,
        Z.fmtDate(s.created_at),
        actions(button("حذف", () => deleteVoice(s.id))),
      ]));
  }

  // The file type comes from the browser, or from the extension when the browser sends none.
  function audioTypeOf(file) {
    if (VOICE_TYPES[file.type]) return VOICE_TYPES[file.type];
    const ext = file.name.split(".").pop().toLowerCase();
    return VOICE_EXT[ext] || null;
  }

  function readAsBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(",")[1]);
      reader.onerror = () => reject(new Error("فایل خوانده نشد."));
      reader.readAsDataURL(file);
    });
  }

  async function addVoice(event) {
    event.preventDefault();
    Z.showError($("voiceError"), "");
    Z.show($("voiceOk"), false);
    const file = $("voiceFile").files[0];
    if (!file) return;
    const mime = audioTypeOf(file);
    if (!mime) {
      Z.showError($("voiceError"), "این نوع فایل پشتیبانی نمی‌شود. فایل mp3، wav، ogg یا m4a انتخاب کنید.");
      return;
    }
    if (file.size > VOICE_LIMIT) {
      Z.showError($("voiceError"), "فایل بزرگ‌تر از ۳ مگابایت است.");
      return;
    }
    try {
      await Z.request("POST", `${API}/voice-samples`, {
        name: $("voiceName").value.trim(),
        accent: $("voiceAccent").value,
        mime,
        data_base64: await readAsBase64(file),
      });
      event.target.reset();
      $("voiceOk").textContent = "نمونه ذخیره شد.";
      Z.show($("voiceOk"), true);
      await loadVoices();
    } catch (err) {
      Z.showError($("voiceError"), err.message);
    }
  }

  function deleteVoice(id) {
    return run(async () => {
      await Z.request("DELETE", `${API}/voice-samples/${id}`);
      await loadVoices();
    });
  }

  // ----- General prompt -----

  async function loadGlobalPrompt() {
    const data = await Z.request("GET", `${API}/global-prompt`);
    $("globalText").value = data.text;
    updateGlobalCount();
  }

  function updateGlobalCount() {
    $("globalCount").textContent = `${$("globalText").value.length} / 4000`;
  }

  async function saveGlobalPrompt(event) {
    event.preventDefault();
    setError("globalError", "");
    Z.show($("globalOk"), false);
    try {
      await Z.request("POST", `${API}/global-prompt`, { text: $("globalText").value });
      $("globalOk").textContent = "پرامپت کلی ذخیره شد. از جلسه‌ی بعدی همه استفاده می‌شود.";
      Z.show($("globalOk"), true);
    } catch (err) {
      setError("globalError", err.message);
    }
  }

  function updateProfileCount() {
    $("profileCount").textContent = `${$("profileText").value.length} / ${PROFILE_LIMIT}`;
  }

  async function saveProfile(event) {
    event.preventDefault();
    setError("profileError", "");
    Z.show($("profileOk"), false);
    try {
      await Z.request("POST", `${API}/students/${editingStudent.id}/profile`, {
        interests: $("profileInterests").value,
        motivation: $("profileMotivation").value,
        instructions: $("profileText").value,
      });
      editingStudent = null;
      show("profileForm", false);
      await loadStudents();
      $("profileOk").textContent = "پرامپت ذخیره شد. از جلسه‌ی بعدی این دانش‌آموز استفاده می‌شود.";
      Z.show($("profileOk"), true);
    } catch (err) {
      setError("profileError", err.message);
    }
  }

  // ----- Curriculum -----

  let curriculum = null;

  function fillSelect(select, pairs) {
    const current = select.value;
    select.innerHTML = "";
    pairs.forEach(([value, label]) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      select.appendChild(option);
    });
    if (pairs.some(([value]) => value === current)) select.value = current;
  }

  function selectedVariantId() {
    return `${$("curTopic").value}.${$("curBand").value}.${$("curLevel").value}`;
  }

  function editVariant(id) {
    const [topic, band, level] = id.split(".");
    $("curTopic").value = topic;
    $("curBand").value = band;
    $("curLevel").value = level;
    showSelectedVariant();
  }

  function renderTopics() {
    fill($("topicTable"), ["شناسه", "موضوع", "هدف گفتگو", "سطح‌ها", "بازه‌ها", "نسخه‌های نوشته‌شده"],
      curriculum.topics.map((t) => {
        const written = t.slots.filter((s) => s.written).length;
        const levels = t.levels.length > 1 ? `${t.levels[0]} تا ${t.levels[t.levels.length - 1]}` : t.levels[0];
        return [t.id, t.title, t.goal, levels, t.bands.join(" "), `${written} از ${t.slots.length}`];
      }));
  }

  function renderVariants() {
    fill($("variantTable"), ["شناسه", "شروع جمله", "عبارت‌ها", "سبک", "عملیات"],
      curriculum.variants.map((v) => [
        v.id,
        v.opener,
        v.phrases.join(" · "),
        v.style,
        actions(button("ویرایش", () => editVariant(v.id))),
      ]));
  }

  function showSelectedVariant() {
    const id = selectedVariantId();
    const variant = curriculum.variants.find((v) => v.id === id);
    $("variantTitle").textContent = variant
      ? `نسخه‌ی ${id} — نوشته شده`
      : `نسخه‌ی ${id} — هنوز نوشته نشده؛ با ذخیره، ساخته می‌شود.`;
    $("variantOpener").value = variant ? variant.opener : "";
    $("variantPhrases").value = variant ? variant.phrases.join("\n") : "";
    $("variantStyle").value = variant ? variant.style : "";
    setError("variantError", "");
    Z.show($("variantOk"), false);
  }

  async function loadCurriculum() {
    curriculum = await Z.request("GET", `${API}/curriculum`);
    $("curriculumVersion").textContent = `نسخه‌ی کاتالوگ: ${curriculum.version}`;
    // fillSelect keeps the current choice when it still exists, so a reload stays on the same version.
    fillSelect($("curTopic"), curriculum.topics.map((t) => [t.id, `${t.title} (${t.id})`]));
    fillSelect($("curBand"), curriculum.bands.map((b) => [b.code, `${b.code} — ${b.label}`]));
    fillSelect($("curLevel"), curriculum.levels.map((l) => [l, l]));
    showSelectedVariant();
    renderTopics();
    renderVariants();
  }

  async function saveVariant(event) {
    event.preventDefault();
    setError("variantError", "");
    const id = selectedVariantId();
    const body = {
      opener: $("variantOpener").value,
      phrases: $("variantPhrases").value.split("\n").map((p) => p.trim()).filter(Boolean),
      style: $("variantStyle").value,
    };
    try {
      const exists = curriculum.variants.some((v) => v.id === id);
      if (exists) {
        await Z.request("PUT", `${API}/curriculum/variants/${id}`, body);
      } else {
        const [topic_id, band, level] = id.split(".");
        await Z.request("POST", `${API}/curriculum/variants`, { topic_id, band, level, ...body });
      }
      await loadCurriculum();
      editVariant(id);
      $("variantOk").textContent = "نسخه ذخیره شد. نسخه‌ی کاتالوگ بالا رفت و از جلسه‌ی بعدی استفاده می‌شود.";
      Z.show($("variantOk"), true);
    } catch (err) {
      setError("variantError", err.message);
    }
  }

  // ----- Learning programs -----

  let programs = null;

  function selectedProgram() {
    return programs ? programs.programs.find((p) => p.id === $("progSelect").value) : null;
  }

  function showProgramItem(number) {
    const program = selectedProgram();
    const item = program && program.items.find((i) => i.position === number);
    if (!item) return;
    $("progNumber").value = item.position;
    $("progTitle").value = item.title;
    $("progTitleEn").value = item.title_en || "";
    $("progStage").value = item.stage || "";
    $("progConcepts").value = (item.concepts || []).join("\n");
    $("progDuration").value = program.duration_months;
    $("progActivity").value = item.activity;
    $("progPhrases").value = item.phrases.join("\n");
    setError("progError", "");
    Z.show($("progOk"), false);
  }

  function renderProgramItems() {
    const program = selectedProgram();
    $("programVersion").textContent = program ? `نسخه‌ی برنامه: ${program.version} — هر ذخیره نسخه را بالا می‌برد.` : "";
    fill($("progItemsTable"), ["جلسه", "عنوان", "فعالیت", "عبارت‌ها", "عملیات"],
      program ? program.items.map((i) => [
        i.position,
        i.title,
        i.activity,
        i.phrases.join(" · "),
        actions(button("ویرایش", () => showProgramItem(i.position))),
      ]) : []);
  }

  async function loadPrograms() {
    programs = await Z.request("GET", `${API}/programs`);
    const current = $("progSelect").value;
    fillSelect($("progSelect"), programs.programs.map((p) => [p.id, p.name]));
    if (current) $("progSelect").value = current;
    renderProgramItems();
    if (programs.programs.length) showProgramItem(1);
    const approvals = await Z.request("GET", `${API}/program-approvals`);
    fill($("approvalTable"), ["دانش‌آموز", "برنامه", "جلسه‌های انجام‌شده", "عملیات"],
      approvals.map((a) => [
        a.name || "—",
        a.program,
        a.done,
        actions(button("تأیید ادامه", () => approveProgram(a.student_id))),
      ]));
  }

  async function approveProgram(studentId) {
    await run(async () => {
      await Z.request("POST", `${API}/students/${studentId}/resume-program`);
      await loadPrograms();
    });
  }

  async function saveProgramDuration(event) {
    event.preventDefault();
    const program = selectedProgram();
    if (!program) return;
    await run(async () => {
      await Z.request("POST", `${API}/programs/${program.id}/duration`, { duration_months: Number($("progDuration").value) });
      await loadPrograms();
    });
  }

  async function saveProgramItem(event) {
    event.preventDefault();
    setError("progError", "");
    const program = selectedProgram();
    if (!program) return;
    try {
      const number = Number($("progNumber").value);
      const result = await Z.request("PUT", `${API}/programs/${program.id}/items/${number}`, {
        title: $("progTitle").value,
        title_en: $("progTitleEn").value.trim(),
        stage: $("progStage").value.trim(),
        concepts: $("progConcepts").value.split("\n").map((c) => c.trim()).filter(Boolean),
        activity: $("progActivity").value,
        phrases: $("progPhrases").value.split("\n").map((p) => p.trim()).filter(Boolean),
      });
      await loadPrograms();
      showProgramItem(number);
      $("progOk").textContent = `جلسه ذخیره شد. نسخه‌ی برنامه: ${result.version}`;
      Z.show($("progOk"), true);
    } catch (err) {
      setError("progError", err.message);
    }
  }

  // ----- Sign-in and boot -----

  async function signIn(event) {
    event.preventDefault();
    setError("adminLoginError", "");
    try {
      await Z.request("POST", `${API}/login`, { password: $("adminPassword").value });
      $("adminPassword").value = "";
      enterConsole();
    } catch (err) {
      setError("adminLoginError", err.message);
    }
  }

  function enterConsole() {
    show("adminLogin", false);
    show("adminApp", true);
    mountAdminMenu();
    mountAdminNav();
    openTab("consults");
  }

  // The sign-out lives in the profile menu of the header, as it does for the website.
  function mountAdminMenu() {
    const box = document.getElementById("siteActions");
    if (!box) return;
    box.replaceChildren();
    box.appendChild(Z.el("span", "site-greeting", "مدیر"));
    const wrap = Z.el("div", "account-menu");
    const avatar = Z.el("button", "avatar-btn");
    avatar.type = "button";
    avatar.setAttribute("aria-haspopup", "menu");
    avatar.setAttribute("aria-expanded", "false");
    avatar.insertAdjacentHTML("beforeend", '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8.5" r="4"/><path d="M4.5 20.5c1.2-3.6 4-5.5 7.5-5.5s6.3 1.9 7.5 5.5"/></svg>');
    const list = Z.el("div", "account-menu-list");
    list.setAttribute("role", "menu");
    const item = Z.el("button", "account-item danger", "خروج");
    item.type = "button";
    item.setAttribute("role", "menuitem");
    item.addEventListener("click", signOut);
    list.appendChild(item);
    const close = () => {
      list.classList.remove("is-open");
      avatar.setAttribute("aria-expanded", "false");
    };
    avatar.addEventListener("click", (event) => {
      event.stopPropagation();
      const open = !list.classList.contains("is-open");
      list.classList.toggle("is-open", open);
      avatar.setAttribute("aria-expanded", String(open));
    });
    document.addEventListener("click", (event) => {
      if (!event.target.closest(".account-menu")) close();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") close();
    });
    wrap.append(avatar, list);
    box.appendChild(wrap);
  }

  // On a desktop the console sections are listed in the side menu. On a phone they stay as a row under the header.
  function mountAdminNav() {
    const side = document.getElementById("memberNav");
    const tabs = document.querySelector("#adminApp .admin-tabs");
    if (!side || !tabs || !window.matchMedia("(min-width: 761px)").matches) return;
    side.appendChild(tabs);
    side.hidden = false;
  }

  // ----- Prompt generator -----

  async function loadPromptGen() {
    const data = await Z.request("GET", `${API}/prompt-template`);
    $("genTemplate").value = data.template;
    $("genPlaceholders").replaceChildren(
      ...data.placeholders.map((p) => Z.el("li", "", `{{${p.key}}}  ${p.label}`)),
    );
    const students = await Z.request("GET", `${API}/students`);
    $("genLearner").replaceChildren(
      ...students.map((s) => {
        const option = Z.el("option", "", `${s.name || "—"}${s.kind === "self" ? " (یادگیری خود)" : ""}`);
        option.value = s.id;
        return option;
      }),
    );
  }

  function saveGenTemplate(text) {
    return run(async () => {
      await Z.request("POST", `${API}/prompt-template`, { template: text });
      $("genNotice").hidden = false;
      $("genNotice").textContent = "قالب ذخیره شد.";
    });
  }

  function generatePrompt() {
    return run(async () => {
      show("genError", false);
      show("genUnknown", false);
      if (!$("genLearner").value) {
        $("genError").hidden = false;
        $("genError").textContent = "ابتدا یک دانش‌آموز انتخاب کنید.";
        return;
      }
      const result = await Z.request("POST", `${API}/prompt/generate`, { student_id: $("genLearner").value });
      $("genOutput").value = result.prompt;
      if (result.unknown_placeholders.length) {
        $("genUnknown").hidden = false;
        $("genUnknown").textContent = `این کلیدها در سامانه نیستند و خالی ماندند: ${result.unknown_placeholders.join("، ")}`;
      }
    });
  }

  // ----- Level test question bank -----

  let bankRows = [];

  async function loadBank() {
    bankRows = await Z.request("GET", `${API}/placement-questions`);
    const skillName = { reading: "خواندن", grammar: "دستور و واژگان", listening: "شنیداری" };
    fill($("bankTable"), ["مهارت", "سطح", "سؤال", "گزینه‌ها", "درست", "فعال", "عملیات"],
      bankRows.map((q) => [
        skillName[q.skill] || q.skill,
        q.level,
        q.text,
        q.options.join(" / "),
        String(q.answer),
        q.active ? "بله" : "خیر",
        button("ویرایش", () => editBank(q)),
      ]));
  }

  function editBank(q) {
    $("bankId").value = String(q.id);
    $("bankFormTitle").textContent = `ویرایش سؤال ${q.id}`;
    $("bankSkill").value = q.skill;
    $("bankLevel").value = q.level;
    $("bankText").value = q.text;
    $("bankOptions").value = q.options.join("\n");
    $("bankAnswer").value = String(q.answer);
    $("bankAudio").value = q.audio_text || "";
    $("bankActive").checked = q.active;
  }

  function resetBank() {
    $("bankId").value = "";
    $("bankFormTitle").textContent = "افزودن سؤال";
    $("bankForm").reset();
    $("bankActive").checked = true;
  }

  function saveBank(event) {
    event.preventDefault();
    return run(async () => {
      show("bankError", false);
      const options = $("bankOptions").value.split("\n").map((line) => line.trim()).filter(Boolean);
      const body = {
        skill: $("bankSkill").value,
        level: $("bankLevel").value,
        text: $("bankText").value.trim(),
        options,
        answer: Number($("bankAnswer").value),
        audio_text: $("bankAudio").value.trim(),
        active: $("bankActive").checked,
      };
      const id = $("bankId").value;
      await Z.request("POST", id ? `${API}/placement-questions/${id}` : `${API}/placement-questions`, body);
      $("bankNotice").hidden = false;
      $("bankNotice").textContent = "سؤال ذخیره شد.";
      resetBank();
      await loadBank();
    });
  }

  // ----- Active sign-ins -----

  let sessionGroups = [];
  const selectedSessions = new Set();
  const expandedPeople = new Set();

  async function loadSessions() {
    sessionGroups = await Z.request("GET", `${API}/sessions`);
    const live = new Set(sessionGroups.flatMap((g) => g.sessions.map((s) => s.id)));
    [...selectedSessions].forEach((id) => { if (!live.has(id)) selectedSessions.delete(id); });
    renderSessions();
  }

  function renderSessions() {
    const total = sessionGroups.reduce((n, g) => n + g.sessions.length, 0);
    $("sesCount").textContent = `${sessionGroups.length} کاربر، ${total} نشست`;
    const all = $("sesAll");
    all.checked = total > 0 && selectedSessions.size === total;
    all.indeterminate = selectedSessions.size > 0 && selectedSessions.size < total;
    $("sesRevoke").disabled = selectedSessions.size === 0;
    $("sesRevoke").textContent = selectedSessions.size
      ? `بستن ${selectedSessions.size} نشست انتخاب‌شده`
      : "بستن نشست‌های انتخاب‌شده";
    const list = $("sesList");
    list.replaceChildren();
    if (!sessionGroups.length) {
      list.appendChild(Z.el("p", "muted", "نشست فعالی وجود ندارد."));
      return;
    }
    sessionGroups.forEach((group) => list.appendChild(sessionGroupRow(group)));
  }

  function sessionGroupRow(group) {
    const key = `${group.role}:${group.subject_id}`;
    const ids = group.sessions.map((s) => s.id);
    const picked = ids.filter((id) => selectedSessions.has(id)).length;
    const card = Z.el("div", "card session-group");

    const head = Z.el("div", "session-head");
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = picked === ids.length;
    box.indeterminate = picked > 0 && picked < ids.length;
    box.setAttribute("aria-label", "انتخاب همه‌ی نشست‌های این کاربر");
    box.addEventListener("change", () => {
      ids.forEach((id) => (box.checked ? selectedSessions.add(id) : selectedSessions.delete(id)));
      renderSessions();
    });
    const info = Z.el("div", "session-info");
    info.appendChild(Z.el("strong", "", group.name || "—"));
    info.appendChild(Z.el("span", "muted", `${group.role === "guardian" ? "بزرگسال" : "یادگیری خود"} · ${group.contact}`));
    const badge = Z.el("span", "session-badge", `${ids.length} نشست`);
    const toggle = Z.el("button", "ghost session-toggle", expandedPeople.has(key) ? "بستن فهرست" : "نمایش نشست‌ها");
    toggle.type = "button";
    toggle.setAttribute("aria-expanded", String(expandedPeople.has(key)));
    toggle.addEventListener("click", () => {
      if (expandedPeople.has(key)) expandedPeople.delete(key);
      else expandedPeople.add(key);
      renderSessions();
    });
    head.append(box, info, badge, toggle);
    card.appendChild(head);

    if (expandedPeople.has(key)) {
      group.sessions.forEach((session) => {
        const row = Z.el("label", "session-row");
        const one = document.createElement("input");
        one.type = "checkbox";
        one.checked = selectedSessions.has(session.id);
        one.addEventListener("change", () => {
          if (one.checked) selectedSessions.add(session.id);
          else selectedSessions.delete(session.id);
          renderSessions();
        });
        const text = Z.el("span", "session-text");
        text.appendChild(Z.el("span", "", `شروع: ${Z.fmtDateTime(session.started_at)}`));
        text.appendChild(Z.el("span", "muted", `${session.ip || "—"} · ${(session.user_agent || "دستگاه نامشخص").slice(0, 70)}`));
        row.append(one, text);
        card.appendChild(row);
      });
    }
    return card;
  }

  function revokeSessions() {
    const ids = [...selectedSessions];
    if (!ids.length) return;
    if (!confirm(`${ids.length} نشست بسته شود؟ دستگاه‌های مربوط باید دوباره وارد شوند.`)) return;
    return run(async () => {
      const result = await Z.request("POST", `${API}/sessions/revoke`, { ids });
      selectedSessions.clear();
      $("sesNotice").hidden = false;
      $("sesNotice").textContent = `${result.revoked} نشست بسته شد.`;
      await loadSessions();
    });
  }

  async function loadConnections() {
    const data = await Z.request("GET", `${API}/connections`);
    $("connSmsProvider").value = data.sms_provider;
    $("connSmsKeyHint").textContent = data.sms_api_key_set ? `کلید فعلی: ${data.sms_api_key_masked}` : "کلیدی ثبت نشده است.";
    $("connSmsTemplate").value = data.sms_otp_template || "";
    $("connPayProvider").value = data.payment_provider;
    $("connMerchantHint").textContent = data.zarinpal_merchant_set ? `کد فعلی: ${data.zarinpal_merchant_masked}` : "کدی ثبت نشده است.";
    $("connCallback").textContent = data.callback_url;
    $("connSmsKey").value = "";
    $("connMerchant").value = "";
  }

  function saveConnections() {
    return run(async () => {
      const body = {
        sms_provider: $("connSmsProvider").value,
        sms_otp_template: $("connSmsTemplate").value,
        payment_provider: $("connPayProvider").value,
      };
      if ($("connSmsKey").value.trim()) body.sms_api_key = $("connSmsKey").value.trim();
      if ($("connMerchant").value.trim()) body.zarinpal_merchant_id = $("connMerchant").value.trim();
      await Z.request("POST", `${API}/connections`, body);
      $("connNotice").hidden = false;
      $("connNotice").textContent = "اتصال‌ها ذخیره شد.";
      await loadConnections();
    });
  }

  async function signOut() {
    await Z.request("POST", `${API}/logout`).catch(() => {});
    location.reload();
  }

  document.addEventListener("DOMContentLoaded", async () => {
    Z.initLang();
    $("adminLoginForm").addEventListener("submit", signIn);
    $("connSave").addEventListener("click", saveConnections);
    $("planEditForm").addEventListener("submit", savePlanEdit);
    $("bankForm").addEventListener("submit", saveBank);
    $("bankReset").addEventListener("click", resetBank);
    $("planEditSelect").addEventListener("change", () => {
      const plan = plansCache.find((p) => p.id === $("planEditSelect").value);
      if (plan) fillPlanEdit(plan);
    });
    $("sesAll").addEventListener("change", () => {
      sessionGroups.forEach((g) => g.sessions.forEach((s) => ($("sesAll").checked ? selectedSessions.add(s.id) : selectedSessions.delete(s.id))));
      renderSessions();
    });
    $("sesRevoke").addEventListener("click", revokeSessions);
    $("genTemplateSave").addEventListener("click", () => saveGenTemplate($("genTemplate").value));
    $("genTemplateReset").addEventListener("click", async () => {
      const data = await Z.request("GET", `${API}/prompt-template`);
      $("genTemplate").value = data.default_template;
    });
    $("genRun").addEventListener("click", generatePrompt);
    $("genCopy").addEventListener("click", () => navigator.clipboard.writeText($("genOutput").value));
    $("planForm").addEventListener("submit", addPlan);
    $("profileForm").addEventListener("submit", saveProfile);
    $("globalForm").addEventListener("submit", saveGlobalPrompt);
    $("voiceForm").addEventListener("submit", addVoice);
    $("variantForm").addEventListener("submit", saveVariant);
    $("progItemForm").addEventListener("submit", saveProgramItem);
    $("progDurationForm").addEventListener("submit", saveProgramDuration);
    $("progSelect").addEventListener("change", () => { renderProgramItems(); showProgramItem(1); });
    ["curTopic", "curBand", "curLevel"].forEach((id) => $(id).addEventListener("change", showSelectedVariant));
    $("globalText").addEventListener("input", updateGlobalCount);
    $("profileText").addEventListener("input", updateProfileCount);
    $("learnerForm").addEventListener("submit", loadLearner);
    $("helpForm").addEventListener("submit", addHelpContent);
    $("setSave").addEventListener("click", saveSettings);
    $("stPromptSave").addEventListener("click", saveSelfTestPrompt);
    $("buildForm").addEventListener("submit", downloadBuild);
    $("previewPrompt").addEventListener("click", () => run(previewPrompt));
    $("profileCancel").addEventListener("click", () => {
      editingStudent = null;
      show("profileForm", false);
    });
    document.querySelectorAll(".admin-tabs .tab").forEach((t) =>
      t.addEventListener("click", () => openTab(t.dataset.tab)));

    // If the admin cookie is still valid, go straight to the console.
    try {
      await Z.request("GET", `${API}/consults`);
      enterConsole();
    } catch (_) {
      show("adminLogin", true);
    }
  });
})();
