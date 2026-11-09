(() => {
  const $ = (id) => document.getElementById(id);
  const english = () => document.documentElement.lang === "en";

  async function load() {
    try {
      const me = await Z.request("GET", "/v1/web/user/profile");
      $("pfName").value = me.name;
      $("pfPhone").value = me.phone;
      Z.show($("profileBox"), true);
      Z.show($("passwordBox"), true);
    } catch (_) {
      // Not signed in as an adult: the sign-in page is the right place.
      location.href = "/parent";
    }
  }

  function flash(id, text) {
    $(id).textContent = text;
    Z.show($(id), true);
  }

  async function saveProfile(event) {
    event.preventDefault();
    Z.showError($("pfError"), "");
    Z.show($("pfOk"), false);
    try {
      const me = await Z.request("PUT", "/v1/web/user/profile", { full_name: $("pfName").value.trim() });
      $("pfName").value = me.name;
      flash("pfOk", english() ? "Saved." : "ذخیره شد.");
    } catch (err) {
      Z.showError($("pfError"), err.message);
    }
  }

  async function savePassword(event) {
    event.preventDefault();
    Z.showError($("pwError"), "");
    Z.show($("pwOk"), false);
    try {
      await Z.request("POST", "/v1/web/user/password", {
        current_password: $("pwCurrent").value,
        new_password: $("pwNew").value,
      });
      $("passwordForm").reset();
      flash("pwOk", english() ? "Your new password is saved." : "رمز تازه ذخیره شد.");
    } catch (err) {
      Z.showError($("pwError"), err.message);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    Z.initLang();
    $("profileForm").addEventListener("submit", saveProfile);
    $("passwordForm").addEventListener("submit", savePassword);
    load();
  });
})();
