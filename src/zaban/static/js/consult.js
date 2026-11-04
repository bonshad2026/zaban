(() => {
  const $ = (id) => document.getElementById(id);

  async function send(event) {
    event.preventDefault();
    const form = event.target;
    Z.showError($("consultError"), "");
    Z.show($("consultOk"), false);
    try {
      const result = await Z.request("POST", "/v1/public/consult", {
        name: form.name.value.trim(),
        phone: form.phone.value.trim(),
        preferred_time: form.preferred_time.value.trim() || null,
        message: form.message.value.trim(),
      });
      form.reset();
      $("consultOk").textContent = result.message;
      Z.show($("consultOk"), true);
    } catch (err) {
      Z.showError($("consultError"), err.message);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    Z.initLang();
    $("consultForm").addEventListener("submit", send);
  });
})();
