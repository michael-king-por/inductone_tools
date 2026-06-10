import frappe
import json
from inductone_tools.bom_export import explode_bom_tree_structured


def execute():
    """
    Export every InductOne Configuration Option, its mappings, and every fact
    the pipeline depends on to resolve those mappings correctly. Writes a JSON
    report and prints a human-readable audit.

    For each mapping, resolves and reports:
      - target item exists?
      - target item has a default active submitted BOM? (needed for EXPLODE)
      - target_bom valid? (needed for USE_TARGET_BOM)
      - replace_with_item / replace_with_bom valid? (needed for REPLACE)
      - how the structural effect mode will resolve (AUTO -> concrete)
      - whether the target is present in the master BOM tree (decides
        INCREMENT vs ADD_BRANCH for ADD; decides whether REMOVE/OVERRIDE has
        anything to act on)
      - flags for anything that would break or silently no-op
    """
    # The master / top BOM the configurator builds against.
    # Pull from a representative build, or hardcode your canonical top item.
    TOP_ITEM = "1611 027 0010"
    top_bom = frappe.db.get_value(
        "BOM", {"item": TOP_ITEM, "is_default": 1, "is_active": 1, "docstatus": 1}, "name"
    )
    print("=" * 78)
    print("CONFIGURATION OPTION STACK EXPORT")
    print("=" * 78)
    print(f"Top item: {TOP_ITEM}")
    print(f"Top BOM:  {top_bom}")

    # Explode the master tree once. This is the reference for present/absent.
    baseline = explode_bom_tree_structured(top_bom, "Follow Explicit Child BOM Links", None, True)
    baseline_items = {r["item_code"] for r in baseline if r.get("item_code")}
    # occurrence count per item (matters for INCREMENT/OVERRIDE single-occurrence rule)
    occ = {}
    for r in baseline:
        ic = r.get("item_code")
        if ic:
            occ[ic] = occ.get(ic, 0) + 1
    print(f"Baseline distinct items: {len(baseline_items)} | total rows: {len(baseline)}")

    options = frappe.get_all(
        "InductOne Configuration Option",
        fields=["name", "option_code", "option_name", "option_category",
                "option_group", "option_group_required", "is_default_selection",
                "is_active", "status", "mapping_status"],
        order_by="option_group asc, sort_order asc",
    )
    print(f"Configuration options: {len(options)}")

    report = {"top_item": TOP_ITEM, "top_bom": top_bom, "options": []}

    # Group-level sanity: required groups must have >=1 active option and exactly
    # one default selection.
    groups = {}
    for o in options:
        g = (o.get("option_group") or "").strip()
        if not g:
            continue
        groups.setdefault(g, {"required": False, "active": 0, "defaults": 0, "options": []})
        if o.get("option_group_required"):
            groups[g]["required"] = True
        if o.get("is_active"):
            groups[g]["active"] += 1
        if o.get("is_default_selection"):
            groups[g]["defaults"] += 1
        groups[g]["options"].append(o["option_code"])

    print("\n" + "=" * 78)
    print("OPTION GROUPS")
    print("=" * 78)
    for g, info in sorted(groups.items()):
        flags = []
        if info["required"] and info["active"] == 0:
            flags.append("REQUIRED-BUT-NO-ACTIVE-OPTION")
        if info["required"] and info["defaults"] == 0:
            flags.append("REQUIRED-BUT-NO-DEFAULT")
        if info["defaults"] > 1:
            flags.append(f"MULTIPLE-DEFAULTS({info['defaults']})")
        flag_str = ("  *** " + ", ".join(flags) + " ***") if flags else ""
        print(f"  [{g}] required={info['required']} active={info['active']} "
              f"defaults={info['defaults']}{flag_str}")
        print(f"      options: {', '.join(info['options'])}")

    print("\n" + "=" * 78)
    print("OPTIONS + MAPPINGS + PIPELINE DEPENDENCY RESOLUTION")
    print("=" * 78)

    for o in options:
        doc = frappe.get_doc("InductOne Configuration Option", o["name"])
        opt_report = {
            "option_code": o["option_code"],
            "option_name": o["option_name"],
            "group": o.get("option_group"),
            "group_required": o.get("option_group_required"),
            "is_default": o.get("is_default_selection"),
            "is_active": o.get("is_active"),
            "status": o.get("status"),
            "mapping_status": o.get("mapping_status"),
            "mappings": [],
            "flags": [],
        }

        print("\n" + "-" * 78)
        print(f"[{o['option_code']}] {o['option_name']}")
        print(f"  group={o.get('option_group')} required={o.get('option_group_required')} "
              f"default={o.get('is_default_selection')} active={o.get('is_active')} "
              f"status={o.get('status')} mapping_status={o.get('mapping_status')}")

        mappings = doc.mappings_table or []
        if not mappings:
            print("  (no mappings)")
            if o.get("is_active"):
                opt_report["flags"].append("ACTIVE-BUT-NO-MAPPINGS")
                print("    *** ACTIVE BUT NO MAPPINGS — selecting this does nothing ***")

        for mr in mappings:
            action = (getattr(mr, "action", "") or "").strip()
            target = getattr(mr, "target_item", None)
            expand = (getattr(mr, "expand_mode", "") or "AS_ITEM_ONLY").strip()
            target_bom = getattr(mr, "target_bom", None)
            rwi = getattr(mr, "replace_with_item", None)
            rwb = getattr(mr, "replace_with_bom", None)
            sem = (getattr(mr, "structural_effect_mode", "") or "AUTO").strip()
            qty_source = getattr(mr, "qty_source", None)
            qty_fixed = getattr(mr, "qty_fixed", None)

            m = {
                "action": action, "target_item": target, "expand_mode": expand,
                "target_bom": target_bom, "replace_with_item": rwi, "replace_with_bom": rwb,
                "structural_effect_mode_authored": sem,
                "qty_source": qty_source, "qty_fixed": qty_fixed,
                "checks": {}, "flags": [],
            }

            # --- dependency resolution ---
            target_exists = bool(target and frappe.db.exists("Item", target))
            target_default_bom = None
            if target:
                target_default_bom = frappe.db.get_value(
                    "BOM", {"item": target, "is_default": 1, "is_active": 1, "docstatus": 1}, "name"
                )
            target_in_baseline = target in baseline_items if target else False
            target_occurrences = occ.get(target, 0) if target else 0

            m["checks"] = {
                "target_exists": target_exists,
                "target_default_bom": target_default_bom,
                "target_in_baseline": target_in_baseline,
                "target_occurrences_in_baseline": target_occurrences,
            }

            # resolve effect mode the way the pipeline will
            resolved_mode = _resolve_mode(action, expand, sem, target_in_baseline)
            m["resolved_effect_mode"] = resolved_mode

            # validate per action
            if not target:
                m["flags"].append("NO-TARGET-ITEM")
            elif not target_exists:
                m["flags"].append("TARGET-ITEM-DOES-NOT-EXIST")

            if expand == "EXPLODE_DEFAULT_BOM" and target_exists and not target_default_bom:
                m["flags"].append("EXPLODE-BUT-NO-DEFAULT-BOM")
            if expand == "USE_TARGET_BOM":
                if not target_bom:
                    m["flags"].append("USE_TARGET_BOM-BUT-NO-target_bom")
                elif not frappe.db.exists("BOM", target_bom):
                    m["flags"].append("target_bom-DOES-NOT-EXIST")

            if action == "REPLACE":
                if not rwi:
                    m["flags"].append("REPLACE-BUT-NO-replace_with_item")
                elif not frappe.db.exists("Item", rwi):
                    m["flags"].append("replace_with_item-DOES-NOT-EXIST")
                if rwb and not frappe.db.exists("BOM", rwb):
                    m["flags"].append("replace_with_bom-DOES-NOT-EXIST")

            if action == "ADD":
                if target_in_baseline:
                    # will become INCREMENT — single-occurrence rule applies for leaf
                    if expand == "AS_ITEM_ONLY" and target_occurrences > 1:
                        m["flags"].append(
                            f"INCREMENT-LEAF-AMBIGUOUS({target_occurrences}-occurrences)")
                # else ADD_BRANCH — fine

            if action == "QTY_OVERRIDE":
                if not target_in_baseline:
                    m["flags"].append("OVERRIDE-TARGET-NOT-IN-BASELINE(no-op)")
                if target_occurrences > 1:
                    m["flags"].append(
                        f"OVERRIDE-AMBIGUOUS({target_occurrences}-occurrences)")

            if action == "REMOVE":
                if not target_in_baseline:
                    m["flags"].append("REMOVE-TARGET-NOT-IN-BASELINE(no-op)")

            opt_report["mappings"].append(m)

            flagstr = ("  *** " + ", ".join(m["flags"]) + " ***") if m["flags"] else "  OK"
            print(f"    {action} {target} [{expand}] qty_src={qty_source} qty={qty_fixed}")
            print(f"      authored_mode={sem} -> resolves={resolved_mode}")
            print(f"      exists={target_exists} default_bom={target_default_bom or '-'} "
                  f"in_baseline={target_in_baseline} occurrences={target_occurrences}")
            if rwi or rwb:
                print(f"      replace_with_item={rwi} replace_with_bom={rwb}")
            print(f"     {flagstr}")

        report["options"].append(opt_report)

    # write JSON
    out_path = frappe.get_site_path("private", "files", "config_option_stack_export.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    # summary of all flags
    print("\n" + "=" * 78)
    print("FLAG SUMMARY (everything needing attention)")
    print("=" * 78)
    any_flag = False
    for opt in report["options"]:
        for fl in opt["flags"]:
            any_flag = True
            print(f"  [{opt['option_code']}] {fl}")
        for m in opt["mappings"]:
            for fl in m["flags"]:
                any_flag = True
                print(f"  [{opt['option_code']}] {m['action']} {m['target_item']}: {fl}")
    if not any_flag:
        print("  No flags — every mapping's dependencies resolve cleanly.")

    print(f"\nJSON written to: {out_path}")
    print("Retrieve with: bench --site <site> execute frappe.utils.print_path "
          "or download from the File list.")
    return out_path


def _resolve_mode(action, expand, authored, target_in_baseline):
    """Mirror the client+server resolution so the export shows the final mode."""
    if authored and authored != "AUTO":
        return authored + " (authored)"
    if action == "REMOVE":
        return "SUPPRESS_TARGET_NODE" if expand == "AS_ITEM_ONLY" else "SUPPRESS_TARGET_BRANCH"
    if action == "REPLACE":
        return "REPLACE_TARGET_BRANCH"
    if action == "ADD":
        if expand in ("EXPLODE_DEFAULT_BOM", "USE_TARGET_BOM"):
            return "INCREMENT_NODE_QTY" if target_in_baseline else "ADD_BRANCH"
        # AS_ITEM_ONLY ADD
        return "INCREMENT_NODE_QTY"
    if action == "QTY_OVERRIDE":
        return "OVERRIDE_NODE_QTY"
    return "NO_STRUCTURAL_CHANGE"
