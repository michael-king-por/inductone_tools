"""
DEPRECATED MODULE — compatibility shim only.

The canonical acceptance implementation lives in
`inductone_tools/build_completion_accept.py`.

This module previously held a SECOND, near-identical copy of
`accept_completion_create_as_built`. That duplication is exactly what let a
fix (the component_label traceability copy) land in one copy while the
ACTIVE client-script path used the other copy and silently dropped the
field. To make sure the two can never diverge again, this module no longer
contains its own logic — it simply delegates to the canonical function.

Do NOT add logic here. Any change to the acceptance flow goes in
build_completion_accept.py.
"""

import frappe


@frappe.whitelist()
def accept_completion_create_as_built(completion_name, as_built_notes=None):
    """Compatibility wrapper. Delegates to the canonical implementation so
    any legacy caller that still references
    `inductone_tools.instance.acceptance.accept_completion_create_as_built`
    runs the maintained code path. The import is done lazily (inside the
    function) to avoid any import-time circular dependency."""
    from inductone_tools.build_completion_accept import (
        accept_completion_create_as_built as _canonical,
    )
    return _canonical(completion_name, as_built_notes=as_built_notes)