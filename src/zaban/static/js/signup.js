(() => {
  const $ = (id) => document.getElementById(id);
  const isEnglish = () => document.documentElement.lang === "en";
  const t = (fa, en) => (isEnglish() ? en : fa);

  // After a code is sent, the send button is replaced by a countdown until a new code can be asked for.
  let stopResendWait = () => {};

  async function sendCode() {
    if ($("sendCodeBtn").hidden) return;
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
      stopResendWait();
      stopResendWait = Z.startResendWait($("sendCodeBtn"), $("signupResendWait"), "zaban.resend.signup", sent.resend_in_seconds);
      $("signupCode").focus();
    } catch (err) {
      if (err.status === 429 && err.retryAfter) {
        stopResendWait();
        stopResendWait = Z.startResendWait($("sendCodeBtn"), $("signupResendWait"), "zaban.resend.signup", err.retryAfter);
        return;
      }
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
      // The account exists and the browser holds its sign-in. The plan page comes next.
      Z.go("/student");
    } catch (err) {
      Z.showError($("signupError"), err.message);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    Z.initLang();
    $("sendCodeBtn").addEventListener("click", sendCode);
    $("signupForm").addEventListener("submit", signUp);
    stopResendWait = Z.resumeResendWait($("sendCodeBtn"), $("signupResendWait"), "zaban.resend.signup");
  });
})();
