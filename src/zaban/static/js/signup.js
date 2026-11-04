(() => {
  const $ = (id) => document.getElementById(id);

  async function sendCode() {
    Z.showError($("signupError"), "");
    const phone = $("signupPhone").value.trim();
    try {
      const sent = await Z.request("POST", "/v1/web/user/otp/request", { phone, purpose: "signup" });
      Z.show($("signupStep"), true);
      Z.showDevCode($("signupDevHint"), $("signupCode"), sent.dev_code);
      $("signupCode").focus();
    } catch (err) {
      Z.showError($("signupError"), err.message);
    }
  }

  async function signUp(event) {
    event.preventDefault();
    // Enter on the phone field sends the code first, before the rest of the form is shown.
    if ($("signupStep").hidden) return sendCode();
    const form = event.target;
    Z.showError($("signupError"), "");
    try {
      await Z.request("POST", "/v1/web/user/signup", {
        phone: form.phone.value.trim(),
        code: form.code.value.trim(),
        full_name: form.full_name.value.trim(),
        password: form.password.value,
        goal: form.goal.value || null,
        age_confirmed: form.age_confirmed.checked,
      });
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
