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
    adults: loadAdults,
    payments: loadPayments,
    plans: loadPlans,
    students: loadStudents,
    global: loadGlobalPrompt,
  };

  function openTab(name) {
    document.querySelectorAll(".admin-tabs .tab").forEach((t) => t.classList.toggle("is-active", t.dataset.tab === name));
    ["consults", "adults", "payments", "plans", "students", "global"].forEach((n) => show(`tab-${n}`, n === name));
    return run(loaders[name]);
  }

  // ----- Consultation requests -----

  async function loadConsults() {
    const rows = await Z.request("GET", `${API}/consults`);
    fill($("consultTable"), ["زمان", "نام", "شماره", "زمان ترجیحی", "پیام", "وضعیت", "عملیات"],
      rows.map((r) => [
        Z.fmtDateTime(r.created_at),
        r.name,
        r.phone,
        r.preferred_time,
        r.message,
        r.status,
        actions(
          button("تماس گرفته شد", () => setConsultStatus(r.id, "contacted")),
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

  // ----- Sign-ups -----

  async function loadAdults() {
    const rows = await Z.request("GET", `${API}/adults`);
    // Plans are extended only when a payment is confirmed in the payments tab, never by hand here.
    fill($("adultTable"), ["ثبت‌نام", "نام", "شماره", "هدف", "پلن تا"],
      rows.map((a) => [
        Z.fmtDate(a.created_at),
        a.name,
        a.phone,
        a.goal,
        a.plan_expires_at ? Z.fmtDate(a.plan_expires_at) : "بدون پلن",
      ]));
  }

  // ----- Payments -----

  async function loadPayments() {
    const rows = await Z.request("GET", `${API}/payments?status=pending`);
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

  async function loadPlans() {
    const rows = await Z.request("GET", `${API}/plans`);
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
    show("profileForm", true);
    $("profileInterests").focus();
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
    openTab("consults");
  }

  async function signOut() {
    await Z.request("POST", `${API}/logout`).catch(() => {});
    location.reload();
  }

  document.addEventListener("DOMContentLoaded", async () => {
    Z.initLang();
    $("adminLoginForm").addEventListener("submit", signIn);
    $("adminLogout").addEventListener("click", signOut);
    $("planForm").addEventListener("submit", addPlan);
    $("profileForm").addEventListener("submit", saveProfile);
    $("globalForm").addEventListener("submit", saveGlobalPrompt);
    $("globalText").addEventListener("input", updateGlobalCount);
    $("profileText").addEventListener("input", updateProfileCount);
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
