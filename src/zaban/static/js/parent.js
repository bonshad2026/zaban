(() => {
  const $ = (id) => document.getElementById(id);

  function showView(name) {
    Z.show($("loginView"), name === "login");
    Z.show($("appView"), name === "app");
  }

  // A paid adult goes straight to learning. Without a plan this page shows the plan and its purchase.
  async function enterApp() {
    showPaymentNotice();
    const status = await loadBilling();
    if (status.has_active_plan) {
      location.replace("/student");
      return;
    }
    showView("app");
  }

  function showPaymentNotice() {
    const result = new URLSearchParams(location.search).get("payment");
    if (!result) return;
    $("paymentNotice").textContent = result === "paid"
      ? "پرداخت شما ثبت شد. بعد از تأیید پشتیبانی، پلن شما فعال می‌شود."
      : "پرداخت انجام نشد. دوباره تلاش کنید.";
    Z.show($("paymentNotice"), true);
    history.replaceState(null, "", location.pathname);
  }

  async function loadBilling() {
    const [plans, status] = await Promise.all([
      Z.request("GET", "/v1/web/billing/plans"),
      Z.request("GET", "/v1/web/billing/status"),
    ]);
    $("planStatus").textContent = status.has_active_plan
      ? `پلن شما فعال است تا ${Z.fmtDate(status.plan_expires_at)}.`
      : "برای استفاده از گفتاریار، ابتدا یک پلن را انتخاب و پرداخت کنید.";
    const list = $("planList");
    list.innerHTML = "";
    for (const plan of plans) {
      const card = Z.el("div", "stat");
      card.appendChild(Z.el("strong", null, plan.name));
      card.appendChild(Z.el("span", "muted", `${plan.days} روز · ${plan.price_toman.toLocaleString("fa-IR")} تومان`));
      const pay = Z.el("button", null, "انتخاب و پرداخت");
      pay.type = "button";
      pay.addEventListener("click", () => choosePlan(plan.id));
      card.appendChild(pay);
      list.appendChild(card);
    }
    return status;
  }

  async function choosePlan(planId) {
    Z.showError($("billingError"), "");
    try {
      const paid = await Z.request("POST", "/v1/web/billing/checkout", { plan_id: planId });
      location.href = paid.redirect;
    } catch (err) {
      Z.showError($("billingError"), err.message);
    }
  }

  // ----- Sign-in with a mobile number and a password -----

  async function login(event) {
    event.preventDefault();
    const form = event.target;
    Z.showError($("loginError"), "");
    try {
      await Z.request("POST", "/v1/web/user/login", {
        phone: form.phone.value.trim(),
        password: form.password.value,
      });
      form.password.value = "";
      // After sign-in the visitor lands on the home page, with no menu item selected.
      location.href = "/";
    } catch (err) {
      Z.showError($("loginError"), err.message);
    }
  }

  // ----- Forgotten password: a one-time SMS code, then a new password -----

  function showReset(on) {
    Z.show($("loginForm"), !on);
    Z.show($("resetForm"), on);
    if (on) $("resetPhone").value = $("parentPhone").value.trim();
  }

  async function sendResetCode() {
    Z.showError($("resetError"), "");
    try {
      const sent = await Z.request("POST", "/v1/web/user/otp/request", { phone: $("resetPhone").value.trim(), purpose: "reset" });
      Z.show($("resetStep"), true);
      Z.showDevCode($("resetDevHint"), $("resetCode"), sent.dev_code);
      $("resetCode").focus();
    } catch (err) {
      Z.showError($("resetError"), err.message);
    }
  }

  async function saveNewPassword(event) {
    event.preventDefault();
    // Enter on the phone field sends the code first, before the new password is asked for.
    if ($("resetStep").hidden) return sendResetCode();
    const form = event.target;
    Z.showError($("resetError"), "");
    try {
      await Z.request("POST", "/v1/web/user/password/reset", {
        phone: form.phone.value.trim(),
        code: form.code.value.trim(),
        password: form.password.value,
      });
      form.code.value = "";
      form.password.value = "";
      Z.show($("resetStep"), false);
      Z.show($("resetOk"), true);
      $("resetOk").textContent = "رمز عبور تازه ذخیره شد. حالا با رمز جدید وارد شوید.";
    } catch (err) {
      Z.showError($("resetError"), err.message);
    }
  }

  async function boot() {
    Z.initLang();
    $("loginForm").addEventListener("submit", login);
    $("forgotLink").addEventListener("click", (event) => { event.preventDefault(); showReset(true); });
    $("backToLogin").addEventListener("click", (event) => { event.preventDefault(); showReset(false); });
    $("resetSendBtn").addEventListener("click", sendResetCode);
    $("resetForm").addEventListener("submit", saveNewPassword);

    let me = null;
    try {
      me = await Z.request("GET", "/v1/web/me?role=parent");
    } catch (_) {
      me = null;
    }
    if (me && me.role === "parent") {
      await enterApp();
    } else {
      showView("login");
    }
  }

  Z.pageRole.value = "parent";
  document.addEventListener("DOMContentLoaded", boot);
})();
