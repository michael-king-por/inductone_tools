(function () {
  const BRAND = {
    blue: "#1794CE",
    grey900: "#101828",
    grey700: "#344054",
    grey600: "#475467",
    grey500: "#667085",
    border: "#EAECF0",
    surface: "#F9FAFB",
    font: "Arial, sans-serif",
  };

  function escapeHtml(value) {
    return frappe.utils.escape_html(value == null ? "" : String(value));
  }

  function statusTone(status) {
    const normalized = String(status || "").toLowerCase();
    if (["released", "reviewed", "approved", "accepted", "completed"].some((v) => normalized.includes(v))) {
      return { icon: "✓", color: "#027A48", bg: "#ECFDF3", text: "Ready" };
    }
    if (["rejected", "error", "cancelled"].some((v) => normalized.includes(v))) {
      return { icon: "!", color: "#B42318", bg: "#FEF3F2", text: "Needs correction" };
    }
    if (["awaiting", "submitted", "pending", "draft"].some((v) => normalized.includes(v))) {
      return { icon: "•", color: "#B54708", bg: "#FFFAEB", text: "Action pending" };
    }
    return { icon: "i", color: BRAND.blue, bg: "#EAF6FC", text: "Status" };
  }

  function checklistRows(rows) {
    return (rows || []).map((row) => {
      const done = !!row.done;
      const color = done ? "#027A48" : "#B54708";
      const bg = done ? "#ECFDF3" : "#FFFAEB";
      const icon = done ? "✓" : "•";
      return `
        <div style="display:flex;gap:10px;align-items:flex-start;padding:8px 0;border-top:1px solid ${BRAND.border}">
          <span aria-label="${done ? "complete" : "not complete"}" style="background:${bg};color:${color};width:20px;height:20px;border-radius:10px;display:inline-flex;align-items:center;justify-content:center;font-size:12px;font-weight:800;flex:0 0 auto">${icon}</span>
          <div style="font-size:12px;color:${BRAND.grey700};line-height:1.4">${escapeHtml(row.label)}</div>
        </div>`;
    }).join("");
  }

  function formPanel(payload) {
    const tone = statusTone(payload.status);
    return `
      <div class="por-guidance-panel" style="font-family:${BRAND.font};border:1px solid ${BRAND.border};border-radius:10px;background:#FFFFFF;margin:10px 0 14px 0;overflow:hidden">
        <div style="display:flex;align-items:center;gap:12px;padding:12px 14px;background:${BRAND.surface};border-bottom:1px solid ${BRAND.border}">
          <div style="width:34px;height:34px;border-radius:17px;background:${tone.bg};color:${tone.color};display:flex;align-items:center;justify-content:center;font-weight:800" aria-hidden="true">${tone.icon}</div>
          <div style="min-width:0">
            <div style="font-size:13px;font-weight:700;color:${BRAND.grey900}">${escapeHtml(payload.title || "InductOne guidance")}</div>
            <div style="font-size:12px;color:${BRAND.grey600}">Status: <strong>${escapeHtml(payload.status || "Unknown")}</strong> · ${escapeHtml(tone.text)}</div>
          </div>
        </div>
        <div style="padding:12px 14px">
          <div style="font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:${BRAND.grey500};font-weight:800;margin-bottom:4px">Next action</div>
          <div style="font-size:13px;color:${BRAND.grey700};line-height:1.5;margin-bottom:10px">${escapeHtml(payload.next_action || "Review this record.")}</div>
          <div style="font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:${BRAND.grey500};font-weight:800;margin-bottom:2px">Prerequisites</div>
          ${checklistRows(payload.checklist || [])}
        </div>
      </div>`;
  }

  function renderFormGuidance(frm) {
    if (!frm || frm.is_new()) return;
    return frappe.call({
      method: "inductone_tools.guidance.get_form_guidance",
      args: {
        doctype: frm.doctype,
        docname: frm.doc.name,
      },
    }).then((response) => {
      const payload = response.message || {};
      if (frm.dashboard && frm.dashboard.wrapper) {
        frm.dashboard.wrapper.find(".por-guidance-panel").closest(".form-dashboard-section").remove();
        frm.dashboard.add_section(formPanel(payload), __("Guidance"));
      }
    }).catch(() => {
      // Keep guidance non-blocking. Real workflow gates remain server-side.
    });
  }

  function taskLink(task) {
    const href = task.url || "#";
    const status = statusTone(task.status);
    return `
      <a href="${escapeHtml(href)}" style="display:block;text-decoration:none;border:1px solid ${BRAND.border};border-radius:8px;padding:10px 12px;background:#FFFFFF;margin-bottom:8px">
        <div style="display:flex;gap:10px;align-items:flex-start">
          <span style="background:${status.bg};color:${status.color};width:22px;height:22px;border-radius:11px;display:inline-flex;align-items:center;justify-content:center;font-size:12px;font-weight:800;flex:0 0 auto">${status.icon}</span>
          <div>
            <div style="font-size:13px;font-weight:700;color:${BRAND.grey900};line-height:1.3">${escapeHtml(task.title)}</div>
            <div style="font-size:12px;color:${BRAND.grey600};line-height:1.45;margin-top:3px">${escapeHtml(task.detail)}</div>
            <div style="font-size:11px;color:${BRAND.blue};font-weight:700;margin-top:6px">${escapeHtml(task.doctype)} ${escapeHtml(task.record || "")}</div>
          </div>
        </div>
      </a>`;
  }

  function portalSection(section) {
    return `
      <div style="border:1px solid ${BRAND.border};border-radius:8px;background:#FFFFFF;padding:12px 14px">
        <div style="font-size:13px;font-weight:800;color:${BRAND.grey900};margin-bottom:5px">${escapeHtml(section.title)}</div>
        <div style="font-size:12px;color:${BRAND.grey600};line-height:1.5">${escapeHtml(section.body)}</div>
      </div>`;
  }

  function builderPortalHtml(payload) {
    const tasks = payload.tasks || [];
    const taskHtml = tasks.length
      ? tasks.map(taskLink).join("")
      : `<div style="border:1px dashed ${BRAND.border};border-radius:8px;background:#FFFFFF;padding:14px;color:${BRAND.grey600};font-size:13px;line-height:1.5">
          You do not have an assigned Build waiting on you right now. This page will populate when Plus One releases a Configuration Order to your supplier account.
        </div>`;
    return `
      <div style="font-family:${BRAND.font};margin:0 0 12px 0">
        <div style="font-size:11px;text-transform:uppercase;letter-spacing:.7px;color:${BRAND.grey500};font-weight:800;margin-bottom:8px">What you need to do</div>
        ${taskHtml}
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin-top:12px">
          ${(payload.sections || []).map(portalSection).join("")}
        </div>
      </div>`;
  }

  function renderBuilderPortal(targetSelector, root) {
    let target;
    if (targetSelector && typeof targetSelector !== "string") {
      target = targetSelector;
    } else {
      const searchRoot = root || document;
      target = searchRoot.querySelector(targetSelector || "[data-por-builder-guidance]");
    }
    if (!target) return;
    target.innerHTML = `<div style="font-family:${BRAND.font};color:${BRAND.grey600};font-size:13px;padding:12px">Loading your Builder Portal tasks...</div>`;
    frappe.call({
      method: "inductone_tools.guidance.get_builder_portal_guidance",
    }).then((response) => {
      target.innerHTML = builderPortalHtml(response.message || {});
    }).catch((err) => {
      target.innerHTML = `<div style="font-family:${BRAND.font};border:1px solid #FECACA;background:#FEF2F2;color:#991B1B;border-radius:8px;padding:12px;font-size:13px">Builder Portal guidance could not load. Refresh the page or contact your Plus One Operations contact.</div>`;
      console.error(err);
    });
  }

  window.inductoneGuidance = {
    brand: BRAND,
    escapeHtml,
    formPanel,
    renderFormGuidance,
    renderBuilderPortal,
    builderPortalHtml,
  };
})();
