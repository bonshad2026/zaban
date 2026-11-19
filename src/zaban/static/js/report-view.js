(() => {
  // The learner page loads student-i18n.js, which adds Z.tr and Z.pick. The teacher's page has only common.js, so these fall back to Persian text.
  const tr = (fa) => (typeof Z.tr === "function" ? Z.tr(fa) : fa);
  const pick = (fa, en) => (typeof Z.pick === "function" ? Z.pick(fa, en) : (document.documentElement.lang === "en" ? en : fa));
  // The report view of a learner. The learner page and a teacher's student profile both use it, so the reports look the same.
  // It shows the stats, the plan, the suggestion and the list of reports. A report opens its details in a dialog.

  function bar(label, percent, planned) {
    const wrap = Z.el("div");
    const top = Z.el("div", "bar-label");
    top.appendChild(Z.el("span", null, label));
    top.appendChild(Z.el("span", null, percent === null ? "—" : `${percent}٪`));
    const track = Z.el("div", "bar");
    const fill = Z.el("span", planned ? "planned" : "");
    fill.style.width = `${Math.min(100, Math.max(0, percent || 0))}%`;
    track.appendChild(fill);
    wrap.append(top, track);
    return wrap;
  }

  function stat(label, value) {
    const box = Z.el("div", "stat");
    box.append(Z.el("div", "label", label), Z.el("div", "value", value));
    return box;
  }

  function renderReport(box, report, detail, items) {
    box.replaceChildren();
    const level = detail.levels?.speaking;
    const levelText = level ? `${level} (${Z.LEVEL_FA[level]})` : tr("هنوز تعیین نشده");
    const completed = report.sessions.filter((s) => s.status === "completed").length;

    box.appendChild(Z.el("h2", null, tr("گزارش یادگیری من")));
    const stats = Z.el("div", "stats");
    stats.append(
      stat(tr("سطح من"), levelText),
      stat(tr("وضعیت من"), Z.STATUS_FA[report.status]),
      stat(tr("جلسه‌های کامل"), String(completed)),
    );
    box.appendChild(stats);

    if (report.plan) {
      box.appendChild(Z.el("h2", null, tr("پیشرفت نسبت به برنامه")));
      box.appendChild(bar(tr("طبق برنامه"), report.planned_percent, true));
      box.appendChild(bar(tr("میزان یادگیری تو"), report.actual_percent, false));
      box.appendChild(Z.el("p", "muted", pick(`پایان برنامه: ${Z.fmtDate(report.plan.end_date)}`, `The plan ends: ${Z.fmtDate(report.plan.end_date)}`)));
    }

    box.appendChild(Z.el("h2", null, tr("پیشنهاد برای ادامه")));
    box.appendChild(Z.el("p", "suggestion", Z.SUGGESTION_FA[report.status]));

    box.appendChild(reportList(items));
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
