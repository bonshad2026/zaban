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
  let stopLoginTimer = () => {};
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
      stopLoginTimer();
      Z.show($("loginTimer"), false);
      Z.show($("loginDevHint"), false);
      setBilingual($("codeModeLink"), "ورود با کد پیامکی", "Sign in with an SMS code");
    }
  }

  // The code is valid for the time the server gives (2 minutes by default). When it runs out, the form says so.
  function startLoginClock(seconds) {
    stopLoginTimer();
    stopLoginTimer = Z.codeTimer(
      $("loginTimer"),
      seconds,
      {
        running: (time) => t(`کد تا ${time} دیگر معتبر است.`, `The code is valid for ${time}.`),
        done: t("کد منقضی شد. دوباره کد پیامکی بگیرید.", "The code has expired. Request a new SMS code."),
      },
    );
  }

  async function sendLoginCode() {
    Z.showError($("loginError"), "");
    const phone = $("parentPhone").value.trim();
    if (!phone) {
      Z.showError($("loginError"), t("ابتدا شماره‌ی موبایل را وارد کنید.", "Enter your mobile number first."));
      $("parentPhone").focus();
      return;
    }
    try {
      const sent = await Z.request("POST", "/v1/web/user/otp/request", { phone, purpose: "login" });
      Z.showDevCode($("loginDevHint"), $("parentCode"), sent.dev_code);
      startLoginClock(sent.expires_in_seconds);
      $("parentCode").focus();
    } catch (err) {
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
        stopLoginTimer();
        location.href = "/";
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
    $("codeModeLink").addEventListener("click", (event) => { event.preventDefault(); showLoginMode(!codeMode); });
    $("loginSendBtn").addEventListener("click", sendLoginCode);
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
