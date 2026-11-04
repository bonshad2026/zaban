// Shared helpers for every page. Users never see raw JSON or HTTP codes; errors become plain Persian sentences.
const Z = (() => {
  const ERROR_TEXT = [
    ["already taken", "این نام کاربری قبلاً استفاده شده است. یک نام دیگر انتخاب کنید."],
    ["Wrong email or password", "ایمیل یا رمز عبور درست نیست."],
    ["Parent consent is required", "برای شروع جلسه، ابتدا رضایت والد را ثبت کنید."],
    ["quota", "امکان ادامه‌ی جلسه‌ها فعلاً فراهم نیست. لطفاً با پشتیبانی تماس بگیرید."],
    ["Subscription expired", "اشتراک شما به پایان رسیده است."],
    ["already running", "یک جلسه هم‌اکنون در جریان است."],
    ["This lesson is closed", "این جلسه تمام شده است."],
    ["Please sign in", "لطفاً دوباره وارد شوید."],
    ["Not allowed", "شما اجازه‌ی انجام این کار را ندارید."],
    ["not found", "این مورد پیدا نشد."],
    ["Student not found", "این دانش‌آموز پیدا نشد."],
    ["A password is needed", "برای ساخت حساب ورود، رمز عبور لازم است."],
    ["Consent must be accepted", "برای ادامه، باید رضایت والد را تأیید کنید."],
  ];

  function friendly(detail, status) {
    if (typeof detail === "string") {
      const match = ERROR_TEXT.find(([key]) => detail.includes(key));
      if (match) return match[1];
    }
    if (status === 401) return "لطفاً دوباره وارد شوید.";
    if (status === 403) return "شما اجازه‌ی انجام این کار را ندارید.";
    if (status === 404) return "این مورد پیدا نشد.";
    if (status === 409) return "این کار هم‌اکنون امکان‌پذیر نیست.";
    return "مشکلی پیش آمد. لطفاً دوباره تلاش کنید.";
  }

  // Set by each page ("student" or "parent") so the server uses the right sign-in.
  const pageRole = { value: null };

  async function request(method, path, body) {
    const options = { method, credentials: "same-origin", headers: {} };
    if (pageRole.value) options.headers["X-Zaban-Role"] = pageRole.value;
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    let res;
    try {
      res = await fetch(path, options);
    } catch (_) {
      throw new Error("اتصال به سرور برقرار نشد. اینترنت یا اتصال سیستم را بررسی کنید.");
    }
    if (res.status === 204) return null;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const error = new Error(friendly(data.detail, res.status));
      error.status = res.status;
      throw error;
    }
    return data;
  }

  // The server stores UTC without a timezone marker. Add "Z" so the browser converts it to local time.
  function parseUtc(iso) {
    if (!iso) return null;
    return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + "Z");
  }

  function fmtDate(iso) {
    const d = parseUtc(iso);
    return d ? d.toLocaleDateString("fa-IR", { year: "numeric", month: "long", day: "numeric" }) : "—";
  }

  function fmtDateTime(iso) {
    const d = parseUtc(iso);
    return d ? d.toLocaleString("fa-IR", { year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function show(node, on) {
    node.hidden = !on;
  }

  function showError(node, message) {
    node.textContent = message || "";
    node.hidden = !message;
  }

  const STATUS_FA = {
    insufficient_data: "هنوز جلسه‌ی کافی ثبت نشده",
    ahead: "از برنامه جلوتر است",
    on_track: "طبق برنامه پیش می‌رود",
    behind: "کمی از برنامه عقب است",
    well_behind: "فاصله‌ی قابل توجهی با برنامه دارد",
    no_plan: "هنوز برنامه‌ای ثبت نشده",
  };

  const SUGGESTION_FA = {
    insufficient_data: "حداقل ۳ جلسه لازم است تا پیشرفت سنجیده شود.",
    ahead: "می‌توان موضوع سخت‌تری را در نظر گرفت.",
    on_track: "همین مسیر را ادامه دهید.",
    behind: "مرور اشتباه‌های ۳ جلسه‌ی اخیر و یک جلسه‌ی اضافه در این هفته پیشنهاد می‌شود.",
    well_behind: "بهتر است برنامه و سطح اولیه دوباره بررسی شود.",
    no_plan: "برای سنجش پیشرفت، ابتدا یک برنامه بسازید.",
  };

  const LEVEL_FA = {
    A1: "مبتدی", A2: "مقدماتی", B1: "متوسط", B2: "متوسط بالا", C1: "پیشرفته",
  };

  const SESSION_FA = { completed: "کامل شد", active: "در حال انجام", expired: "تمام شد" };

  // Shared language switch for the public pages. Only elements with data-fa / data-en change.
  function applyLang(lang) {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "en" ? "ltr" : "rtl";
    document.querySelectorAll("[data-fa]").forEach((node) => {
      node.textContent = lang === "en" ? node.dataset.en : node.dataset.fa;
    });
    const toggle = document.getElementById("langToggle");
    if (toggle) toggle.textContent = lang === "en" ? "فارسی" : "English";
  }

  function initLang() {
    let lang = "fa";
    try { lang = localStorage.getItem("zaban-lang") || "fa"; } catch (_) { /* storage blocked */ }
    applyLang(lang);
    const toggle = document.getElementById("langToggle");
    if (toggle) {
      toggle.addEventListener("click", () => {
        const next = document.documentElement.lang === "en" ? "fa" : "en";
        try { localStorage.setItem("zaban-lang", next); } catch (_) { /* storage blocked */ }
        applyLang(next);
      });
    }
  }

  return {
    request, friendly, pageRole, parseUtc, fmtDate, fmtDateTime, el, show, showError, initLang,
    STATUS_FA, SUGGESTION_FA, LEVEL_FA, SESSION_FA,
  };
})();
