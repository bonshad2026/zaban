(() => {
  const $ = (id) => document.getElementById(id);

  async function send(event) {
    event.preventDefault();
    const form = event.target;
    Z.showError($("coopError"), "");
    try {
      await Z.request("POST", "/v1/public/cooperation", {
        subject: form.subject.value.trim(),
        phone: form.phone.value.trim(),
        email: form.email.value.trim() || null,
        message: form.message.value.trim(),
      });
      form.reset();
      form.hidden = true;
      Z.show($("coopDone"), true);
    } catch (err) {
      Z.showError($("coopError"), err.message);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    Z.initLang();
    $("cooperationForm").addEventListener("submit", send);
  });
})();
