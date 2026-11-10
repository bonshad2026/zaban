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
    consults: () => loadRequests("consult"),
    cooperations: () => loadRequests("cooperation"),
    overview: loadOverview,
    helpcontent: loadHelpSection,
    settings: loadSettings,
    connections: loadSms,
    payment: loadPayment,
    sessions: loadSessions,
    promptgen: loadPromptGen,
    promptview: loadPromptView,
    selftest: loadSelfTest,
    placementbank: loadBank,
    adults: loadAdults,
    payments: loadPayments,
    plans: loadPlans,
    global: loadGlobalPrompt,
    voices: loadVoices,
    curriculum: loadCurriculum,
    programs: loadPrograms,
  };

  function openTab(name) {
    document.querySelectorAll(".admin-tabs .tab").forEach((t) => t.classList.toggle("is-active", t.dataset.tab === name));
    ["overview", "consults", "cooperations", "helpcontent", "settings", "connections", "payment", "sessions", "promptgen", "promptview", "selftest", "placementbank", "adults", "payments", "plans", "curriculum", "programs", "global", "voices"]
      .forEach((n) => show(`tab-${n}`, n === name));
    return run(loaders[name]);
  }

  // ----- Consultation and cooperation requests -----

  // Each kind lists its statuses in the order the team works through them. The status is chosen, not clicked.
  const REQUEST_KINDS = {
    consult: {
      path: "consults",
      table: "consultTable",
      filter: "consultFilter",
      title: "درخواست مشاوره",
      statuses: [
        ["new", "جدید"],
        ["reviewed", "بررسی شد"],
        ["called", "تماس گرفته شد"],
        ["recall", "تماس مجدد"],
        ["awaiting_reply", "منتظر پاسخ"],
        ["closed", "بسته شد"],
      ],
      headers: ["زمان", "نام", "موضوع", "شماره", "پیام", "وضعیت", "عملیات"],
      list: (r) => [Z.fmtDateTime(r.created_at), fullName(r), r.subject, r.phone, r.message],
      details: (r) => [
        ["زمان ثبت", Z.fmtDateTime(r.created_at)],
        ["نام", fullName(r)],
        ["موضوع", r.subject || "—"],
        ["شماره", r.phone],
        ["اجازه‌ی تماس", r.contact_permission ? "بله" : "نه"],
        ["زمان ترجیحی", r.preferred_time || "—"],
      ],
    },
    cooperation: {
      path: "cooperations",
      table: "cooperationTable",
      filter: "cooperationFilter",
      title: "درخواست همکاری",
      statuses: [
        ["new", "جدید"],
        ["contacted", "تماس گرفته شد"],
        ["closed", "بسته شد"],
      ],
      headers: ["زمان", "موضوع", "شماره", "ایمیل", "پیام", "وضعیت", "عملیات"],
      list: (r) => [Z.fmtDateTime(r.created_at), r.subject, r.phone, r.email, r.message],
      details: (r) => [
        ["زمان ثبت", Z.fmtDateTime(r.created_at)],
        ["موضوع", r.subject],
        ["شماره", r.phone],
        ["ایمیل", r.email || "—"],
      ],
    },
  };

  // Rows as the server last returned them. A status change updates the row here too, so the list and the dialog agree.
  const requestRows = { consult: [], cooperation: [] };

  // Status labels for a status that is no longer in the list (for example «contacted» on old consultation requests).
  const LEGACY_STATUS = { contacted: "تماس گرفته شد" };

  function fullName(r) {
    return `${r.name} ${r.last_name || ""}`.trim();
  }

  function option(value, label) {
    const o = Z.el("option", "", label);
    o.value = value;
    return o;
  }

  function statusLabel(cfg, status) {
    const hit = cfg.statuses.find(([value]) => value === status);
    return hit ? hit[1] : LEGACY_STATUS[status] || status;
  }

  function statusClass(status) {
    if (status === "new") return "is-new";
    if (status === "closed") return "is-closed";
    return "";
  }

  // A long text is cut in the list. The full text shows on hover and in the details dialog.
  function textCell(value, max = 50) {
    const text = value == null || value === "" ? "—" : String(value);
    if (text.length <= max) return text;
    const clip = Z.el("span", "clip", `${text.slice(0, max)}…`);
    clip.title = text;
    return clip;
  }

  // The status is picked from a list, and «اعمال» saves it. «اعمال» stays off until the choice differs from the saved status.
  function statusControl(kind, row, errorId, onSaved) {
    const cfg = REQUEST_KINDS[kind];
    const select = Z.el("select", "");
    select.setAttribute("aria-label", "وضعیت");
    cfg.statuses.forEach(([value, label]) => select.appendChild(option(value, label)));
    if (!cfg.statuses.some(([value]) => value === row.status)) select.appendChild(option(row.status, statusLabel(cfg, row.status)));
    select.value = row.status;
    const apply = Z.el("button", "", "اعمال");
    apply.type = "button";
    apply.disabled = true;
    select.addEventListener("change", () => { apply.disabled = select.value === row.status; });
    apply.addEventListener("click", async () => {
      apply.disabled = true;
      setError(errorId, "");
      try {
        await Z.request("POST", `${API}/${cfg.path}/${row.id}/status`, { status: select.value });
        row.status = select.value;
        renderRequests(kind);
        if (onSaved) onSaved();
      } catch (err) {
        setError(errorId, err.message);
        apply.disabled = select.value === row.status;
      }
    });
    const box = Z.el("div", "status-control");
    box.append(select, apply);
    return box;
  }

  async function loadRequests(kind) {
    requestRows[kind] = await Z.request("GET", `${API}/${REQUEST_KINDS[kind].path}`);
    renderRequests(kind);
  }

  function renderRequests(kind) {
    const cfg = REQUEST_KINDS[kind];
    const filter = $(cfg.filter).value;
    const rows = requestRows[kind].filter((r) => !filter || r.status === filter);
    fill($(cfg.table), cfg.headers,
      rows.map((r) => [
        ...cfg.list(r).map((value) => textCell(value)),
        statusControl(kind, r, "adminError"),
        actions(button("مشاهده", () => showRequest(kind, r.id))),
      ]));
  }

  function fillRequestFilter(kind) {
    const cfg = REQUEST_KINDS[kind];
    $(cfg.filter).replaceChildren(option("", "همه"), ...cfg.statuses.map(([value, label]) => option(value, label)));
    $(cfg.filter).addEventListener("change", () => renderRequests(kind));
  }

  // The details dialog shows every field, the full message and the status control.
  function showRequest(kind, id) {
    const cfg = REQUEST_KINDS[kind];
    const row = requestRows[kind].find((r) => r.id === id);
    if (!row) return;
    $("requestTitle").textContent = cfg.title;
    $("requestDetails").replaceChildren(...cfg.details(row).flatMap(([label, value]) => [Z.el("dt", "", label), Z.el("dd", "", value)]));
    $("requestMessage").textContent = row.message || "—";
    showRequestStatus(kind, row);
    setError("requestError", "");
    $("requestDialog").showModal();
  }

  function showRequestStatus(kind, row) {
    const cfg = REQUEST_KINDS[kind];
    const badge = $("requestCurrent");
    badge.textContent = statusLabel(cfg, row.status);
    badge.className = `status-badge ${statusClass(row.status)}`;
    $("requestStatusSlot").replaceChildren(statusControl(kind, row, "requestError", () => showRequestStatus(kind, row)));
  }

  function closeRequestDialog() {
    $("requestDialog").close();
  }

  // ----- Overview, learner detail, help content and settings -----

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

  // ----- Help content tags: facets (groups) and their tags, defined by the administrator -----

  let helpFacets = [];

  async function loadFacets() {
    helpFacets = await Z.request("GET", `${API}/help-facets`);
    renderFacets();
    renderTagPicker($("hcTags"), []);
  }

  // Checkboxes for every tag, grouped by facet. Returns nothing; the picked ids are read with pickedTags.
  function renderTagPicker(picker, selected) {
    const chosen = new Set(selected);
    if (!helpFacets.length) {
      picker.replaceChildren(Z.el("p", "muted", "هنوز برچسبی تعریف نشده است."));
      return;
    }
    picker.replaceChildren(...helpFacets.map((facet) => {
      const group = Z.el("div", "tag-group");
      group.appendChild(Z.el("strong", "", facet.name));
      facet.tags.forEach((tag) => {
        const choice = Z.el("label", "tag-choice");
        const check = document.createElement("input");
        check.type = "checkbox";
        check.value = tag.id;
        check.checked = chosen.has(tag.id);
        choice.append(check, ` ${tag.label}`);
        group.appendChild(choice);
      });
      return group;
    }));
  }

  function pickedTags(picker) {
    return [...picker.querySelectorAll("input[type=checkbox]:checked")].map((check) => check.value);
  }

  function renderFacets() {
    const list = $("facetList");
    if (!helpFacets.length) {
      list.replaceChildren(Z.el("p", "muted", "موردی وجود ندارد."));
      return;
    }
    list.replaceChildren(...helpFacets.map(facetCard));
  }

  function facetCard(facet) {
    const card = Z.el("div", "card facet-card");
    const head = Z.el("div", "row");
    head.append(Z.el("strong", "", facet.name), button("حذف گروه", () => removeFacet(facet)));
    const chips = Z.el("div", "tag-chips");
    facet.tags.forEach((tag) => {
      const chip = Z.el("span", "tag-chip", tag.label);
      chip.appendChild(button("×", () => removeTag(tag)));
      chips.appendChild(chip);
    });
    const form = document.createElement("form");
    form.className = "row";
    const input = document.createElement("input");
    input.placeholder = "برچسب تازه";
    input.maxLength = 60;
    input.required = true;
    const add = Z.el("button", "", "افزودن برچسب");
    add.type = "submit";
    form.append(input, add);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      addTag(facet.id, input.value.trim());
    });
    card.append(head, chips, form);
    return card;
  }

  function addFacet(event) {
    event.preventDefault();
    return run(async () => {
      await Z.request("POST", `${API}/help-facets`, { name: $("facetName").value.trim() });
      event.target.reset();
      await loadFacets();
    });
  }

  function removeFacet(facet) {
    return run(async () => {
      if (!confirm(`گروه «${facet.name}» و همه‌ی برچسب‌هایش حذف شود؟ این کار روی محتواها هم اثر می‌گذارد.`)) return;
      await Z.request("DELETE", `${API}/help-facets/${facet.id}`);
      await loadFacets();
      await loadHelpContent();
    });
  }

  function addTag(facetId, label) {
    return run(async () => {
      await Z.request("POST", `${API}/help-facets/${facetId}/tags`, { label });
      await loadFacets();
    });
  }

  function removeTag(tag) {
    return run(async () => {
      if (!confirm(`برچسب «${tag.label}» از همه‌ی محتواها برداشته و حذف شود؟`)) return;
      await Z.request("DELETE", `${API}/help-tags/${tag.id}`);
      await loadFacets();
      await loadHelpContent();
    });
  }

  // ----- Help content list and edit -----

  async function loadHelpSection() {
    await loadFacets();
    await loadHelpContent();
  }

  async function loadHelpContent() {
    const rows = await Z.request("GET", `${API}/help-content`);
    fill($("helpTable"), ["عنوان", "دسته", "گروه سنی", "سطح", "جنسیت", "برچسب‌ها", "منبع", "عملیات"],
      rows.map((r) => [
        textCell(r.title, 60),
        r.category,
        r.age_band,
        r.level,
        r.gender === "female" ? "دختر" : r.gender === "male" ? "پسر" : "برای همه",
        textCell(r.tags.map((t) => t.label).join("، ") || "—", 40),
        r.url ? textCell(r.url, 40) : `فایل (${Math.round(r.size_bytes / 1024)} کیلوبایت)`,
        actions(
          button("ویرایش", () => editHelpContent(r)),
          button("حذف", () => deleteHelpContent(r.id)),
        ),
      ]));
  }

  let editingHelpId = null;

  function editHelpContent(row) {
    editingHelpId = row.id;
    $("helpEditName").textContent = row.title;
    $("hbBand").value = row.age_band;
    $("hbLevel").value = row.level;
    $("hbGender").value = row.gender || "";
    renderTagPicker($("hbTags"), row.tags.map((t) => t.id));
    Z.showError($("helpEditError"), "");
    $("helpEditDialog").showModal();
  }

  async function saveHelpClassification(event) {
    event.preventDefault();
    Z.showError($("helpEditError"), "");
    try {
      await Z.request("PUT", `${API}/help-content/${editingHelpId}/classification`, {
        age_band: $("hbBand").value,
        level: $("hbLevel").value,
        gender: $("hbGender").value || null,
        tag_ids: pickedTags($("hbTags")),
      });
      $("helpEditDialog").close();
      await loadHelpContent();
    } catch (err) {
      Z.showError($("helpEditError"), err.message);
    }
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
      tag_ids: pickedTags($("hcTags")),
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
    // Only the AI key belongs to the prompt settings. The SMS and payment keys are shown in their own sections.
    $("secretsList").replaceChildren(
      ...Object.entries(data.secrets)
        .filter(([k]) => k.startsWith("anthropic"))
        .map(([k, v]) => Z.el("li", "", `${k}: ${v === true ? "تنظیم شده" : "تنظیم نشده"}`)),
    );
  }

  function saveSettings() {
    return run(async () => {
      await Z.request("POST", `${API}/settings`, {
        prompt_mode: $("setMode").value,
        expected_output: $("setExpected").value,
      });
      $("settingsNotice").hidden = false;
      $("settingsNotice").textContent = "تنظیمات ذخیره شد.";
    });
  }

  // ----- Self-test prompt: template, rules and a preview for one learner -----

  let stDefaultTemplate = "";

  async function loadSelfTest() {
    const data = await Z.request("GET", `${API}/self-test/template`);
    stDefaultTemplate = data.default_template;
    $("stTemplate").value = data.template;
    $("stPlaceholders").replaceChildren(
      ...data.placeholders.map((p) => Z.el("li", "", `{{${p.key}}}  ${p.label}`)),
    );
    renderSelfTestRules(data.rules);
    const students = await Z.request("GET", `${API}/students`);
    $("stLearner").replaceChildren(
      ...students.map((s) => {
        const option = Z.el("option", "", `${s.name || "—"}${s.kind === "self" ? " (یادگیری خود)" : ""}`);
        option.value = s.id;
        return option;
      }),
    );
  }

  function saveSelfTestTemplate(text) {
    return run(async () => {
      await Z.request("POST", `${API}/self-test/template`, { template: text });
      Z.show($("stNotice"), true);
      $("stNotice").textContent = "قالب پرامپت آزمون ذخیره شد.";
    });
  }

  function renderSelfTestRules(rules) {
    const box = $("stRules");
    if (!rules.length) {
      box.replaceChildren(Z.el("p", "muted", "هنوز قاعده‌ای ثبت نشده است."));
      return;
    }
    box.replaceChildren(...rules.map((rule) => {
      const card = Z.el("div", "card facet-card");
      const title = Z.el("strong", "", `{{rule.${rule.key}}}`);
      const hint = Z.el("span", "muted", rule.default ? "  (قاعده‌ی پیش‌فرض)" : "  (قاعده‌ی تازه)");
      const text = document.createElement("textarea");
      text.rows = 3;
      text.maxLength = 1500;
      text.value = rule.text;
      const save = button("ذخیره", () => saveSelfTestRule(rule.key, text.value));
      const reset = button(rule.default ? "برگشت به پیش‌فرض" : "حذف", () => removeSelfTestRule(rule));
      card.append(title, hint, text, actions(save, reset));
      return card;
    }));
  }

  function saveSelfTestRule(key, text) {
    return run(async () => {
      await Z.request("POST", `${API}/self-test/rules`, { key, text });
      await loadSelfTest();
    });
  }

  function removeSelfTestRule(rule) {
    return run(async () => {
      const question = rule.default ? `قاعده‌ی ${rule.key} به پیش‌فرض برگردد؟` : `قاعده‌ی ${rule.key} حذف شود؟`;
      if (!confirm(question)) return;
      await Z.request("DELETE", `${API}/self-test/rules/${encodeURIComponent(rule.key)}`);
      await loadSelfTest();
    });
  }

  async function addSelfTestRule(event) {
    event.preventDefault();
    await run(async () => {
      await Z.request("POST", `${API}/self-test/rules`, { key: $("stRuleKey").value.trim(), text: $("stRuleText").value.trim() });
      event.target.reset();
      await loadSelfTest();
    });
  }

  async function previewSelfTest(event) {
    event.preventDefault();
    Z.showError($("stError"), "");
    Z.show($("stUnknown"), false);
    try {
      const result = await Z.request("POST", `${API}/self-test/preview`, {
        student_id: $("stLearner").value,
        kind: $("stKind").value,
        skill: $("stSkill").value,
        minutes: Number($("stMinutes").value),
      });
      $("stOutput").value = result.prompt;
      if (result.unknown_placeholders.length) {
        $("stUnknown").hidden = false;
        $("stUnknown").textContent = `این کلیدها در سامانه نیستند و خالی ماندند: ${result.unknown_placeholders.join("، ")}`;
      }
    } catch (err) {
      Z.showError($("stError"), err.message);
    }
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

  // ----- Plans: the list shows the plans; adding and editing happen in a dialog -----

  let editingPlanId = null;

  const ICON_EDIT = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h4L19 9l-4-4L4 16v4z"/><path d="M13.5 6.5l4 4"/></svg>';
  const ICON_TRASH = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16"/><path d="M9 7V4h6v3"/><path d="M6.5 7l1 13h9l1-13"/><path d="M10 11v5M14 11v5"/></svg>';

  function iconButton(icon, label, onClick, danger = false) {
    const b = Z.el("button", danger ? "icon-btn danger" : "icon-btn ghost");
    b.type = "button";
    b.title = label;
    b.setAttribute("aria-label", label);
    b.insertAdjacentHTML("beforeend", icon);
    b.addEventListener("click", onClick);
    return b;
  }

  async function loadPlans() {
    const rows = await Z.request("GET", `${API}/plans`);
    fill($("planTable"), ["پلن", "قیمت (تومان)", "مدت (روز)", "سقف توکن", "وضعیت", "عملیات"],
      rows.map((p) => {
        const status = Z.el("span", `status-badge ${p.active ? "" : "is-off"}`, p.active ? "فعال" : "غیرفعال");
        const toggle = button(p.active ? "غیرفعال کردن" : "فعال کردن", () => setPlanActive(p.id, !p.active));
        return [
          p.name,
          p.price_toman.toLocaleString("fa-IR"),
          p.days,
          p.token_allowance.toLocaleString("fa-IR"),
          status,
          actions(
            toggle,
            iconButton(ICON_EDIT, "ویرایش پلن", () => openPlanDialog(p)),
            iconButton(ICON_TRASH, "حذف پلن", () => removePlan(p), true),
          ),
        ];
      }));
  }

  function setPlanActive(id, active) {
    return run(async () => {
      await Z.request("POST", `${API}/plans/${id}/active`, { active });
      await loadPlans();
    });
  }

  function removePlan(plan) {
    return run(async () => {
      if (!confirm(`پلن «${plan.name}» حذف شود؟ اگر پرداختی با آن ثبت شده باشد، حذف نمی‌شود.`)) return;
      await Z.request("DELETE", `${API}/plans/${plan.id}`);
      $("planNotice").hidden = false;
      $("planNotice").textContent = "پلن حذف شد.";
      await loadPlans();
    });
  }

  // One dialog for adding and editing. editingPlanId is null when adding.
  function openPlanDialog(plan) {
    editingPlanId = plan ? plan.id : null;
    $("planDialogTitle").textContent = plan ? "ویرایش پلن" : "افزودن پلن";
    $("planName").value = plan ? plan.name : "";
    $("planNameEn").value = plan ? plan.name_en || "" : "";
    $("planPrice").value = plan ? plan.price_toman : "";
    $("planDays").value = plan ? plan.days : "";
    $("planTokens").value = plan ? plan.token_allowance : 1000000;
    $("planDescription").value = plan ? plan.description || "" : "";
    Z.showError($("planFormError"), "");
    $("planDialog").showModal();
  }

  async function savePlan(event) {
    event.preventDefault();
    Z.showError($("planFormError"), "");
    const body = {
      name: $("planName").value.trim(),
      name_en: $("planNameEn").value.trim(),
      price_toman: Number($("planPrice").value),
      days: Number($("planDays").value),
      token_allowance: Number($("planTokens").value),
      description: $("planDescription").value.trim(),
    };
    try {
      if (editingPlanId) await Z.request("POST", `${API}/plans/${editingPlanId}/update`, body);
      else await Z.request("POST", `${API}/plans`, body);
      $("planDialog").close();
      $("planNotice").hidden = false;
      $("planNotice").textContent = editingPlanId ? "پلن ذخیره شد." : "پلن اضافه شد.";
      await loadPlans();
    } catch (err) {
      Z.showError($("planFormError"), err.message);
    }
  }

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

  // ----- Curriculum: topic, conversation goal and the points to talk about -----

  // Used by the programs tab as well: keeps the current choice when it still exists.
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

  let curTopics = [];
  let curOpenId = null;

  function renderTopicTable() {
    fill($("topicTable"), ["شناسه", "موضوع", "هدف گفتگو", "موارد آموزشی", "عملیات"],
      curTopics.map((t) => [
        t.id,
        t.title,
        textCell(t.goal, 60),
        String(t.points.length),
        actions(button("مشاهده", () => openTopic(t.id))),
      ]));
  }

  async function loadCurriculum() {
    curTopics = await Z.request("GET", `${API}/curriculum/topics`);
    renderTopicTable();
  }

  function renderPoints(topic) {
    const list = $("curPoints");
    if (!topic.points.length) {
      list.replaceChildren(Z.el("li", "muted", "هنوز موردی ثبت نشده است."));
      return;
    }
    list.replaceChildren(...topic.points.map((point) => {
      const li = Z.el("li", "point-row");
      li.append(Z.el("span", "", point.text), button("حذف", () => removePoint(point)));
      return li;
    }));
  }

  // The dialog holds the full goal and every point, so the list stays short.
  function openTopic(id) {
    const topic = curTopics.find((t) => t.id === id);
    if (!topic) return;
    curOpenId = id;
    $("curDialogTitle").textContent = `${topic.title} (${topic.id})`;
    $("curTitle").value = topic.title;
    $("curGoal").value = topic.goal;
    Z.showError($("curFormError"), "");
    renderPoints(topic);
    $("curDialog").showModal();
  }

  async function saveTopic(event) {
    event.preventDefault();
    Z.showError($("curFormError"), "");
    try {
      await Z.request("PUT", `${API}/curriculum/topics/${curOpenId}`, {
        title: $("curTitle").value.trim(),
        goal: $("curGoal").value.trim(),
      });
      await loadCurriculum();
      openTopic(curOpenId);
    } catch (err) {
      Z.showError($("curFormError"), err.message);
    }
  }

  async function addPoint(event) {
    event.preventDefault();
    await run(async () => {
      await Z.request("POST", `${API}/curriculum/topics/${curOpenId}/points`, { text: $("curPointText").value.trim() });
      $("curPointForm").reset();
      await loadCurriculum();
      openTopic(curOpenId);
    });
  }

  function removePoint(point) {
    return run(async () => {
      if (!confirm(`«${point.text}» حذف شود؟`)) return;
      await Z.request("DELETE", `${API}/curriculum/points/${point.id}`);
      await loadCurriculum();
      openTopic(curOpenId);
    });
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
    if (program) enableLessonDrag(program);
  }

  // Dragging a lesson row to another place saves the new order. The rows are in the same order as program.items.
  function enableLessonDrag(program) {
    let from = null;
    [...$("progItemsTable").querySelectorAll("tr")].slice(1).forEach((row, index) => {
      row.draggable = true;
      row.classList.add("drag-row");
      row.addEventListener("dragstart", (event) => {
        from = index;
        event.dataTransfer.effectAllowed = "move";
        event.dataTransfer.setData("text/plain", String(index));
      });
      row.addEventListener("dragover", (event) => event.preventDefault());
      row.addEventListener("drop", (event) => {
        event.preventDefault();
        if (from === null || from === index) return;
        saveLessonOrder(program, from, index);
        from = null;
      });
    });
  }

  function saveLessonOrder(program, from, to) {
    const ids = program.items.map((item) => item.id);
    const [moved] = ids.splice(from, 1);
    ids.splice(to, 0, moved);
    return run(async () => {
      await Z.request("POST", `${API}/programs/${program.id}/order`, { item_ids: ids });
      await loadPrograms();
    });
  }

  // ----- Learner progress in the program: plays and averages, and a request to repeat one lesson -----

  async function loadLearnerProgress() {
    const studentId = $("progLearner").value;
    if (!studentId) return;
    try {
      const data = await Z.request("GET", `${API}/students/${studentId}/program-progress`);
      const pending = data.items.find((row) => row.item_id === data.revisit_item_id);
      Z.show($("progressNotice"), Boolean(pending));
      if (pending) $("progressNotice").textContent = `برای جلسه‌ی بعد درخواست گفتگوی مجدد دارد: ${pending.position + 1} — ${pending.title}`;
      fill($("progressTable"), ["جلسه", "عنوان", "دفعات", "میانگین امتیاز", "وضعیت", "عملیات"],
        data.items.map((row) => [
          row.position + 1,
          row.title,
          row.visits,
          row.average == null ? "—" : String(row.average),
          row.item_id === data.revisit_item_id ? "گفتگوی مجدد در جلسه‌ی بعد" : row.done ? "انجام شده" : "انجام نشده",
          actions(
            button("گفتگوی مجدد در جلسه‌ی بعد", () => requestRevisit(studentId, row.item_id)),
            ...(data.revisit_item_id === row.item_id ? [button("لغو", () => requestRevisit(studentId, null))] : []),
          ),
        ]));
    } catch (err) {
      setError("progError", err.message);
    }
  }

  function requestRevisit(studentId, itemId) {
    return run(async () => {
      await Z.request("POST", `${API}/students/${studentId}/revisit`, { item_id: itemId });
      await loadLearnerProgress();
    });
  }

  async function loadPrograms() {
    programs = await Z.request("GET", `${API}/programs`);
    const current = $("progSelect").value;
    fillSelect($("progSelect"), programs.programs.map((p) => [p.id, p.name]));
    if (current) $("progSelect").value = current;
    const learners = await Z.request("GET", `${API}/students`);
    const learner = $("progLearner").value;
    fillSelect($("progLearner"), learners.map((l) => [l.id, `${l.name || "—"}${l.kind === "self" ? " (یادگیری خود)" : ""}`]));
    if (learner) $("progLearner").value = learner;
    await loadLearnerProgress();
    renderProgramItems();
    if (programs.programs.length) showProgramItem(1);
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
    const everywhere = Z.el("button", "account-item danger", "خروج از همه‌ی دستگاه‌ها");
    everywhere.type = "button";
    everywhere.setAttribute("role", "menuitem");
    everywhere.addEventListener("click", signOutEverywhere);
    item.setAttribute("role", "menuitem");
    item.addEventListener("click", signOut);
    list.append(item, everywhere);
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
    // Every group starts folded. The administrator opens the group they need, and it folds again on its title.
    tabs.querySelectorAll(".admin-group").forEach((group) => {
      group.classList.add("is-closed");
      group.querySelector(".admin-group-title").setAttribute("aria-expanded", "false");
    });
    tabs.querySelectorAll(".admin-group-title").forEach((title) => {
      title.addEventListener("click", () => {
        const group = title.parentElement;
        const closed = group.classList.toggle("is-closed");
        title.setAttribute("aria-expanded", String(!closed));
      });
    });
  }

  // Tabs are only visible when their group is open, so choosing a tab never needs to open a group.

  // ----- Prompt generator -----

  // «ساختار پرامپت»: the template only.
  async function loadPromptGen() {
    const data = await Z.request("GET", `${API}/prompt-template`);
    $("genTemplate").value = data.template;
    $("genPlaceholders").replaceChildren(
      ...data.placeholders.map((p) => Z.el("li", "", `{{${p.key}}}  ${p.label}`)),
    );
  }

  // «مشاهده پرامپت»: pick a learner and see the finished prompt for them.
  async function loadPromptView() {
    const students = await Z.request("GET", `${API}/students`);
    $("genLearner").replaceChildren(
      ...students.map((s) => {
        const option = Z.el("option", "", `${s.name || "—"}${s.kind === "self" ? " (یادگیری خود)" : ""}`);
        option.value = s.id;
        return option;
      }),
    );
    if (students.length) return generatePrompt();
    $("genOutput").value = "";
    return null;
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

  // The SMS and payment sections read the same endpoint, but each one saves only its own fields.
  async function loadConnections() {
    return Z.request("GET", `${API}/connections`);
  }

  async function loadSms() {
    const data = await loadConnections();
    $("connSmsProvider").value = data.sms_provider;
    $("connSmsKeyHint").textContent = data.sms_api_key_set ? `کلید فعلی: ${data.sms_api_key_masked}` : "کلیدی ثبت نشده است.";
    $("connSmsTemplate").value = data.sms_otp_template || "";
    $("connSmsKey").value = "";
  }

  async function loadPayment() {
    const data = await loadConnections();
    $("connPayProvider").value = data.payment_provider;
    $("connMerchantHint").textContent = data.zarinpal_merchant_set ? `کد فعلی: ${data.zarinpal_merchant_masked}` : "کدی ثبت نشده است.";
    $("connCallback").textContent = data.callback_url;
    $("connMerchant").value = "";
  }

  function saveSms() {
    return run(async () => {
      const body = {
        sms_provider: $("connSmsProvider").value,
        sms_otp_template: $("connSmsTemplate").value,
      };
      if ($("connSmsKey").value.trim()) body.sms_api_key = $("connSmsKey").value.trim();
      await Z.request("POST", `${API}/connections`, body);
      $("smsNotice").hidden = false;
      $("smsNotice").textContent = "تنظیمات پیامک ذخیره شد.";
      await loadSms();
    });
  }

  function savePayment() {
    return run(async () => {
      const body = { payment_provider: $("connPayProvider").value };
      if ($("connMerchant").value.trim()) body.zarinpal_merchant_id = $("connMerchant").value.trim();
      await Z.request("POST", `${API}/connections`, body);
      $("payNotice").hidden = false;
      $("payNotice").textContent = "درگاه پرداخت ذخیره شد.";
      await loadPayment();
    });
  }

  async function signOut() {
    await Z.request("POST", `${API}/logout`).catch(() => {});
    location.reload();
  }

  async function signOutEverywhere() {
    if (!confirm("از همه‌ی دستگاه‌ها خارج شوید؟ همین دستگاه هم خارج می‌شود.")) return;
    await Z.request("POST", `${API}/logout-all`).catch(() => {});
    location.reload();
  }

  document.addEventListener("DOMContentLoaded", async () => {
    Z.initLang();
    window.AdminI18n.refresh();
    fillRequestFilter("consult");
    fillRequestFilter("cooperation");
    $("requestClose").addEventListener("click", closeRequestDialog);
    $("adminLoginForm").addEventListener("submit", signIn);
    $("smsSave").addEventListener("click", saveSms);
    $("paySave").addEventListener("click", savePayment);
    $("planForm").addEventListener("submit", savePlan);
    $("planAddOpen").addEventListener("click", () => openPlanDialog(null));
    $("planClose").addEventListener("click", () => $("planDialog").close());
    $("bankForm").addEventListener("submit", saveBank);
    $("bankReset").addEventListener("click", resetBank);
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
    $("genLearner").addEventListener("change", () => run(generatePrompt));
    $("genCopy").addEventListener("click", () => navigator.clipboard.writeText($("genOutput").value));
    $("globalForm").addEventListener("submit", saveGlobalPrompt);
    $("voiceForm").addEventListener("submit", addVoice);
    $("progItemForm").addEventListener("submit", saveProgramItem);
    $("progDurationForm").addEventListener("submit", saveProgramDuration);
    $("progSelect").addEventListener("change", () => { renderProgramItems(); showProgramItem(1); });
    $("progLearner").addEventListener("change", loadLearnerProgress);
    $("globalText").addEventListener("input", updateGlobalCount);
    $("learnerForm").addEventListener("submit", loadLearner);
    $("helpForm").addEventListener("submit", addHelpContent);
    $("curForm").addEventListener("submit", saveTopic);
    $("curPointForm").addEventListener("submit", addPoint);
    $("curClose").addEventListener("click", () => $("curDialog").close());
    $("facetForm").addEventListener("submit", addFacet);
    $("helpEditForm").addEventListener("submit", saveHelpClassification);
    $("helpEditClose").addEventListener("click", () => $("helpEditDialog").close());
    $("setSave").addEventListener("click", saveSettings);
    $("stTemplateSave").addEventListener("click", () => saveSelfTestTemplate($("stTemplate").value));
    $("stTemplateReset").addEventListener("click", async () => {
      if (!confirm("قالب به پیش‌فرض برگردد؟")) return;
      $("stTemplate").value = stDefaultTemplate;
      await saveSelfTestTemplate(stDefaultTemplate);
    });
    $("stRuleForm").addEventListener("submit", addSelfTestRule);
    $("stPreviewForm").addEventListener("submit", previewSelfTest);
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
