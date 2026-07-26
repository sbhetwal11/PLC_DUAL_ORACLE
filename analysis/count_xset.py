"""Count frozen external-set totals via the real loader (coordinator verification)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from plcbench.loader import load_all

ts = load_all("external_testset_draft/tasks")
props = sum(len(t.task.safety_properties) for t in ts)
scens = sum(len(t.task.scenarios) for t in ts)
print("tasks:", len(ts), "properties:", props, "scenarios:", scens)
for t in sorted(ts, key=lambda x: x.task.id):
    print(f"  {t.task.id}: {len(t.task.safety_properties)} props, {len(t.task.scenarios)} scen")
