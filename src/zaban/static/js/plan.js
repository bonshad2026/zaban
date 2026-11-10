(() => {
  const $ = (id) => document.getElementById(id);
  const english = () => document.documentElement.lang === "en";

  // Shows the adult's plan: its name, when the paid period began, when it ends, and the days left.
  function show(plan) {
    $("planName").textContent = (english() ? plan.plan_name_en : plan.plan_name) || (english() ? "No plan yet" : "هنوز پلنی فعال نشده است");
    $("planStarted").textContent = Z.fmtDate(plan.plan_started_at);
    $("planExpires").textContent = Z.fmtDate(plan.plan_expires_at);
    $("planDays").textContent = String(plan.days_left);
    const allowance = plan.token_allowance || 0;
    $("planTokens").textContent = allowance
      ? `${Number(plan.tokens_used).toLocaleString(english() ? "en-US" : "fa-IR")} از ${Number(allowance).toLocaleString(english() ? "en-US" : "fa-IR")}`
      : "—";
    $("planPercent").textContent = `${plan.tokens_percent}٪`;
    $("planBar").style.width = `${plan.tokens_percent}%`;
    Z.show($("planMeter"), allowance > 0);
    $("planStatus").textContent = plan.has_active_plan
      ? (english() ? "Your plan is active." : "پلن شما فعال است.")
      : (english() ? "Your plan is not active. Buy a plan to continue." : "پلن شما فعال نیست. برای ادامه، یک پلن تهیه کنید.");
    Z.show($("planStatus"), true);
    Z.show($("planFacts"), true);
    // While the plan still has days and tokens, a new one cannot be bought.
    $("planBuyBtn").disabled = Boolean(plan.has_active_plan);
    $("planBuyBtn").title = plan.has_active_plan
      ? (english() ? "Your plan is not finished yet." : "پلن فعلی هنوز تمام نشده است.")
      : "";
  }

  // The buy button starts the payment with the single plan the service sells.
  async function buy() {
    Z.showError($("planError"), "");
    try {
      const plans = await Z.request("GET", "/v1/web/billing/plans");
      const paid = await Z.request("POST", "/v1/web/billing/checkout", { plan_id: plans[0].id });
      location.href = paid.redirect;
    } catch (err) {
      Z.showError($("planError"), err.message);
    }
  }

  // After the gateway returns the buyer here, the result is shown. A failed payment shows its reason in the payments page.
  function showResult() {
    const result = new URLSearchParams(location.search).get("payment");
    if (!result) return;
    const node = $("planNotice");
    node.hidden = false;
    if (result === "paid") {
      node.textContent = english() ? "Your payment was successful and your plan is active." : "پرداخت شما موفق بود و پلن شما فعال شد.";
    } else {
      node.className = "error";
      node.textContent = english()
        ? "The payment did not go through. See the reason in the payments page."
        : "پرداخت انجام نشد. دلیل آن را در بخش پرداخت‌ها ببینید.";
    }
    history.replaceState(null, "", location.pathname);
  }

  async function load() {
    try {
      show(await Z.request("GET", "/v1/web/billing/plan"));
    } catch (err) {
      Z.showError($("planError"), err.message);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    Z.initLang();
    $("planBuyBtn").addEventListener("click", buy);
    showResult();
    load();
  });
})();
