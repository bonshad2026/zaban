(() => {
  // The learner page loads student-i18n.js, which adds Z.tr and Z.pick. The teacher's page has only common.js, so these fall back to Persian text.
  const tr = (fa) => (typeof Z.tr === "function" ? Z.tr(fa) : fa);
  const pick = (fa, en) => (typeof Z.pick === "function" ? Z.pick(fa, en) : (document.documentElement.lang === "en" ? en : fa));
  // The report view of a learner. The learner page and a teacher's student profile both use it, so the reports look the same.
  // Three blocks, top to bottom: the status (where the learner is), the level of each skill, and the list of reports.
  // The data comes in as one object: progress, partner (levels, criteria and phrases), items and onShowProgress.

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
  const PARTNER_CRITERIA = [["range", "دامنه", "Range"], ["accuracy", "دقت", "Accuracy"], ["fluency", "روانی", "Fluency"], ["interaction", "تعامل", "Interaction"], ["coherence", "انسجام", "Coherence"]];
  const PARTNER_PHRASE_STATUS = { seen: "دیده‌شده", used: "به‌کار رفته", mastered: "متسلط" };

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

  // One box per skill, the same as on the level page, but read only: the box shows the level and opens its details.
  function levelBlock(partner) {
    const block = Z.el("section", "report-block");
    block.appendChild(Z.el("h2", null, tr("گزارش سطح")));
    if (!partner || partner.started === false) {
      block.appendChild(Z.el("p", "muted", tr("سطح مهارت‌ها بعد از شروع یادگیری نشان داده می‌شود.")));
      return block;
    }
    const grid = Z.el("div", "skill-rows");
    SKILLS.forEach((skill) => grid.appendChild(skillCard(skill, partner)));
    block.appendChild(grid);
    return block;
  }

  function skillIcon(skill) {
    const icon = Z.el("span", "skill-icon");
    icon.setAttribute("aria-hidden", "true");
    icon.innerHTML = SKILL_ICONS[skill.key];
    return icon;
  }

  function skillCard(skill, partner) {
    const card = Z.el("article", `skill-card skill-${skill.key}`);
    const head = Z.el("div", "skill-head");
    head.append(skillIcon(skill), Z.el("strong", "skill-name", pick(skill.fa, skill.en)), Z.el("span", "level-chip", partner.levels?.[skill.key] || "A1"));
    const button = Z.el("button", "ghost skill-btn", tr("مشاهده جزئیات"));
    button.type = "button";
    button.addEventListener("click", () => openSkill(skill, partner));
    card.append(head, button);
    return card;
  }

  // The details of one skill, read only. Speaking also shows its five criteria and the phrases.
  function openSkill(skill, partner) {
    const view = detailsDialog();
    view.title.textContent = pick(skill.fa, skill.en);
    const body = view.body;
    body.replaceChildren();
    const head = Z.el("div", "skill-head");
    head.append(skillIcon(skill), Z.el("span", "level-chip", partner.levels?.[skill.key] || "A1"));
    body.appendChild(head);
    if (skill.key === "speaking") {
      body.appendChild(Z.el("h3", null, tr("پنج معیار گفتاری")));
      const criteria = Z.el("ul", "plain");
      PARTNER_CRITERIA.forEach(([key, fa, en]) => criteria.appendChild(Z.el("li", null, `${pick(fa, en)}: ${partner.criteria?.[key] || "—"}`)));
      body.appendChild(criteria);
      body.appendChild(Z.el("h3", null, tr("عبارت‌های من")));
      const phrases = Z.el("ul", "plain");
      const rows = (partner.phrases || []).map((p) => Z.el("li", null, `${p.text} — ${tr(PARTNER_PHRASE_STATUS[p.status] || p.status)}`));
      phrases.append(...(rows.length ? rows : [Z.el("li", "muted", tr("هنوز عبارتی ثبت نشده است."))]));
      body.appendChild(phrases);
    }
    view.dialog.showModal();
  }

  function renderReport(box, data) {
    box.replaceChildren(statusBlock(data.progress, data.onShowProgress), levelBlock(data.partner), reportList(data.items));
  }

  // Every report in one list: lessons, free talks and self-tests. The filter shows one kind; a row opens its details.
  const REPORT_KINDS = [["all", "همه"], ["lesson", "جلسه"], ["test", "آزمون"], ["talk", "گفتگو"]];
  const REPORT_TYPE_FA = { lesson: "جلسه", test: "آزمون", talk: "گفتگو" };
  const REPORT_STATUS_FA = { completed: "کامل شد", finished: "کامل شد", active: "در حال انجام", expired: "تمام شد" };
  const REPORT_CRITERIA_FA = { range: "دامنه", accuracy: "دقت", fluency: "روانی", interaction: "تعامل", coherence: "انسجام" };

  function reportMeta(item) {
    const duration = pick(`${item.duration_minutes} دقیقه`, `${item.duration_minutes} min`);
    return `${Z.fmtDateTime(item.date)} · ${duration} · ${tr(REPORT_STATUS_FA[item.status] || item.status)}`;
  }

  function reportList(items) {
    const wrap = Z.el("div", "report-list");
    wrap.appendChild(Z.el("h2", null, tr("گزارش‌های من")));
    if (!items.length) {
      wrap.appendChild(Z.el("p", "muted", tr("هنوز گزارشی ثبت نشده است. از تب «جلسه» یا «خودت رو محک بزن» شروع کن.")));
      return wrap;
    }
    const filters = Z.el("div", "report-filter");
    const rows = Z.el("div", "report-rows");
    const buttons = REPORT_KINDS.map(([kind, fa]) => {
      const button = Z.el("button", "ghost", tr(fa));
      button.type = "button";
      button.addEventListener("click", () => paint(kind));
      filters.appendChild(button);
      return [kind, button];
    });
    function paint(kind) {
      buttons.forEach(([key, button]) => button.setAttribute("aria-pressed", String(key === kind)));
      const shown = items.filter((item) => kind === "all" || item.type === kind);
      rows.replaceChildren();
      if (!shown.length) {
        rows.appendChild(Z.el("p", "muted", tr("در این بخش هنوز گزارشی نیست.")));
        return;
      }
      shown.forEach((item) => rows.appendChild(reportRow(item)));
    }
    wrap.append(filters, rows);
    paint("all");
    return wrap;
  }

  function reportRow(item) {
    const row = Z.el("div", "report-row");
    const top = Z.el("div", "report-row-top");
    top.append(Z.el("strong", null, item.title), Z.el("span", "report-type", tr(REPORT_TYPE_FA[item.type])));
    const open = Z.el("button", "ghost report-open", tr("مشاهده جزئیات"));
    open.type = "button";
    open.addEventListener("click", () => openReport(item));
    row.append(top, Z.el("div", "muted", reportMeta(item)), open);
    return row;
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

  window.ReportView = { render: renderReport };
})();
