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

  // ----- Sign-in: with the password, or with a one-time code sent by SMS to the mobile -----

  let codeMode = false;
  const t = (fa, en) => (document.documentElement.lang === "en" ? en : fa);

  function setBilingual(node, fa, en) {
    node.dataset.fa = fa;
    node.dataset.en = en;
    node.textContent = t(fa, en);
  }

  function showLoginMode(useCode) {
    codeMode = useCode;
    Z.show($("passwordPart"), !useCode);
    Z.show($("codePart"), useCode);
    Z.showError($("loginError"), "");
    if (useCode) {
      setBilingual($("codeModeLink"), "ورود با رمز عبور", "Sign in with a password");
    } else {
      Z.show($("loginDevHint"), false);
      setBilingual($("codeModeLink"), "ورود با کد پیامکی", "Sign in with an SMS code");
    }
  }

  // After a code is sent, the send button is replaced by a countdown until a new code can be asked for.
  let stopLoginResendWait = () => {};

  async function sendLoginCode() {
    if ($("loginSendBtn").hidden) return;
    Z.showError($("loginError"), "");
    const phone = $("loginPhone").value.trim();
    if (!phone) {
      Z.showError($("loginError"), t("ابتدا شماره‌ی موبایل را وارد کنید.", "Enter your mobile number first."));
      $("loginPhone").focus();
      return;
    }
    try {
      const sent = await Z.request("POST", "/v1/web/user/otp/request", { phone, purpose: "login" });
      Z.showDevCode($("loginDevHint"), $("loginCode"), sent.dev_code);
      stopLoginResendWait();
      stopLoginResendWait = Z.startResendWait($("loginSendBtn"), $("loginResendWait"), "zaban.resend.login", sent.resend_in_seconds);
      $("loginCode").focus();
    } catch (err) {
      // The server still counts a code asked for a moment ago: show the same countdown instead of an error.
      if (err.status === 429 && err.retryAfter) {
        stopLoginResendWait();
        stopLoginResendWait = Z.startResendWait($("loginSendBtn"), $("loginResendWait"), "zaban.resend.login", err.retryAfter);
        return;
      }
      Z.showError($("loginError"), err.message);
    }
  }

  async function login(event) {
    event.preventDefault();
    const form = event.target;
    Z.showError($("loginError"), "");
    const phone = form.phone.value.trim();
    if (!phone) {
      Z.showError($("loginError"), t("شماره‌ی موبایل را وارد کنید.", "Enter your mobile number."));
      return;
    }
    if (codeMode) {
      const code = form.code.value.trim();
      if (!code) {
        Z.showError($("loginError"), t("کد پیامکی را وارد کنید.", "Enter the SMS code."));
        return;
      }
      try {
        await Z.request("POST", "/v1/web/user/otp/login", { phone, code });
        location.href = "/student";
      } catch (err) {
        Z.showError($("loginError"), err.message);
      }
      return;
    }
    if (!form.password.value) {
      Z.showError($("loginError"), t("رمز عبور را وارد کنید.", "Enter your password."));
      return;
    }
    try {
      await Z.request("POST", "/v1/web/user/login", {
        phone,
        password: form.password.value,
      });
      form.password.value = "";
      // After sign-in the visitor lands on the lesson page.
      location.href = "/student";
    } catch (err) {
      Z.showError($("loginError"), err.message);
    }
  }

  // ----- Forgotten password: a one-time SMS code, then a new password -----

  function showReset(on) {
    Z.show($("loginForm"), !on);
    Z.show($("resetForm"), on);
    if (on) $("resetPhone").value = $("loginPhone").value.trim();
  }

  let stopResetResendWait = () => {};

  async function sendResetCode() {
    if ($("resetSendBtn").hidden) return;
    Z.showError($("resetError"), "");
    try {
      const sent = await Z.request("POST", "/v1/web/user/otp/request", { phone: $("resetPhone").value.trim(), purpose: "reset" });
      Z.show($("resetStep"), true);
      Z.showDevCode($("resetDevHint"), $("resetCode"), sent.dev_code);
      stopResetResendWait();
      stopResetResendWait = Z.startResendWait($("resetSendBtn"), $("resetResendWait"), "zaban.resend.reset", sent.resend_in_seconds);
      $("resetCode").focus();
    } catch (err) {
      if (err.status === 429 && err.retryAfter) {
        stopResetResendWait();
        stopResetResendWait = Z.startResendWait($("resetSendBtn"), $("resetResendWait"), "zaban.resend.reset", err.retryAfter);
        return;
      }
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
    $("codeModeLink").addEventListener("click", (event) => { event.preventDefault(); showLoginMode(!codeMode); });
    $("loginSendBtn").addEventListener("click", sendLoginCode);
    $("forgotLink").addEventListener("click", (event) => { event.preventDefault(); showReset(true); });
    $("backToLogin").addEventListener("click", (event) => { event.preventDefault(); showReset(false); });
    $("resetSendBtn").addEventListener("click", sendResetCode);
    $("resetForm").addEventListener("submit", saveNewPassword);
    stopLoginResendWait = Z.resumeResendWait($("loginSendBtn"), $("loginResendWait"), "zaban.resend.login");
    stopResetResendWait = Z.resumeResendWait($("resetSendBtn"), $("resetResendWait"), "zaban.resend.reset");

    let me = null;
    try {
      me = await Z.request("GET", "/v1/web/me");
    } catch (_) {
      me = null;
    }
    if (me) {
      await enterApp();
    } else {
      showView("login");
    }
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
