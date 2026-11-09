(() => {
  const $ = (id) => document.getElementById(id);
  const english = () => document.documentElement.lang === "en";

  const KIND = {
    consult: { fa: "درخواست مشاوره", en: "Consult request" },
    cooperation: { fa: "درخواست همکاری", en: "Cooperation request" },
  };

  function row(item) {
    const kind = KIND[item.kind];
    const li = document.createElement("li");
    li.className = "card";
    const title = document.createElement("strong");
    title.textContent = item.subject;
    const meta = document.createElement("p");
    meta.className = "muted";
    const date = new Date(item.created_at).toLocaleDateString(english() ? "en-GB" : "fa-IR");
    meta.textContent = `${english() ? kind.en : kind.fa} · ${date} · ${item.status}`;
    li.append(title, meta);
    return li;
  }

  async function load() {
    try {
      const data = await Z.request("GET", "/v1/web/user/requests");
      const items = [...data.consult, ...data.cooperation].sort((a, b) => b.created_at.localeCompare(a.created_at));
      Z.show($("requestsEmpty"), items.length === 0);
      $("requestsList").replaceChildren(...items.map(row));
    } catch (err) {
      Z.showError($("requestsError"), err.message);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    Z.initLang();
    load();
  });
})();
