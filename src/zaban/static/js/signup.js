(() => {
  const $ = (id) => document.getElementById(id);
  const isEnglish = () => document.documentElement.lang === "en";
  const t = (fa, en) => (isEnglish() ? en : fa);

  let stopTimer = () => {};

  // The code is valid for the time the server gives (2 minutes by default). When it runs out, the form says so.
  function startCodeClock(seconds) {
    stopTimer();
    stopTimer = Z.codeTimer(
      $("signupTimer"),
      seconds,
      {
        running: (time) => t(`کد تا ${time} دیگر معتبر است.`, `The code is valid for ${time}.`),
        done: t("کد منقضی شد. دوباره کد پیامکی بگیرید.", "The code has expired. Request a new SMS code."),
      },
    );
  }

  async function sendCode() {
    Z.showError($("signupError"), "");
    const phone = $("signupPhone").value.trim();
    if (!phone) {
      Z.showError($("signupError"), t("ابتدا شماره‌ی موبایل را وارد کنید.", "Enter your mobile number first."));
      $("signupPhone").focus();
      return;
    }
    try {
      const sent = await Z.request("POST", "/v1/web/user/otp/request", { phone, purpose: "signup" });
      Z.showDevCode($("signupDevHint"), $("signupCode"), sent.dev_code);
      startCodeClock(sent.expires_in_seconds);
      $("signupCode").focus();
    } catch (err) {
      Z.showError($("signupError"), err.message);
    }
  }

  // Checks the form before it is sent, so each mistake gets its own sentence.
  function problemWith(form) {
    if (!form.full_name.value.trim()) return t("نام و نام خانوادگی را وارد کنید.", "Enter your full name.");
    if (!form.phone.value.trim()) return t("شماره‌ی موبایل را وارد کنید.", "Enter your mobile number.");
    if (form.password.value.length < 8) return t("رمز عبور باید حداقل ۸ نویسه باشد.", "The password must be at least 8 characters.");
    if (form.password.value !== form.password_repeat.value) {
      return t("رمز عبور و تکرار آن یکسان نیست.", "The password and its repeat do not match.");
    }
    if (!form.code.value.trim()) return t("کد پیامکی را وارد کنید.", "Enter the SMS code.");
    if (!form.consent.checked) return t("برای ساخت حساب، قوانین و حریم خصوصی را بپذیرید.", "Accept the terms and privacy policy to create an account.");
    return "";
  }

  async function signUp(event) {
    event.preventDefault();
    const form = event.target;
    Z.showError($("signupError"), "");
    const problem = problemWith(form);
    if (problem) {
      Z.showError($("signupError"), problem);
      return;
    }
    try {
      await Z.request("POST", "/v1/web/user/signup", {
        phone: form.phone.value.trim(),
        code: form.code.value.trim(),
        full_name: form.full_name.value.trim(),
        password: form.password.value,
        referral_code: form.referral_code.value.trim() || null,
      });
      stopTimer();
      // The account exists and the browser holds its sign-in. The plan page comes next.
      location.href = "/parent";
    } catch (err) {
      Z.showError($("signupError"), err.message);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    Z.initLang();
    $("sendCodeBtn").addEventListener("click", sendCode);
    $("signupForm").addEventListener("submit", signUp);
  });
})();
