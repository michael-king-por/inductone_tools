"""Re-run Custom DocPerm convergence after Global Viewer fixture expansion.

The 2026-07-16 convergence patch made existing deterministic fixture rows the
source of truth. The Global Viewer tranche deliberately broadens deterministic
fixture ownership to additional DocTypes, so a second idempotent pass is needed
after fixture sync to remove newly duplicated legacy random-name rows.
"""

from inductone_tools.patches.v2026_07_16_custom_docperm_legacy_convergence import execute
