// Shared helpers for every page. Users never see raw JSON or HTTP codes; errors become plain Persian sentences.
const Z = (() => {
  const ERROR_TEXT = [
    ["already taken", "این نام کاربری قبلاً استفاده شده است. یک نام دیگر انتخاب کنید."],
    ["Wrong username or PIN", "نام کاربری یا PIN درست نیست."],
    ["Too many wrong PINs", "چند بار PIN اشتباه وارد شده است. ۱۵ دقیقه بعد دوباره تلاش کنید."],
    ["Invalid or expired code", "کد اشتباه است یا منقضی شده. کد تازه بگیرید."],
    ["Please wait a minute", "لطفاً یک دقیقه صبر کنید، سپس دوباره کد بگیرید."],
    ["Too many codes", "تعداد درخواست کد زیاد شده است. کمی بعد دوباره تلاش کنید."],
    ["Enter a valid mobile number", "شماره‌ی موبایل معتبر نیست. مثلاً 09121234567 را وارد کنید."],
    ["Your name is needed", "برای ساخت حساب، نام و نام خانوادگی لازم است."],
    ["SMS could not be sent", "پیامک ارسال نشد. لطفاً دوباره تلاش کنید."],
    ["The PIN must be", "PIN باید ۴ تا ۶ رقم باشد."],
    ["Adults must create", "بزرگسالان باید حساب خودشان را بسازند."],
    ["not ready yet", "سرویس هنوز آماده نیست. کمی بعد دوباره تلاش کنید."],
    ["Choose a plan first", "برای ادامه، ابتدا یک پلن را انتخاب و پرداخت کنید."],
    ["Wrong phone number or password", "شماره موبایل یا رمز عبور درست نیست."],
    ["Too many wrong passwords", "چند بار رمز اشتباه وارد شده است. ۱۵ دقیقه بعد دوباره تلاش کنید."],
    ["already registered", "این شماره قبلاً ثبت شده است. با همین شماره وارد شوید."],
    ["Only adults can create", "ثبت‌نام در این بخش فقط برای بزرگسالان است."],
    ["Password must", "رمز عبور باید حداقل ۸ نویسه باشد."],
    ["Your name is needed", "برای ثبت‌نام، نام و نام خانوادگی لازم است."],
    ["Too many requests", "تعداد درخواست‌ها زیاد شده است. کمی بعد دوباره تلاش کنید."],
    ["Wrong password", "رمز ورود درست نیست."],
    ["not available", "این پلن در حال حاضر در دسترس نیست."],
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

  // Development only: when no SMS provider is set, the server returns the code and it is filled in here.
  function showDevCode(hint, input, code) {
    if (!code) {
      hint.hidden = true;
      return;
    }
    input.value = code;
    hint.textContent = `حالت آزمایشی: پیامک ارسال نشد. کد ${code} خودکار وارد شد.`;
    hint.hidden = false;
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

  // Shows who is signed in on this browser. A visitor who is signed out keeps the static "ورود" menu.
  // A sign-in that is missing is normal here, so each check only decides which buttons appear.
  async function initSiteHeader() {
    const box = document.getElementById("siteActions");
    if (!box) return;
    const signedIn = [];
    for (const role of ["parent", "student"]) {
      try {
        await request("GET", `/v1/web/me?role=${role}`);
        signedIn.push(role);
      } catch (_) { /* not signed in to this area */ }
    }
    if (!signedIn.length) return;

    const english = document.documentElement.lang === "en";
    const labelled = (tag, className, href, fa, en) => {
      const node = el(tag, className, english ? en : fa);
      node.dataset.fa = fa;
      node.dataset.en = en;
      if (href) node.href = href;
      return node;
    };
    const toggle = document.getElementById("langToggle");
    box.replaceChildren();
    if (toggle) box.appendChild(toggle);
    if (signedIn.includes("parent")) box.appendChild(labelled("a", "pill", "/parent", "پنل والد", "Parent area"));
    if (signedIn.includes("student")) box.appendChild(labelled("a", "pill", "/student", "یادگیری من", "My learning"));
    const logout = labelled("button", "ghost", null, "خروج", "Sign out");
    logout.addEventListener("click", async () => {
      await Promise.all(signedIn.map((role) => request("POST", `/v1/web/logout?role=${role}`).catch(() => {})));
      location.href = "/";
    });
    box.appendChild(logout);
    box.dataset.state = "member";
  }

  return {
    request, friendly, pageRole, parseUtc, fmtDate, fmtDateTime, el, show, showError, showDevCode, initLang,
    initSiteHeader, STATUS_FA, SUGGESTION_FA, LEVEL_FA, SESSION_FA,
  };
})();

document.addEventListener("DOMContentLoaded", () => Z.initSiteHeader());
