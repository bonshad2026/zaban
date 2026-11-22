(() => {
  // The learner page loads student-i18n.js, which adds Z.tr and Z.pick. The teacher's page has only common.js, so these fall back to Persian text.
  const tr = (fa) => (typeof Z.tr === "function" ? Z.tr(fa) : fa);
  const pick = (fa, en) => (typeof Z.pick === "function" ? Z.pick(fa, en) : (document.documentElement.lang === "en" ? en : fa));
  // The report view of a learner. The learner page and a teacher's student profile both use it, so the reports look the same.
  // Three blocks, top to bottom: the status (where the learner is), the level of each skill, and the list of reports.
  // The data comes in as one object: progress, partner (levels and criteria), items and onShowProgress.

  // The five skills in the order the progress page shows them. The icons are the ones the level page uses.
  const SKILLS = [
    { key: "listening", fa: "شنیداری", en: "Listening" },
    { key: "reading", fa: "خواندن", en: "Reading" },
    { key: "grammar", fa: "دستور و واژگان", en: "Grammar and vocabulary" },
    { key: "writing", fa: "نوشتاری", en: "Writing" },
    { key: "speaking", fa: "گفتاری", en: "Speaking" },
  ];
  const SKILL_ICONS = {
    listening: '<svg viewBox="0 0 24 24"><path d="M4 9v6h4l5 4V5L8 9H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/></svg>',
    reading: '<svg viewBox="0 0 24 24"><path d="M2 5h7a3 3 0 0 1 3 3v12a2 2 0 0 0-2-2H2z"/><path d="M22 5h-7a3 3 0 0 0-3 3v12a2 2 0 0 1 2-2h8z"/></svg>',
    grammar: '<svg viewBox="0 0 24 24"><path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16z"/><path d="M14 6l4 4"/></svg>',
    writing: '<svg viewBox="0 0 24 24"><path d="M6 3h9l4 4v14H6z"/><path d="M9 12h7M9 16h5"/></svg>',
    speaking: '<svg viewBox="0 0 24 24"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/></svg>',
  };
  // The five speaking criteria, each with a plain line icon in the same style as the skill icons.
  const CRITERION_ICONS = {
    range: '<svg viewBox="0 0 24 24"><path d="M4 5a2 2 0 0 1 2-2h13v15H6a2 2 0 0 0-2 2z"/><path d="M4 5v17"/></svg>',
    accuracy: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.5 2.5L16 9.5"/></svg>',
    fluency: '<svg viewBox="0 0 24 24"><path d="M2 12c2.5-4 5-4 7.5 0s5 4 7.5 0 4-3 5.5-1"/></svg>',
    interaction: '<svg viewBox="0 0 24 24"><path d="M4 5h10v7H8l-4 3z"/><path d="M14 9h6v7h-2l-3 2.5V16h-1z"/></svg>',
    coherence: '<svg viewBox="0 0 24 24"><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/></svg>',
  };
  const CRITERIA = [["range", "دامنه", "Range"], ["accuracy", "دقت", "Accuracy"], ["fluency", "روانی", "Fluency"], ["interaction", "تعامل", "Interaction"], ["coherence", "انسجام", "Coherence"]];

  // Where the learner is in the lesson path, with the progress bar and the button to the full progress view.
  function statusBlock(progress, onShowProgress) {
    const block = Z.el("section", "report-block");
    block.appendChild(Z.el("h2", null, tr("گزارش وضعیت")));
    if (!progress || progress.started === false || !progress.total) {
      block.appendChild(Z.el("p", "muted", tr("هنوز برنامه‌ای برای شما تعیین نشده است.")));
      return block;
    }
    const head = Z.el("div", "report-status-head");
    head.append(
      Z.el("strong", "", pick(`مرحله‌ی ${progress.current} از ${progress.total}`, `Step ${progress.current} of ${progress.total}`)),
      Z.el("span", "", `${progress.percent}٪`),
    );
    const meter = Z.el("div", "bar");
    const fill = Z.el("span");
    fill.style.width = `${Math.min(100, Math.max(0, progress.percent))}%`;
    meter.appendChild(fill);
    const button = Z.el("button", "ghost", tr("مشاهده جزئیات"));
    button.type = "button";
    button.addEventListener("click", () => onShowProgress && onShowProgress());
    block.append(head, meter, button);
    return block;
  }

  // One line per skill: the icon at the start, then the skill and its level on the same line.
  // Speaking also shows its five criteria inside its line, and takes the full width.
  function levelBlock(partner) {
    const block = Z.el("section", "report-block");
    block.appendChild(Z.el("h2", null, tr("گزارش سطح")));
    if (!partner || partner.started === false) {
      block.appendChild(Z.el("p", "muted", tr("سطح مهارت‌ها بعد از شروع یادگیری نشان داده می‌شود.")));
      return block;
    }
    const list = Z.el("div", "level-list");
    SKILLS.forEach((skill) => list.appendChild(skillRow(skill, partner)));
    block.appendChild(list);
    return block;
  }

  function skillIcon(skill) {
    const icon = Z.el("span", "skill-icon");
    icon.setAttribute("aria-hidden", "true");
    icon.innerHTML = SKILL_ICONS[skill.key];
    return icon;
  }

  function skillRow(skill, partner) {
    const item = Z.el("div", `level-item level-${skill.key}`);
    const row = Z.el("div", "level-row");
    row.append(skillIcon(skill), Z.el("strong", "level-name", pick(`سطح ${skill.fa}`, `${skill.en} level`)), Z.el("span", "level-chip", partner.levels?.[skill.key] || "A1"));
    item.appendChild(row);
    if (skill.key === "speaking") item.appendChild(speakingDetail(partner));
    return item;
  }

  // The five criteria sit inside the speaking line, in the same form as the skill lines: icon, name and level.
  function speakingDetail(partner) {
    const box = Z.el("div", "level-sub");
    CRITERIA.forEach(([key, fa, en]) => {
      const row = Z.el("div", `level-row level-criterion criterion-${key}`);
      const icon = Z.el("span", "skill-icon");
      icon.setAttribute("aria-hidden", "true");
      icon.innerHTML = CRITERION_ICONS[key];
      row.append(icon, Z.el("strong", "level-name", pick(fa, en)), Z.el("span", "level-chip", partner.criteria?.[key] || "A1"));
      box.appendChild(row);
    });
    return box;
  }

  // The button at the top of the page. It opens the newest analysis of the learner in the dialog.
  function analysisBar(analysis) {
    const bar = Z.el("div", "report-top");
    const button = Z.el("button", "ghost", tr("مشاهده وضعیت من"));
    button.type = "button";
    button.addEventListener("click", () => openAnalysis(analysis));
    bar.appendChild(button);
    return bar;
  }

  function openAnalysis(analysis) {
    const view = detailsDialog();
    view.title.textContent = tr("تحلیل وضعیت");
    const body = view.body;
    body.replaceChildren();
    if (!analysis || !analysis.text) {
      body.appendChild(Z.el("p", "muted", tr("تحلیل وضعیت هنوز ساخته نشده است. اگر مدل زبانی تنظیم نشده باشد، تحلیل ساخته نمی‌شود.")));
    } else {
      body.appendChild(Z.el("p", "muted", `${tr("آخرین به‌روزرسانی")}: ${Z.fmtDateTime(analysis.created_at)}`));
      body.appendChild(evaluationBlocks(analysis.text));
    }
    view.dialog.showModal();
  }

  function renderReport(box, data) {
    box.classList.add("report-stack");
    const blocks = [statusBlock(data.progress, data.onShowProgress), levelBlock(data.partner)];
    // The teacher's page still shows every report in one list. The learner's own report tab does not.
    if (data.items) blocks.push(reportList({ kind: "all", items: data.items }));
    // Only the learner's own page has an analysis; a teacher's view leaves it out.
    if (data.analysis !== undefined) blocks.unshift(analysisBar(data.analysis));
    box.replaceChildren(...blocks);
  }

  // The reports of one kind (lesson, talk or test) are listed inside the card that starts that kind. A row opens its details.
  const REPORT_LIST_TITLES = { lesson: "گزارش جلسه‌ها", talk: "گزارش گفتگوها", test: "گزارش آزمون‌ها" };
  const REPORT_TYPE_CHOICES = [["all", "همه"], ["lesson", "جلسه"], ["test", "آزمون"], ["talk", "گفتگو"]];
  const REPORT_TYPE_FA = { lesson: "جلسه", test: "آزمون", talk: "گفتگو" };
  const REPORT_STATUS_FA = { completed: "کامل شد", finished: "کامل شد", active: "در حال انجام", expired: "تمام شد" };
  const REPORT_CRITERIA_FA = { range: "دامنه", accuracy: "دقت", fluency: "روانی", interaction: "تعامل", coherence: "انسجام" };

  function reportMeta(item) {
    const duration = pick(`${item.duration_minutes} دقیقه`, `${item.duration_minutes} min`);
    return `${Z.fmtDateTime(item.date)} · ${duration} · ${tr(REPORT_STATUS_FA[item.status] || item.status)}`;
  }

  // The list of reports: a type filter, a date range, and pages of a size the learner chooses.
  const PAGE_SIZES = [10, 20, 50];

  const english = () => document.documentElement.lang === "en";
  const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
  const JALALI = new Intl.DateTimeFormat("en-u-ca-persian-nu-latn", { year: "numeric", month: "numeric", day: "numeric", timeZone: "UTC" });

  function jalaliOf(date) {
    const parts = Object.fromEntries(JALALI.formatToParts(date).map((part) => [part.type, part.value]));
    return { y: Number(parts.year), m: Number(parts.month), d: Number(parts.day) };
  }

  // The Gregorian date (UTC midnight) of a Jalali date, or null when that date does not exist.
  function jalaliToDate(y, m, d) {
    // The Jalali year starts in March of the Gregorian year y + 621. The search starts a year earlier and walks forward.
    const start = Date.UTC(y + 620, 2, 1);
    for (let i = 0; i < 800; i += 1) {
      const date = new Date(start + i * 86400000);
      const j = jalaliOf(date);
      if (j.y === y && j.m === m && j.d === d) return date;
    }
    return null;
  }

  // Reads a typed Jalali date such as ۱۴۰۵/۰۱/۰۱. Empty gives "", and text that is not a date gives null.
  function parseJalali(text) {
    const cleaned = text.trim()
      .replace(/[۰-۹]/g, (c) => String(PERSIAN_DIGITS.indexOf(c)))
      .replace(/[٠-٩]/g, (c) => String(c.charCodeAt(0) - 0x0660));
    if (!cleaned) return "";
    const match = cleaned.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})$/);
    if (!match) return null;
    const [y, m, d] = match.slice(1).map(Number);
    return { y, m, d };
  }

  // The Gregorian YYYY-MM-DD that the filter compares with. Empty gives "", and an invalid date gives null.
  function jalaliToIso(text) {
    const parsed = parseJalali(text);
    if (parsed === "" || parsed === null) return parsed;
    const date = jalaliToDate(parsed.y, parsed.m, parsed.d);
    return date ? date.toISOString().slice(0, 10) : null;
  }

  function formatJalali(y, m, d) {
    return `${y}/${String(m).padStart(2, "0")}/${String(d).padStart(2, "0")}`;
  }

  // The month and year title of the calendar, in Persian, for example «فروردین ۱۴۰۵».
  const JALALI_MONTH = new Intl.DateTimeFormat("fa-IR-u-ca-persian", { month: "long", year: "numeric", timeZone: "UTC" });
  const WEEKDAYS_FA = ["ش", "ی", "د", "س", "چ", "پ", "ج"];

  const CALENDAR_ICON = '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>';

  // The date range filter: one box that takes a range, typed or picked from the calendar, with a × inside that clears it.
  // Persian takes Jalali dates; English takes two calendar inputs (Gregorian). onChange(from, to) gets ISO dates, "" when cleared.
  function isoOf(jalali) {
    const date = jalali ? jalaliToDate(jalali.y, jalali.m, jalali.d) : null;
    return date ? date.toISOString().slice(0, 10) : "";
  }

  function dateRange(onChange) {
    const field = Z.el("div", "report-date");
    field.append(Z.el("span", "", tr("تاریخ")));
    const wrap = Z.el("div", "report-input report-range");
    const clear = Z.el("button", "report-date-clear", "×");
    clear.type = "button";
    clear.setAttribute("aria-label", tr("پاک کردن تاریخ"));

    if (english()) {
      const from = Z.el("input");
      from.type = "date";
      from.setAttribute("aria-label", tr("از تاریخ"));
      const to = Z.el("input");
      to.type = "date";
      to.setAttribute("aria-label", tr("تا تاریخ"));
      const emit = () => onChange(from.value, to.value);
      from.addEventListener("change", emit);
      to.addEventListener("change", emit);
      clear.addEventListener("click", () => {
        from.value = "";
        to.value = "";
        emit();
      });
      wrap.append(from, Z.el("span", "muted", "–"), to, clear);
      field.append(wrap);
      return field;
    }

    const input = Z.el("input");
    input.type = "text";
    input.inputMode = "numeric";
    input.placeholder = tr("از تاریخ تا تاریخ");
    input.setAttribute("aria-label", tr("بازه‌ی تاریخ"));
    const toggle = Z.el("button", "report-cal-btn");
    toggle.type = "button";
    toggle.setAttribute("aria-label", tr("تقویم"));
    toggle.title = tr("تقویم");
    toggle.innerHTML = CALENDAR_ICON;
    const error = Z.el("span", "error", tr("تاریخ را به شکل ۱۴۰۵/۰۱/۰۱ وارد کنید."));
    error.hidden = true;
    const panel = Z.el("div", "report-calendar");
    panel.hidden = true;
    wrap.append(input, clear, toggle);
    field.append(wrap, error, panel);

    // The chosen range in Jalali dates. A drag over the calendar picks the whole range at once, from the day it starts on to the day it ends on.
    let range = { start: null, end: null };
    let shown = null;
    // The first day clicked is the anchor; the second click ends the range, whichever of the two is earlier.
    let anchor = null;
    const order = (d) => d.y * 10000 + d.m * 100 + d.d;

    function show() {
      const { start, end } = range;
      if (!start) input.value = "";
      else if (order(start) === order(end)) input.value = formatJalali(start.y, start.m, start.d);
      else input.value = `${formatJalali(start.y, start.m, start.d)} تا ${formatJalali(end.y, end.m, end.d)}`;
    }

    function emit() {
      onChange(isoOf(range.start), isoOf(range.end));
    }

    // Writes the range into the box, sends it to the list and closes the calendar.
    function finish() {
      show();
      emit();
      panel.hidden = true;
    }

    function dayOf(cell) {
      const key = Number(cell.dataset.key);
      return { y: Math.floor(key / 10000), m: Math.floor((key % 10000) / 100), d: key % 100 };
    }

    // Highlights the days inside the range and marks its two ends.
    function paintDays() {
      const { start, end } = range;
      panel.querySelectorAll("[data-key]").forEach((cell) => {
        const key = Number(cell.dataset.key);
        const inside = start && end && key >= order(start) && key <= order(end);
        const edge = (start && key === order(start)) || (end && key === order(end));
        cell.classList.toggle("is-in-range", Boolean(inside));
        cell.setAttribute("aria-pressed", String(Boolean(edge)));
      });
    }

    function shiftMonth(delta) {
      let { y, m } = shown;
      m += delta;
      if (m < 1) { m = 12; y -= 1; }
      if (m > 12) { m = 1; y += 1; }
      shown = { y, m };
      renderPanel();
    }

    function renderPanel() {
      panel.replaceChildren();
      const head = Z.el("div", "report-cal-head");
      const prev = Z.el("button", "ghost report-cal-nav", "‹");
      prev.type = "button";
      prev.setAttribute("aria-label", tr("ماه قبل"));
      prev.addEventListener("click", () => shiftMonth(-1));
      const next = Z.el("button", "ghost report-cal-nav", "›");
      next.type = "button";
      next.setAttribute("aria-label", tr("ماه بعد"));
      next.addEventListener("click", () => shiftMonth(1));
      const first = jalaliToDate(shown.y, shown.m, 1);
      const nextFirst = shown.m === 12 ? jalaliToDate(shown.y + 1, 1, 1) : jalaliToDate(shown.y, shown.m + 1, 1);
      const days = Math.round((nextFirst - first) / 86400000);
      head.append(next, Z.el("strong", "", JALALI_MONTH.format(first)), prev);
      const grid = Z.el("div", "report-cal-grid");
      WEEKDAYS_FA.forEach((day) => grid.appendChild(Z.el("span", "report-cal-week", day)));
      // Saturday is the first day of the week in the Persian calendar.
      const offset = (first.getUTCDay() + 1) % 7;
      for (let i = 0; i < offset; i += 1) grid.appendChild(Z.el("span"));
      for (let d = 1; d <= days; d += 1) {
        const cell = Z.el("button", "report-cal-day", String(d));
        cell.type = "button";
        cell.dataset.key = String(order({ y: shown.y, m: shown.m, d }));
        grid.appendChild(cell);
      }
      // The grid is redrawn on each month, so its click handler is added here.
      grid.addEventListener("click", (event) => {
        const cell = event.target.closest("[data-key]");
        if (!cell) return;
        const day = dayOf(cell);
        if (!anchor) {
          anchor = day;
          range = { start: day, end: day };
          paintDays();
          return;
        }
        range = order(anchor) <= order(day) ? { start: anchor, end: day } : { start: day, end: anchor };
        anchor = null;
        finish();
      });
      panel.append(head, grid);
      paintDays();
    }

    // A typed range such as ۱۴۰۵/۰۱/۰۱ تا ۱۴۰۵/۰۱/۳۰ is read when the box is left. Empty clears it.
    input.addEventListener("change", () => {
      const pieces = input.value.split(/\s*(?:تا|-|–)\s*/).map((piece) => piece.trim()).filter(Boolean);
      if (!pieces.length) {
        range = { start: null, end: null };
        error.hidden = true;
        emit();
        return;
      }
      const dates = pieces.map(parseJalali);
      const valid = dates.length <= 2 && dates.every((d) => d && jalaliToDate(d.y, d.m, d.d));
      error.hidden = valid;
      if (!valid) return;
      const [a, b] = dates.length === 1 ? [dates[0], dates[0]] : dates;
      range = order(a) <= order(b) ? { start: a, end: b } : { start: b, end: a };
      show();
      emit();
    });

    // The × only clears the range: it does not open the calendar.
    clear.addEventListener("click", (event) => {
      event.stopPropagation();
      range = { start: null, end: null };
      anchor = null;
      show();
      error.hidden = true;
      panel.hidden = true;
      emit();
    });

    // The calendar opens from the box itself, or from its calendar button. Picking a day inside it closes it.
    function openPanel() {
      const now = jalaliOf(new Date());
      const base = range.start || now;
      shown = { y: base.y, m: base.m };
      anchor = null;
      renderPanel();
      panel.hidden = false;
    }
    toggle.addEventListener("click", () => {
      if (panel.hidden) openPanel();
      else panel.hidden = true;
    });
    input.addEventListener("click", () => {
      if (panel.hidden) openPanel();
    });
    document.addEventListener("click", (event) => {
      if (!field.contains(event.target)) panel.hidden = true;
    });
    return field;
  }

  // The list of reports. kind is "lesson", "talk" or "test" for the card that starts it, which has no type filter and no type tag.
  // kind "all" (the teacher's page) lists every kind and has a type filter. onBack, when given, returns to the card.
  function reportList({ kind, items, onBack, studentId, onResume, onReload }) {
    const wrap = Z.el("section", "report-block report-list");
    const head = Z.el("div", "d-flex justify-content-between align-items-center gap-2 flex-wrap");
    head.appendChild(Z.el("h2", null, tr(REPORT_LIST_TITLES[kind] || "گزارش‌ها")));
    if (onBack) {
      const close = Z.el("button", "btn-close");
      close.type = "button";
      close.setAttribute("aria-label", tr("بستن"));
      close.addEventListener("click", onBack);
      head.appendChild(close);
    }
    wrap.appendChild(head);
    if (!items.length) {
      wrap.appendChild(Z.el("p", "muted", tr(kind === "all" ? "هنوز گزارشی ثبت نشده است." : "گزارشی برای شما ثبت نشده است.")));
      return wrap;
    }
    const state = { type: "all", from: "", to: "", size: PAGE_SIZES[0], page: 1 };
    // The buttons that change a report need the learner's id and the page's own actions. The teacher's page has none.
    const ctx = studentId ? { studentId, onResume, onReload } : null;

    const typeButtons = [];
    if (kind === "all") {
      const filters = Z.el("div", "report-filter");
      REPORT_TYPE_CHOICES.forEach(([type, fa]) => {
        const button = Z.el("button", "ghost", tr(fa));
        button.type = "button";
        button.addEventListener("click", () => {
          state.type = type;
          state.page = 1;
          paint();
        });
        filters.appendChild(button);
        typeButtons.push([type, button]);
      });
      wrap.appendChild(filters);
    }

    // One line: the date range, then the number of items per page.
    const bar = Z.el("div", "report-bar");
    const range = dateRange((from, to) => {
      state.from = from;
      state.to = to;
      state.page = 1;
      paint();
    });
    const sizeField = Z.el("label", "report-size", tr("تعداد آیتم"));
    const sizeSelect = Z.el("select");
    PAGE_SIZES.forEach((size) => {
      const option = Z.el("option", "", String(size));
      option.value = String(size);
      sizeSelect.appendChild(option);
    });
    sizeSelect.addEventListener("change", () => {
      state.size = Number(sizeSelect.value);
      state.page = 1;
      paint();
    });
    sizeField.appendChild(sizeSelect);
    bar.append(range, sizeField);

    const rows = Z.el("div", "report-rows");
    const pager = Z.el("div", "report-pager");
    const prev = Z.el("button", "ghost", tr("قبلی"));
    prev.type = "button";
    prev.addEventListener("click", () => {
      state.page -= 1;
      paint();
    });
    const next = Z.el("button", "ghost", tr("بعدی"));
    next.type = "button";
    next.addEventListener("click", () => {
      state.page += 1;
      paint();
    });
    const info = Z.el("span", "muted");
    pager.append(prev, info, next);

    wrap.append(bar, rows, pager);

    // A report matches when its type is chosen (or all) and its date is inside the range, if one is set.
    function matches(item) {
      if (state.type !== "all" && item.type !== state.type) return false;
      const when = Z.parseUtc(item.date);
      if (state.from && when < new Date(`${state.from}T00:00:00`)) return false;
      if (state.to && when > new Date(`${state.to}T23:59:59.999`)) return false;
      return true;
    }

    function paint() {
      typeButtons.forEach(([type, button]) => button.setAttribute("aria-pressed", String(type === state.type)));
      const shown = items.filter(matches);
      const pages = Math.max(1, Math.ceil(shown.length / state.size));
      state.page = Math.min(Math.max(1, state.page), pages);
      const start = (state.page - 1) * state.size;
      rows.replaceChildren();
      if (!shown.length) {
        rows.appendChild(Z.el("p", "muted", tr("در این بازه گزارشی نیست.")));
      }
      shown.slice(start, start + state.size).forEach((item) => rows.appendChild(reportRow(item, kind === "all", ctx)));
      info.textContent = pick(`صفحه ${state.page} از ${pages}`, `Page ${state.page} of ${pages}`);
      prev.disabled = state.page <= 1;
      next.disabled = state.page >= pages;
    }

    paint();
    return wrap;
  }

  const REPORT_STATE_FA = { active: "در حال انجام", completed: "کامل شده", unevaluated: "ارزیابی نشده" };
  const RESUME_FA = { lesson: "تکمیل جلسه", talk: "تکمیل گفتگو", test: "تکمیل آزمون" };
  const EVALUATE_NOTICE = {
    impossible: "متاسفانه برای این مورد امکان ارزیابی وجود ندارد. پیام کافی برای ارزیابی ثبت نشده است.",
    plan: "توکن‌های پلن شما برای ارزیابی کافی نیست. برای ادامه، پلن خود را تمدید کنید.",
    failed: "ارزیابی انجام نشد. اتصال اینترنت را بررسی کنید و دوباره تلاش کنید.",
  };

  // A short message in the details window, for example when a report cannot be evaluated.
  function showNotice(text) {
    const view = detailsDialog();
    view.title.textContent = tr("ارزیابی");
    view.body.replaceChildren(Z.el("p", null, tr(text)));
    view.dialog.showModal();
  }

  // Makes the evaluation of an unevaluated report now. When it is written, the list is reloaded and the evaluation opens.
  async function evaluateItem(item, button, ctx) {
    const label = button.textContent;
    button.disabled = true;
    button.textContent = tr("در حال ارزیابی…");
    try {
      const data = await Z.request("POST", `/v1/students/${ctx.studentId}/reports/${item.type}/${item.id}/evaluate`);
      if (data.state === "completed") {
        const items = await ctx.onReload();
        openReport(items.find((row) => row.id === item.id) || item);
      } else {
        showNotice(EVALUATE_NOTICE[data.state] || EVALUATE_NOTICE.failed);
      }
    } catch (err) {
      showNotice(err.message);
    } finally {
      button.disabled = false;
      button.textContent = label;
    }
  }

  // One report row: its state, and the buttons that fit the state. The conversation button is there whenever the list can load it.
  // The type tag is shown only where the list holds every kind. Without a context (the teacher's page) only the evaluation opens.
  function reportRow(item, showType, ctx) {
    const row = Z.el("div", "report-row");
    const top = Z.el("div", "report-row-top");
    top.append(Z.el("strong", null, item.title));
    if (showType) top.append(Z.el("span", "report-type", tr(REPORT_TYPE_FA[item.type])));
    top.append(Z.el("span", "report-type", tr(REPORT_STATE_FA[item.state] || "")));
    const actions = Z.el("div", "d-flex flex-wrap gap-2");
    if (!ctx) {
      const evaluation = Z.el("button", "ghost report-open", tr("ارزیابی"));
      evaluation.type = "button";
      evaluation.addEventListener("click", () => openReport(item));
      actions.appendChild(evaluation);
    } else if (item.state === "active") {
      const resume = Z.el("button", "report-open", tr(RESUME_FA[item.type]));
      resume.type = "button";
      resume.addEventListener("click", () => ctx.onResume(item));
      actions.appendChild(resume);
    } else if (item.state === "unevaluated") {
      const evaluate = Z.el("button", "report-open", tr("ارزیابی"));
      evaluate.type = "button";
      evaluate.addEventListener("click", () => evaluateItem(item, evaluate, ctx));
      actions.appendChild(evaluate);
    } else {
      const evaluation = Z.el("button", "ghost report-open", tr("ارزیابی"));
      evaluation.type = "button";
      evaluation.addEventListener("click", () => openReport(item));
      actions.appendChild(evaluation);
    }
    if (ctx) {
      const transcript = Z.el("button", "ghost report-open", tr("اصل گفتگو"));
      transcript.type = "button";
      transcript.addEventListener("click", () => openTranscript(item, ctx.studentId));
      actions.appendChild(transcript);
    }
    row.append(top, Z.el("div", "muted", reportMeta(item)), actions);
    return row;
  }

  // The conversation of one report, as the learner and the teacher wrote it. It opens in the same details window.
  async function openTranscript(item, studentId) {
    const view = detailsDialog();
    view.title.textContent = item.title;
    view.body.replaceChildren(Z.el("p", "muted", tr("در حال بارگذاری گفتگو…")));
    view.dialog.showModal();
    try {
      const data = await Z.request("GET", `/v1/students/${studentId}/reports/${item.type}/${item.id}/messages`);
      if (!data.messages.length) {
        view.body.replaceChildren(Z.el("p", "muted", tr("برای این گزارش گفتگویی ذخیره نشده است.")));
        return;
      }
      view.body.replaceChildren(...data.messages.map((message) => {
        const line = Z.el("p", null);
        line.append(Z.el("strong", null, `${tr(message.role === "user" ? "شما" : "معلم")}: `), document.createTextNode(message.content));
        return line;
      }));
    } catch (err) {
      view.body.replaceChildren(Z.el("p", "error", err.message));
    }
  }

  // The stored evaluation is plain text: headings end with a colon, and the points under them are bullet or numbered lines.
  // It is shown as titled sections with bullets; any other line is a paragraph.
  function evaluationBlocks(text) {
    const wrap = Z.el("div", "evaluation");
    let list = null;
    let paragraph = null;
    text.split("\n").map((line) => line.trim()).filter(Boolean).forEach((line) => {
      const heading = line.match(/^(.{2,60}):$/);
      const point = line.match(/^(?:[-•*]|\d+[.)])\s+(.+)$/);
      if (heading) {
        wrap.appendChild(Z.el("h3", "evaluation-heading", heading[1]));
        list = null;
        paragraph = null;
      } else if (point) {
        if (!list) {
          list = Z.el("ul", "evaluation-list");
          wrap.appendChild(list);
        }
        list.appendChild(Z.el("li", null, point[1]));
        paragraph = null;
      } else {
        if (!paragraph) {
          paragraph = Z.el("p");
          wrap.appendChild(paragraph);
        }
        paragraph.textContent += (paragraph.textContent ? " " : "") + line;
        list = null;
      }
    });
    return wrap;
  }

  // The details of one report: its scores and the evaluation text stored for it.
  // The details dialog is made once, on first use, so every page that shows reports can open it.
  let details = null;
  function detailsDialog() {
    if (details) return details;
    const dialog = Z.el("dialog", "account-dialog account-dialog-wide");
    const title = Z.el("h2");
    const body = Z.el("div");
    const close = Z.el("button", "ghost", tr("بستن"));
    close.type = "button";
    close.addEventListener("click", () => dialog.close());
    const actions = Z.el("div", "dialog-actions");
    actions.appendChild(close);
    dialog.append(title, body, actions);
    document.body.appendChild(dialog);
    details = { dialog, title, body };
    return details;
  }

  function openReport(item) {
    const view = detailsDialog();
    view.title.textContent = item.title;
    const body = view.body;
    body.replaceChildren();
    body.appendChild(Z.el("p", "muted", `${tr(REPORT_TYPE_FA[item.type])} · ${reportMeta(item)}`));
    if (item.score !== null) {
      body.appendChild(Z.el("p", null, `${tr("امتیاز")}: ${Math.round(item.score)}`));
    }
    const levels = Object.entries(item.levels).filter(([, value]) => value);
    if (levels.length) {
      body.appendChild(Z.el("h3", null, tr("پنج معیار گفتاری")));
      const list = Z.el("ul", "plain");
      levels.forEach(([key, value]) => list.appendChild(Z.el("li", null, `${tr(REPORT_CRITERIA_FA[key])}: ${value}`)));
      body.appendChild(list);
    }
    body.appendChild(Z.el("h3", null, tr("ارزیابی")));
    body.appendChild(item.text ? evaluationBlocks(item.text) : Z.el("p", "muted", tr("برای این گزارش هنوز ارزیابی متنی ثبت نشده است.")));
    view.dialog.showModal();
  }

  // Fills `box` with the list of one kind. The caller shows the box and hides it again through onBack.
  function renderReportList(box, data) {
    box.replaceChildren(reportList(data));
  }

  window.ReportView = { render: renderReport, list: renderReportList };
})();
