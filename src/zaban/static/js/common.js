// Shared helpers for every page. Users never see raw JSON or HTTP codes; errors become plain Persian sentences.
const Z = (() => {
  const ERROR_TEXT = [
    ["already taken", "این نام کاربری قبلاً استفاده شده است. یک نام دیگر انتخاب کنید."],
    ["Wrong username or PIN", "نام کاربری یا PIN درست نیست."],
    ["Too many wrong PINs", "چند بار PIN اشتباه وارد شده است. ۱۵ دقیقه بعد دوباره تلاش کنید."],
    ["Invalid or expired code", "کد اشتباه است یا منقضی شده. کد تازه بگیرید."],
    ["Please wait a minute", "لطفاً یک دقیقه صبر کنید، سپس دوباره کد بگیرید."],
    ["Too many codes", "تعداد درخواست کد زیاد شده است. کمی بعد دوباره تلاش کنید."],
    ["This account is suspended", "این حساب موقتاً تعلیق شده است. برای پیگیری با پشتیبانی تماس بگیرید."],
    ["Your current plan is not finished yet", "پلن فعلی شما هنوز تمام نشده است. بعد از پایان آن می‌توانید پلن جدید تهیه کنید."],
    ["This plan is not available", "این پلن در حال حاضر در دسترس نیست."],
    ["Enter a valid mobile number", "شماره‌ی موبایل معتبر نیست. مثلاً 09121234567 را وارد کنید."],
    ["Your name is needed", "برای ساخت حساب، نام و نام خانوادگی لازم است."],
    ["SMS could not be sent", "پیامک ارسال نشد. لطفاً دوباره تلاش کنید."],
    ["The PIN must be", "PIN باید ۴ تا ۶ رقم باشد."],
    ["Adults must create", "بزرگسالان باید حساب خودشان را بسازند."],
    ["not ready yet", "سرویس هنوز آماده نیست. کمی بعد دوباره تلاش کنید."],
    ["Choose a plan first", "برای ادامه، ابتدا یک پلن را انتخاب و پرداخت کنید."],
    ["Wrong phone number or password", "شماره موبایل یا رمز عبور درست نیست."],
    ["This teacher code is not valid", "این کد مربی معتبر نیست."],
    ["You cannot choose yourself as your teacher", "نمی‌توانید خودتان را مربی خود انتخاب کنید."],
    ["Please confirm that this is your teacher", "لطفاً تأیید کنید که این مربی شماست."],
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
    ["Enter a valid email", "ایمیل معتبر نیست. مثلاً name@example.com را وارد کنید."],
    ["already used by another", "این ایمیل برای حساب دیگری استفاده شده است."],
    ["current password is not correct", "رمز فعلی درست نیست."],
    ["photo must be", "عکس باید از نوع JPG، PNG یا WebP باشد."],
    ["This program is finished", "این برنامه‌ی یادگیری تمام شده است."],
    ["This test is finished", "این آزمون تمام شده است."],
    ["Level is already set", "سطح این دانش‌آموز قبلاً ثبت شده است."],
    ["This part of the test is not running", "این بخش از آزمون در حال اجرا نیست."],
  ];

  // English messages for the same server errors, matched by the same keys, in the same order.
  const ERROR_TEXT_EN = [
    ["already taken", "This username is already taken. Please choose another one."],
    ["Wrong username or PIN", "The username or PIN is wrong."],
    ["Too many wrong PINs", "Too many wrong PINs. Please try again in 15 minutes."],
    ["Invalid or expired code", "The code is wrong or has expired. Please request a new one."],
    ["Please wait a minute", "Please wait a minute, then request a new code."],
    ["Too many codes", "Too many codes were requested. Please try again later."],
    ["This account is suspended", "This account is suspended for now. Contact support to follow up."],
    ["Your current plan is not finished yet", "Your current plan is not finished yet. You can buy a new one when it ends."],
    ["This plan is not available", "This plan is not available right now."],
    ["Enter a valid mobile number", "Please enter a valid mobile number, for example 09121234567."],
    ["Your name is needed", "Please enter your full name."],
    ["SMS could not be sent", "The SMS could not be sent. Please try again."],
    ["The PIN must be", "The PIN must be 4 to 6 digits."],
    ["Adults must create", "Adults must create their own account."],
    ["not ready yet", "The service is not ready yet. Please try again later."],
    ["Choose a plan first", "Please choose and pay for a plan first."],
    ["Wrong phone number or password", "The phone number or password is wrong."],
    ["This teacher code is not valid", "This teacher code is not valid."],
    ["You cannot choose yourself as your teacher", "You cannot choose yourself as your teacher."],
    ["Please confirm that this is your teacher", "Please confirm that this is your teacher."],
    ["Too many wrong passwords", "Too many wrong passwords. Please try again in 15 minutes."],
    ["already registered", "This number is already registered. Please sign in instead."],
    ["Only adults can create", "Only adults can create an account here."],
    ["Password must", "The password must be at least 8 characters."],
    ["Too many requests", "Too many requests. Please try again later."],
    ["Wrong password", "The password is wrong."],
    ["not available", "This plan is not available right now."],
    ["Parent consent is required", "A parent's consent is needed before a lesson can start."],
    ["quota", "Lessons are not available right now. Please contact support."],
    ["Subscription expired", "Your subscription has ended."],
    ["already running", "A lesson is already running."],
    ["This lesson is closed", "This lesson has ended."],
    ["Please sign in", "Please sign in again."],
    ["Not allowed", "You are not allowed to do this."],
    ["not found", "This item was not found."],
    ["Student not found", "This learner was not found."],
    ["A password is needed", "A password is needed to create a sign-in."],
    ["Consent must be accepted", "The parent's consent must be accepted to continue."],
    ["Enter a valid email", "Please enter a valid email address, for example name@example.com."],
    ["already used by another", "This email is already used by another account."],
    ["current password is not correct", "The current password is not correct."],
    ["photo must be", "The photo must be a JPG, PNG or WebP image."],
    ["This program is finished", "This learning program is finished."],
    ["This test is finished", "This test is finished."],
    ["Level is already set", "The level is already set."],
    ["This part of the test is not running", "This part of the test is not running."],
  ];

  function isEnglish() {
    return document.documentElement.lang === "en";
  }

  // Picks the message in the language the page is showing, so Persian pages stay Persian.
  function friendly(detail, status) {
    const english = isEnglish();
    // The server lists the missing profile fields after the colon, for example "level, age".
    if (typeof detail === "string" && detail.startsWith("Complete the profile")) {
      const names = english
        ? { level: "level", age: "age", gender: "gender" }
        : { level: "سطح", age: "سن", gender: "جنسیت" };
      const items = detail
        .split(":")
        .pop()
        .split(",")
        .map((key) => names[key.trim()] || key.trim())
        .join(english ? ", " : "، ");
      return english
        ? `Before a lesson starts, complete: ${items}.`
        : `برای شروع جلسه، ابتدا این موارد را کامل کنید: ${items}.`;
    }
    if (typeof detail === "string") {
      const table = english ? ERROR_TEXT_EN : ERROR_TEXT;
      const match = table.find(([key]) => detail.includes(key));
      if (match) return match[1];
    }
    if (status === 401) return english ? "Please sign in again." : "لطفاً دوباره وارد شوید.";
    if (status === 403) return english ? "You are not allowed to do this." : "شما اجازه‌ی انجام این کار را ندارید.";
    if (status === 404) return english ? "This item was not found." : "این مورد پیدا نشد.";
    if (status === 422) return english ? "Please check the form and try again." : "لطفاً مقدارهای فرم را بررسی کنید.";
    if (status === 409) return english ? "This action is not possible right now." : "این کار هم‌اکنون امکان‌پذیر نیست.";
    return english ? "Something went wrong. Please try again." : "مشکلی پیش آمد. لطفاً دوباره تلاش کنید.";
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
      throw new Error(isEnglish()
        ? "Could not reach the server. Please check your internet connection."
        : "اتصال به سرور برقرار نشد. اینترنت یا اتصال سیستم را بررسی کنید.");
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

  // Dates and numbers follow the language the visitor chose.
  // The language is read from storage, so it is known before the page's first script runs.
  function currentLang() {
    try { return localStorage.getItem("zaban-lang") === "en" ? "en" : "fa"; } catch (_) { return "fa"; }
  }

  function locale() {
    return currentLang() === "en" ? "en-US" : "fa-IR";
  }

  function fmtDate(iso) {
    const d = parseUtc(iso);
    return d ? d.toLocaleDateString(locale(), { year: "numeric", month: "long", day: "numeric" }) : "—";
  }

  function fmtDateTime(iso) {
    const d = parseUtc(iso);
    return d ? d.toLocaleString(locale(), { year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";
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

  // Shows how long a one-time code stays valid. texts.running(time) while it is valid, texts.done once it expires.
  // Returns a function that stops the countdown.
  function codeTimer(node, seconds, texts, onDone) {
    const end = Date.now() + seconds * 1000;
    const locale = isEnglish() ? "en-US" : "fa-IR";
    const tick = () => {
      const left = Math.max(0, Math.ceil((end - Date.now()) / 1000));
      if (left === 0) {
        node.textContent = texts.done;
        clearInterval(timerId);
        if (onDone) onDone();
        return;
      }
      const minutes = Math.floor(left / 60).toLocaleString(locale, { minimumIntegerDigits: 2 });
      const rest = (left % 60).toLocaleString(locale, { minimumIntegerDigits: 2 });
      node.textContent = texts.running(`${minutes}:${rest}`);
    };
    const timerId = setInterval(tick, 1000);
    node.hidden = false;
    tick();
    return () => clearInterval(timerId);
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
    A1: "مبتدی", A2: "مقدماتی", B1: "متوسط", B2: "متوسط بالا", C1: "پیشرفته", C2: "تسلط کامل",
  };

  const SESSION_FA = { completed: "کامل شد", active: "در حال انجام", expired: "تمام شد" };

  // Shared language switch for the public pages. Only elements with data-fa / data-en change.
  function applyLang(lang) {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "en" ? "ltr" : "rtl";
    document.querySelectorAll("[data-fa]").forEach((node) => {
      node.textContent = lang === "en" ? node.dataset.en : node.dataset.fa;
    });
    // Placeholders in forms follow the language too.
    document.querySelectorAll("[data-placeholder-fa]").forEach((node) => {
      node.placeholder = lang === "en" ? node.dataset.placeholderEn : node.dataset.placeholderFa;
    });
    document.querySelectorAll("#langToggle [data-lang]").forEach((node) => {
      node.classList.toggle("is-active", node.dataset.lang === lang);
    });
    paintThemeToggle();
  }

  // Light or dark theme. Dark is the default. The choice is remembered in this browser.
  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    paintThemeToggle();
  }

  // The button names the theme it will switch to, in the language the page is showing.
  function paintThemeToggle() {
    const button = document.getElementById("themeToggle");
    if (!button) return;
    const english = document.documentElement.lang === "en";
    const light = document.documentElement.dataset.theme === "light";
    const label = light ? (english ? "Dark theme" : "تم تاریک") : (english ? "Light theme" : "تم روشن");
    button.setAttribute("aria-label", label);
    button.title = label;
  }

  let themeReady = false;
  function initTheme() {
    if (themeReady) return;
    themeReady = true;
    let theme = "dark";
    try { theme = localStorage.getItem("zaban-theme") === "light" ? "light" : "dark"; } catch (_) { /* storage blocked */ }
    applyTheme(theme);
    const button = document.getElementById("themeToggle");
    if (button) {
      button.addEventListener("click", () => {
        const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
        try { localStorage.setItem("zaban-theme", next); } catch (_) { /* storage blocked */ }
        applyTheme(next);
      });
    }
  }

  // Runs once per page. Pages may call it again without adding a second click handler.
  let langReady = false;
  function initLang() {
    if (langReady) return;
    langReady = true;
    let lang = "fa";
    try { lang = localStorage.getItem("zaban-lang") || "fa"; } catch (_) { /* storage blocked */ }
    applyLang(lang);
    const toggle = document.getElementById("langToggle");
    if (toggle) {
      toggle.addEventListener("click", () => {
        const next = document.documentElement.lang === "en" ? "fa" : "en";
        try { localStorage.setItem("zaban-lang", next); } catch (_) { /* storage blocked */ }
        applyLang(next);
        document.dispatchEvent(new Event("zaban:lang"));
      });
    }
  }

  function byId(id) {
    return document.getElementById(id);
  }

  // Shown when the adult has no photo: a plain silhouette.
  const AVATAR_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8.5" r="4"/><path d="M4.5 20.5c1.2-3.9 4-6 7.5-6s6.3 2.1 7.5 6"/></svg>';

  function paintAvatar(node, src) {
    node.replaceChildren();
    if (src) {
      const img = el("img", "avatar-img");
      img.src = src;
      img.alt = "";
      node.appendChild(img);
    } else {
      node.insertAdjacentHTML("beforeend", AVATAR_ICON);
    }
  }

  // A link or button whose words follow the language switch.
  function labelled(tag, className, href, fa, en) {
    const node = el(tag, className, isEnglish() ? en : fa);
    node.dataset.fa = fa;
    node.dataset.en = en;
    if (href) node.href = href;
    return node;
  }

  // Resizes the picked photo to a 256 px square JPEG, so it is small enough to store with the profile.
  function readPhoto(file) {
    return new Promise((resolve, reject) => {
      const fail = () => reject(new Error(isEnglish()
        ? "This picture could not be read. Please choose another one."
        : "این عکس خوانده نشد. عکس دیگری انتخاب کنید."));
      if (!file || !file.type.startsWith("image/")) return fail();
      const reader = new FileReader();
      reader.onerror = fail;
      reader.onload = () => {
        const img = new Image();
        img.onerror = fail;
        img.onload = () => {
          const side = Math.min(img.naturalWidth, img.naturalHeight);
          const canvas = document.createElement("canvas");
          canvas.width = 256;
          canvas.height = 256;
          const ctx = canvas.getContext("2d");
          ctx.fillStyle = "#ffffff";
          ctx.fillRect(0, 0, 256, 256);
          ctx.drawImage(img, (img.naturalWidth - side) / 2, (img.naturalHeight - side) / 2, side, side, 0, 0, 256, 256);
          resolve(canvas.toDataURL("image/jpeg", 0.85));
        };
        img.src = reader.result;
      };
      reader.readAsDataURL(file);
    });
  }

  // Opens the personal-details form with the values the server has right now.
  async function openPersonalDetails() {
    const dialog = byId("accInfoDialog");
    showError(byId("accInfoError"), "");
    show(byId("accInfoOk"), false);
    try {
      const me = await request("GET", "/v1/web/user/profile");
      byId("accName").value = me.name;
      byId("accPhone").value = me.phone;
      byId("accEmail").value = me.email;
      byId("accAge").value = me.age == null ? "" : me.age;
      byId("accGender").value = me.gender;
      byId("accGoal").value = me.goal || "";
      setPhoto(me.avatar);
    } catch (err) {
      showError(byId("accInfoError"), err.message);
    }
    learnerReady = false;
    const learner = await learnerDetails();
    learnerReady = Boolean(learner);
    fillLearner(learner);
    dialog.showModal();
  }

  // The learner part of the dialog (level, grade, how the teacher should talk, and so on) needs the learner sign-in.
  // The adult gets it by starting their own learning, which needs a plan. Without one, this part stays hidden.
  let learnerReady = false;
  async function learnerDetails() {
    try {
      return await request("GET", "/v1/web/student/details");
    } catch (_) { /* not signed in as the learner yet */ }
    try {
      await request("POST", "/v1/web/user/self");
      return await request("GET", "/v1/web/student/details");
    } catch (_) {
      return null;
    }
  }

  function fillLearner(data) {
    byId("accLearnerBox").hidden = !data;
    if (!data) return;
    const d = data.details;
    const levels = data.skill_levels || {};
    byId("accLevelListening").value = levels.listening || "A1";
    byId("accLevelReading").value = levels.reading || "A1";
    byId("accLevelGrammar").value = levels.grammar || "A1";
    byId("accLevelSpeakingWriting").value = levels.speaking_writing || "A1";
    byId("accGrade").value = d.grade || "";
    byId("accAttributes").value = d.attributes || "";
    byId("accConversation").value = d.conversation_style || "";
    byId("accResponse").value = d.response_style || "";
    byId("accSample").value = d.level_sample || "";
    byId("accFree").value = d.free_text || "";
  }

  async function saveLearner() {
    const nullIfEmpty = (value) => value || null;
    await request("PUT", "/v1/web/student/details", {
      age: byId("accAge").value ? Number(byId("accAge").value) : null,
      gender: nullIfEmpty(byId("accGender").value),
      grade: nullIfEmpty(byId("accGrade").value.trim()),
      attributes: byId("accAttributes").value.trim(),
      conversation_style: nullIfEmpty(byId("accConversation").value),
      response_style: nullIfEmpty(byId("accResponse").value),
      level_sample: byId("accSample").value.trim(),
      free_text: byId("accFree").value.trim(),
    });
    await request("PUT", "/v1/web/student/skill-levels", {
      listening: byId("accLevelListening").value,
      reading: byId("accLevelReading").value,
      grammar: byId("accLevelGrammar").value,
      speaking_writing: byId("accLevelSpeakingWriting").value,
    });
  }

  // The photo shown in the personal-details form. Only a change is sent when the form is saved.
  let photoDraft = "";
  let photoChanged = false;
  function setPhoto(src) {
    photoDraft = src || "";
    photoChanged = false;
    paintAvatar(byId("accAvatar"), photoDraft);
  }

  // Wires the two account forms once, on the first page that shows them. onSaved gets the saved profile.
  // ----- Choosing a teacher: the learner enters the teacher's code, checks the name, and confirms -----

  async function loadTeacher() {
    const state = await request("GET", "/v1/web/user/teacher");
    const hasTeacher = Boolean(state.teacher);
    show(byId("accTeacherCurrent"), hasTeacher);
    show(byId("accTeacherChoose"), !hasTeacher);
    if (hasTeacher) byId("accTeacherName").textContent = state.teacher.name;
    const own = await request("GET", "/v1/web/user/referrals");
    byId("accTeacherOwnCode").textContent = own.code;
  }

  async function openTeacherDialog() {
    const dialog = byId("accTeacherDialog");
    showError(byId("accTeacherError"), "");
    show(byId("accTeacherOk"), false);
    show(byId("accTeacherFound"), false);
    byId("accTeacherCode").value = "";
    byId("accTeacherConfirm").checked = false;
    byId("accTeacherSave").disabled = true;
    dialog.showModal();
    try {
      await loadTeacher();
    } catch (err) {
      showError(byId("accTeacherError"), err.message);
    }
  }

  let foundTeacherCode = "";

  async function checkTeacherCode() {
    showError(byId("accTeacherError"), "");
    show(byId("accTeacherFound"), false);
    foundTeacherCode = byId("accTeacherCode").value.trim();
    try {
      const found = await request("POST", "/v1/web/user/teacher/lookup", { code: foundTeacherCode });
      byId("accTeacherFoundName").textContent = found.teacher.name;
      byId("accTeacherConfirm").checked = false;
      byId("accTeacherSave").disabled = true;
      show(byId("accTeacherFound"), true);
    } catch (err) {
      showError(byId("accTeacherError"), err.message);
    }
  }

  async function saveTeacher() {
    showError(byId("accTeacherError"), "");
    try {
      await request("PUT", "/v1/web/user/teacher", { code: foundTeacherCode, confirm: true });
      show(byId("accTeacherOk"), true);
      byId("accTeacherOk").textContent = isEnglish() ? "Your teacher is saved." : "مربی شما ثبت شد.";
      await loadTeacher();
    } catch (err) {
      showError(byId("accTeacherError"), err.message);
    }
  }

  async function removeTeacher() {
    showError(byId("accTeacherError"), "");
    try {
      await request("DELETE", "/v1/web/user/teacher");
      show(byId("accTeacherOk"), true);
      byId("accTeacherOk").textContent = isEnglish() ? "You no longer have a teacher." : "مربی شما حذف شد.";
      await loadTeacher();
    } catch (err) {
      showError(byId("accTeacherError"), err.message);
    }
  }

  function setupTeacherForm() {
    byId("accTeacherCheck").addEventListener("click", checkTeacherCode);
    byId("accTeacherConfirm").addEventListener("change", (event) => {
      byId("accTeacherSave").disabled = !event.target.checked;
    });
    byId("accTeacherSave").addEventListener("click", saveTeacher);
    byId("accTeacherRemove").addEventListener("click", removeTeacher);
  }

  function setupAccountForms(onSaved) {
    setupTeacherForm();
    document.querySelectorAll("#accInfoDialog [data-close], #accPasswordDialog [data-close], #accSignOutDialog [data-close], #accTeacherDialog [data-close]").forEach((button) => {
      button.addEventListener("click", () => button.closest("dialog").close());
    });
    // A click on the grey area outside a dialog closes it. Clicks inside the box have another target.
    document.querySelectorAll("dialog.account-dialog").forEach((dialog) => {
      dialog.addEventListener("click", (event) => {
        if (event.target === dialog) dialog.close();
      });
    });
    byId("accSignOutConfirm").addEventListener("click", async () => {
      const run = pendingSignOut;
      pendingSignOut = null;
      if (!run) return;
      try {
        await run();
      } catch (err) {
        showError(byId("accSignOutError"), err.message);
      }
    });
    byId("accAvatarPick").addEventListener("click", () => byId("accAvatarFile").click());
    byId("accAvatarRemove").addEventListener("click", () => {
      photoDraft = "";
      photoChanged = true;
      paintAvatar(byId("accAvatar"), "");
    });
    byId("accAvatarFile").addEventListener("change", async (event) => {
      const file = event.target.files[0];
      event.target.value = "";
      showError(byId("accInfoError"), "");
      try {
        photoDraft = await readPhoto(file);
        photoChanged = true;
        paintAvatar(byId("accAvatar"), photoDraft);
      } catch (err) {
        showError(byId("accInfoError"), err.message);
      }
    });
    byId("accInfoForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      showError(byId("accInfoError"), "");
      show(byId("accInfoOk"), false);
      const body = {
        full_name: byId("accName").value.trim(),
        email: byId("accEmail").value.trim(),
        age: byId("accAge").value ? Number(byId("accAge").value) : null,
        gender: byId("accGender").value || null,
        goal: byId("accGoal").value || null,
      };
      if (photoChanged) body.avatar = photoDraft;
      try {
        const saved = await request("PUT", "/v1/web/user/profile", body);
        if (learnerReady) await saveLearner();
        onSaved(saved);
        setPhoto(saved.avatar);
        byId("accInfoOk").textContent = isEnglish() ? "Saved." : "ذخیره شد.";
        show(byId("accInfoOk"), true);
      } catch (err) {
        showError(byId("accInfoError"), err.message);
      }
    });
    byId("accPasswordForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      showError(byId("accPwError"), "");
      show(byId("accPwOk"), false);
      if (byId("accPwNew").value !== byId("accPwRepeat").value) {
        showError(byId("accPwError"), isEnglish() ? "The two new passwords do not match." : "دو رمز جدید یکسان نیست.");
        return;
      }
      try {
        await request("POST", "/v1/web/user/password", {
          current_password: byId("accPwCurrent").value,
          new_password: byId("accPwNew").value,
        });
        event.target.reset();
        byId("accPwOk").textContent = isEnglish() ? "Your new password is saved." : "رمز جدید ذخیره شد.";
        show(byId("accPwOk"), true);
      } catch (err) {
        showError(byId("accPwError"), err.message);
      }
    });
  }

  // An adult opens their own learning from the menu. The server sets the learner sign-in, then the learner page opens.
  async function startOwnLearning(event) {
    event.preventDefault();
    try {
      await request("POST", "/v1/web/user/self");
      location.href = "/student";
    } catch (err) {
      window.alert(err.message);
    }
  }

  // The action waits until the visitor confirms in the dialog, so a mis-tap does not sign them out.
  let pendingSignOut = null;
  function askSignOut(question, action) {
    byId("accSignOutQuestion").textContent = question;
    show(byId("accSignOutError"), false);
    pendingSignOut = action;
    byId("accSignOutDialog").showModal();
  }

  async function signOut(signedIn) {
    await Promise.all(signedIn.map((role) => request("POST", `/v1/web/logout?role=${role}`).catch(() => {})));
    location.href = "/";
  }

  // Ends every sign-in for this adult and their own learning, on every device. Only the adult can do this.
  async function signOutEverywhere() {
    await request("POST", "/v1/web/user/logout-all").catch(() => {});
    location.href = "/";
  }

  // Set by each build of the menu. The document-level listeners are added only once, in initSiteHeader.
  let closeAccountMenu = () => {};
  // Set by each build of the header, so the one-time form wiring always updates the current name and photo.
  let onProfileSaved = () => {};
  let headerWired = false;

  // The profile photo in the header. Its menu holds the account items and sign-out.
  function buildAccountMenu(signedIn, avatarSrc) {
    const wrap = el("div", "account-menu");
    const avatar = el("button", "avatar-btn");
    avatar.type = "button";
    avatar.setAttribute("aria-haspopup", "menu");
    avatar.setAttribute("aria-expanded", "false");
    paintAvatar(avatar, avatarSrc);

    const list = el("div", "account-menu-list");
    list.setAttribute("role", "menu");
    const close = () => {
      list.classList.remove("is-open");
      avatar.setAttribute("aria-expanded", "false");
    };
    const addItem = (fa, en, action, extraClass) => {
      const item = labelled("button", extraClass ? `account-item ${extraClass}` : "account-item", null, fa, en);
      item.type = "button";
      item.setAttribute("role", "menuitem");
      item.addEventListener("click", () => {
        close();
        action();
      });
      list.appendChild(item);
    };
    addItem("اطلاعات شخصی", "Personal details", openPersonalDetails);
    addItem("تعیین مربی", "Choose a teacher", openTeacherDialog);
    addItem("تغییر رمز عبور", "Change password", () => byId("accPasswordDialog").showModal());
    addItem("درخواست‌های شما", "Your requests", () => { location.href = "/requests"; });
    addItem("کد معرف من", "My referral code", () => { location.href = "/referrals"; });
    addItem("پرداخت‌های شما", "Your payments", () => {
      location.href = signedIn.includes("parent") ? "/payments" : "/student?tab=payments";
    });
    list.appendChild(el("div", "account-sep"));
    addItem("خروج", "Sign out", () => askSignOut(
      isEnglish() ? "Are you sure you want to sign out?" : "آیا برای خروج اطمینان دارید؟",
      () => signOut(signedIn),
    ));
    if (signedIn.includes("parent")) {
      addItem("خروج از همه‌ی دستگاه‌ها", "Sign out of all devices", () => askSignOut(
        isEnglish()
          ? "Are you sure you want to sign out of all devices? You will need your password to sign in again."
          : "آیا برای خروج از همه‌ی دستگاه‌ها اطمینان دارید؟ دوباره باید با رمز عبور وارد شوید.",
        signOutEverywhere,
      ), "danger");
    }

    avatar.addEventListener("click", (event) => {
      event.stopPropagation();
      const open = !list.classList.contains("is-open");
      list.classList.toggle("is-open", open);
      avatar.setAttribute("aria-expanded", String(open));
    });
    closeAccountMenu = close;
    wrap.append(avatar, list);
    return { wrap, avatar };
  }

  // Shows who is signed in on this browser. A visitor who is signed out keeps the static "ورود" menu.
  // A sign-in that is missing is normal here, so each check only decides which buttons appear.
  async function initSiteHeader() {
    const box = document.getElementById("siteActions");
    if (!box) return;
    const signedIn = [];
    let greeting = "";
    let teaches = 0;
    for (const role of ["parent", "student"]) {
      try {
        const me = await request("GET", `/v1/web/me?role=${role}`);
        signedIn.push(role);
        greeting = greeting || me.name;
        if (role === "parent") teaches = me.students || 0;
      } catch (_) { /* not signed in to this area */ }
    }
    if (!signedIn.length) return;

    // A signed-in visitor starts on the lesson page, not on the public home page. The logo and the home link go there too.
    const memberHome = "/student";
    if (location.pathname === "/") {
      location.replace(memberHome);
      return;
    }
    document.querySelectorAll('.site-brand, .site-nav a[href="/"]').forEach((link) => link.setAttribute("href", memberHome));

    let profile = { avatar: "" };
    try {
      profile = await request("GET", "/v1/web/user/profile");
    } catch (_) { /* the header still works without the photo */ }

    box.replaceChildren();
    // Only the name, then the photo. The photo opens the account menu.
    const nameNode = el("span", "site-greeting", greeting);
    box.appendChild(nameNode);
    const menu = buildAccountMenu(signedIn, profile.avatar);
    box.appendChild(menu.wrap);
    box.dataset.state = "member";

    onProfileSaved = (saved) => {
      if (signedIn.includes("parent")) nameNode.textContent = saved.name;
      paintAvatar(menu.avatar, saved.avatar);
    };
    if (!headerWired) {
      headerWired = true;
      setupAccountForms((saved) => onProfileSaved(saved));
      // Clicking outside the menu, or pressing Escape, closes it.
      document.addEventListener("click", (event) => {
        if (!event.target.closest(".account-menu")) closeAccountMenu();
      });
      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeAccountMenu();
      });
    }

    // The side menu of the signed-in area. One level only; the learning tabs sit under «آموزش من».
    const path = location.pathname;
    const tool = new URLSearchParams(location.search).get("tab");
    const onLearnerPage = path === "/student";
    const learnerSignedIn = signedIn.includes("student");
    const items = [];
    items.push({ href: "/student", fa: "آموزش من", en: "My learning", active: onLearnerPage && tool !== "payments" && tool !== "help", startOwn: !learnerSignedIn, learning: true });
    if (signedIn.includes("parent")) {
      items.push({ href: "/plan", fa: "پلن و اعتبار", en: "Plan and credit", active: path === "/plan" });
      items.push({ href: "/level", fa: "تعیین سطح", en: "Set level", active: path === "/level" });
    } else {
    }
    items.push({ href: "/student?tab=help", fa: "کمک‌آموزشی", en: "Help", active: onLearnerPage && tool === "help" });
    // "My students" appears once at least one adult has chosen this account as their teacher.
    if (signedIn.includes("parent") && teaches > 0) {
      items.push({ href: "/students", fa: "دانش‌آموزان من", en: "My students", active: path === "/students" });
    }

    const nav = document.getElementById("memberNav");
    const header = document.querySelector(".site-header");
    if (header) header.dataset.member = String(signedIn.length > 0);
    if (nav) {
      nav.replaceChildren();
      items.forEach((item) => {
        const group = el("div", "side-group");
        const link = labelled("a", "side-item", item.href, item.fa, item.en);
        if (item.active) link.setAttribute("aria-current", "page");
        if (item.startOwn) link.addEventListener("click", startOwnLearning);
        group.appendChild(link);
        if (item.learning) {
          const collapse = learningMenu(onLearnerPage && learnerSignedIn);
          const chevron = el("span", "side-chevron");
          link.appendChild(chevron);
          const isOpen = () => !collapse.classList.contains("is-closed");
          link.setAttribute("aria-expanded", String(isOpen()));
          // The chevron always opens and closes the list. On the learner page the label does too, without a reload.
          link.addEventListener("click", (event) => {
            const onChevron = event.target.closest(".side-chevron");
            if (!onChevron && !onLearnerPage) return;
            event.preventDefault();
            collapse.classList.toggle("is-closed", isOpen());
            link.setAttribute("aria-expanded", String(isOpen()));
            rememberLearningOpen(isOpen());
          });
          group.appendChild(collapse);
        }
        nav.appendChild(group);
      });
      nav.hidden = !items.length;
    }
  }

  // The learning tabs, shown under «آموزش من» on the learner page. Each entry clicks the page's own tab,
  // so the lesson, report and progress sections stay where they are. The entries follow the page's active tab.
  let learnObserver = null;
  // The visitor's own choice of open or closed is remembered in this browser. Without a choice, the list is open on a computer and closed on a phone.
  const LEARNING_OPEN_KEY = "zaban-learning-open";
  function learningListOpen() {
    try {
      const saved = localStorage.getItem(LEARNING_OPEN_KEY);
      if (saved !== null) return saved === "open";
    } catch (_) { /* storage can be blocked; the default applies */ }
    return !window.matchMedia("(max-width: 760px)").matches;
  }
  function rememberLearningOpen(open) {
    try {
      localStorage.setItem(LEARNING_OPEN_KEY, open ? "open" : "closed");
    } catch (_) { /* the choice lasts only for this page then */ }
  }
  const LEARNING_TABS = [
    ["lesson", "جلسه"], ["accent", "لهجه"], ["report", "گزارش من"], ["progress", "پیشرفت"],
    ["profile", "اطلاعات من"], ["test", "خودت رو محک بزن"],
  ];

  // The learning list under «آموزش من». On the learner page its entries click the page's own tabs and follow the active tab.
  // Elsewhere each entry opens the learner page on that tab. It starts open on the learner page of a desktop, and closed otherwise.
  function learningMenu(live) {
    const collapse = el("div", "side-collapse");
    const box = el("div", "side-sub");
    const list = el("div", "side-list");
    box.appendChild(list);
    collapse.appendChild(box);
    const tabs = live ? document.querySelector("#appView .tabs") : null;
    if (tabs) {
      const entries = [];
      // Payments and help have their own main items, so they are left out of this list.
      tabs.querySelectorAll('.tab:not([data-tab="payments"]):not([data-tab="help"])').forEach((tab) => {
        const entry = el("button", "side-sub-item", tab.textContent.trim());
        entry.type = "button";
        entry.addEventListener("click", () => tab.click());
        entries.push([tab, entry]);
        list.appendChild(entry);
      });
      const sync = () => entries.forEach(([tab, entry]) => {
        entry.textContent = tab.textContent.trim();
        entry.classList.toggle("is-active", tab.classList.contains("is-active"));
      });
      sync();
      if (learnObserver) learnObserver.disconnect();
      learnObserver = new MutationObserver(sync);
      learnObserver.observe(tabs, { subtree: true, attributes: true, childList: true, characterData: true });
    } else {
      const current = new URLSearchParams(location.search).get("tab") || "lesson";
      LEARNING_TABS.forEach(([key, fa]) => {
        const entry = labelled("a", "side-sub-item", key === "lesson" ? "/student" : `/student?tab=${key}`, fa, fa);
        entry.classList.toggle("is-active", location.pathname === "/student" && current === key);
        list.appendChild(entry);
      });
    }
    collapse.classList.toggle("is-closed", !learningListOpen());
    return collapse;
  }

  // Blocks marked .reveal rise in once they reach the screen. Each one animates only once.
  function initReveal() {
    const items = document.querySelectorAll(".reveal");
    if (!items.length) return;
    if (!("IntersectionObserver" in window)) {
      items.forEach((node) => node.classList.add("is-visible"));
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.12 });
    items.forEach((node) => observer.observe(node));
  }

  return {
    request, friendly, pageRole, parseUtc, locale, currentLang, fmtDate, fmtDateTime, el, show, showError, showDevCode, codeTimer, initLang, initTheme, initReveal,
    initSiteHeader, STATUS_FA, SUGGESTION_FA, LEVEL_FA, SESSION_FA,
  };
})();

// Every page gets the language switch and the sign-in state of the header.
document.addEventListener("DOMContentLoaded", () => {
  Z.initLang();
  Z.initTheme();
  Z.initReveal();
  Z.initSiteHeader();
});
