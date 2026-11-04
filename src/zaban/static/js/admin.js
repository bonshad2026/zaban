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
  };

  function openTab(name) {
    document.querySelectorAll(".admin-tabs .tab").forEach((t) => t.classList.toggle("is-active", t.dataset.tab === name));
    ["consults", "adults", "payments", "plans"].forEach((n) => show(`tab-${n}`, n === name));
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
    fill($("adultTable"), ["ثبت‌نام", "نام", "شماره", "هدف", "پلن تا", "عملیات"],
      rows.map((a) => [
        Z.fmtDate(a.created_at),
        a.name,
        a.phone,
        a.goal,
        a.plan_expires_at ? Z.fmtDate(a.plan_expires_at) : "بدون پلن",
        actions(
          button("۳۰ روز اعتبار", () => grantDays(a.id, 30)),
          button("۹۰ روز اعتبار", () => grantDays(a.id, 90)),
        ),
      ]));
  }

  function grantDays(id, days) {
    return run(async () => {
      await Z.request("POST", `${API}/adults/${id}/grant`, { days });
      await loadAdults();
    });
  }

  // ----- Payments -----

  async function loadPayments() {
    const rows = await Z.request("GET", `${API}/payments?status=pending`);
    fill($("paymentTable"), ["زمان", "نام", "شماره", "پلن", "مبلغ (تومان)", "درگاه", "عملیات"],
      rows.map((p) => [
        Z.fmtDateTime(p.created_at),
        p.adult,
        p.phone,
        p.plan,
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
