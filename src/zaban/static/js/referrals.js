(() => {
  const $ = (id) => document.getElementById(id);

  async function load() {
    try {
      const data = await Z.request("GET", "/v1/web/user/referrals");
      $("referralCode").textContent = data.code || "—";
      $("referralTotal").textContent = String(data.total);
      $("referralPaid").textContent = String(data.with_plan);
      const list = $("referralList");
      list.replaceChildren(...data.people.map((person) => {
        const item = document.createElement("li");
        item.textContent = person.name;
        return item;
      }));
      $("referralEmpty").hidden = data.people.length > 0;
    } catch (err) {
      Z.showError($("referralError"), err.message);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    Z.initLang();
    load();
  });
})();
