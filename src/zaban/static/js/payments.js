(() => {
  const $ = (id) => document.getElementById(id);
  const english = () => document.documentElement.lang === "en";

  const STATUS = {
    pending: { fa: "در انتظار پرداخت", en: "Waiting for payment" },
    paid: { fa: "منتظر تأیید", en: "Waiting for confirmation" },
    confirmed: { fa: "تأیید شده", en: "Confirmed" },
    failed: { fa: "ناموفق", en: "Failed" },
  };

  function cell(text) {
    const td = document.createElement("td");
    td.textContent = text;
    return td;
  }

  // One row per payment: date, plan, amount in toman, and the status in words.
  function row(item) {
    const status = STATUS[item.status] || { fa: item.status, en: item.status };
    const amount = Number(item.amount_toman).toLocaleString(english() ? "en-US" : "fa-IR");
    const tr = document.createElement("tr");
    tr.append(
      cell(Z.fmtDate(item.created_at)),
      cell(item.plan_name || "—"),
      cell(english() ? `${amount} Toman` : `${amount} تومان`),
      cell(english() ? status.en : status.fa),
      cell(item.failure_reason || "—"),
    );
    return tr;
  }

  async function load() {
    try {
      const items = await Z.request("GET", "/v1/web/billing/payments");
      Z.show($("paymentsEmpty"), items.length === 0);
      Z.show($("paymentsTableWrap"), items.length > 0);
      $("paymentsRows").replaceChildren(...items.map(row));
    } catch (err) {
      Z.showError($("paymentsError"), err.message);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    Z.initLang();
    load();
  });
})();
