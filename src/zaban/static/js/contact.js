(() => {
  const $ = (id) => document.getElementById(id);

  // Sends the contact form to the same public endpoint as the consult request.
  async function send(event) {
    event.preventDefault();
    const form = event.target;
    Z.showError($("contactError"), "");
    try {
      if (!form.contact_permission.checked) {
        Z.showError($("contactError"), document.documentElement.lang === "en" ? "Please confirm that we may call you before sending." : "برای ارسال پیام، اجازه‌ی تماس را تأیید کنید.");
        return;
      }
      await Z.request("POST", "/v1/public/consult", {
        name: form.name.value.trim(),
        last_name: form.last_name.value.trim(),
        subject: form.subject.value,
        contact_permission: true,
        phone: form.phone.value.trim(),
        preferred_time: null,
        message: form.message.value.trim(),
      });
      form.reset();
      form.hidden = true;
      Z.show($("contactDone"), true);
    } catch (err) {
      Z.showError($("contactError"), err.message);
    }
  }

  function sendAnother() {
    Z.show($("contactDone"), false);
    $("contactForm").hidden = false;
    $("contactName").focus();
  }

  document.addEventListener("DOMContentLoaded", () => {
    Z.initLang();
    $("contactForm").addEventListener("submit", send);
    $("contactAgain").addEventListener("click", sendAnother);
  });
})();
