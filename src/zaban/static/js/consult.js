(() => {
  const $ = (id) => document.getElementById(id);

  async function send(event) {
    event.preventDefault();
    const form = event.target;
    Z.showError($("consultError"), "");
    try {
      if (!form.contact_permission.checked) {
        Z.showError($("consultError"), document.documentElement.lang === "en" ? "Please confirm that we may call you before sending." : "برای ارسال درخواست، اجازه‌ی تماس را تأیید کنید.");
        return;
      }
      await Z.request("POST", "/v1/public/consult", {
        name: form.name.value.trim(),
        last_name: form.last_name.value.trim(),
        subject: form.subject.value,
        contact_permission: true,
        phone: form.phone.value.trim(),
        preferred_time: form.preferred_time.value.trim() || null,
        message: form.message.value.trim(),
      });
      // After a successful request the form is replaced by two choices: send another, or go to the home page.
      form.reset();
      form.hidden = true;
      Z.show($("consultDone"), true);
    } catch (err) {
      Z.showError($("consultError"), err.message);
    }
  }

  function sendAnother() {
    Z.show($("consultDone"), false);
    $("consultForm").hidden = false;
    $("consultName").focus();
  }

  document.addEventListener("DOMContentLoaded", () => {
    Z.initLang();
    $("consultForm").addEventListener("submit", send);
    $("consultAgain").addEventListener("click", sendAnother);
  });
})();
