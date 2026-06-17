"""Test the get_report_data whitelisted method (the one the sandbox shell calls)."""
import sys, types
sys.path.insert(0, "/home/claude/diff_tool")

frappe = types.ModuleType("frappe")
class _Dict(dict):
    def __getattr__(self, k): return self.get(k)
    def __setattr__(self, k, v): self[k] = v
frappe._dict = _Dict
frappe.throw = lambda *a, **k: (_ for _ in ()).throw(Exception(a[0] if a else "throw"))
frappe.msgprint = lambda *a, **k: None
def _wl(*da, **dk):
    if len(da) == 1 and callable(da[0]) and not dk: return da[0]
    def deco(fn): return fn
    return deco
frappe.whitelist = _wl
frappe._ = lambda s, *a, **k: s
utils = types.ModuleType("frappe.utils")
import datetime
utils.now_datetime = lambda: datetime.datetime(2026,6,16,12,0,0)
sys.modules["frappe.utils"] = utils
frappe.utils = utils
frappe.local = types.SimpleNamespace(response=_Dict())
sys.modules["frappe"] = frappe

from inductone_tools.snapshot_diff.schema import SnapshotNode
import inductone_tools.snapshot_diff.loader as loader

def node(nid, ic, qty=1.0, bom="", pid=None, lvl=1, grp="Test", uom="Nos"):
    return SnapshotNode(node_id=nid, parent_node_id=pid, bom_level=lvl, item_code=ic,
        item_name=ic, item_group=grp, description="", qty=qty, uom=uom, bom_used=bom,
        node_type="Leaf", is_leaf=True, effect_origin="BASELINE", source_option_code="",
        excluded=False, source_bom=bom, balloon_numbers="", electrical_unit="",
        source_electrical_bom_rev="")

SNAPS = {
    "A": [node("a1","TOP",1,"BOM-TOP-003",None,0), node("a4","2000010",1,"BOM-TOP-003","a1",1),
          node("a2","1000001",2,"BOM-2000010-002","a4",2), node("a5","1000099",5,"BOM-TOP-003","a1",1)],
    "B": [node("b1","TOP",1,"BOM-TOP-004",None,0), node("b4","2000010",1,"BOM-TOP-004","b1",1),
          node("b2","1000001",3,"BOM-2000010-003","b4",2), node("b8","1000300",1,"BOM-2000010-003","b4",2)],
}
loader.load_snapshot_nodes = lambda n: SNAPS[n]
loader._snapshot_label = lambda n: n

for vm in ["Hierarchical", "Flat Procurement"]:
    r = loader.get_report_data("A", "B", view_mode=vm, context_mode="Changes only")
    print(f"{vm}: cols={len(r['columns'])} rows={len(r['data'])} summary={len(r['report_summary'])}")
    assert r['columns'] and r['data'] and r['report_summary']
    assert "<b>" in r['message']

# empty state
r0 = loader.get_report_data(None, None)
assert r0['data'] == [] and r0['columns']
print("Empty state OK")
print("\nget_report_data works for both views. Sandbox shell will succeed.")