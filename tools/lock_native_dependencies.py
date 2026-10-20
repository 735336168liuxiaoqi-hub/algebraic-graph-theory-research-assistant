"""Pin only this project's transitive runtime dependencies, not all of conda."""
from importlib.metadata import distribution
from pathlib import Path
from packaging.requirements import Requirement

seen = {}
expanded=set()
def visit(name,extras=()):
    dist = distribution(name)
    canonical = dist.metadata["Name"]
    key=(canonical.lower(),tuple(sorted(extras)))
    if key in expanded:return
    expanded.add(key)
    seen[canonical.lower()] = canonical+"=="+dist.version
    for text in dist.requires or []:
        requirement = Requirement(text)
        if requirement.marker is None or any(requirement.marker.evaluate({"extra":extra}) for extra in ('',*extras)):
            visit(requirement.name,requirement.extras)

for name in ["numpy","networkx","sympy","langgraph","jsonschema","httpx","matplotlib","PySide6","mcp"]: visit(name)
Path(__file__).resolve().parents[1].joinpath("requirements-lock.txt").write_text(
    "# Validated native Python runtime dependencies\n"+"\n".join(sorted(seen.values(),key=str.lower))+"\n",encoding="utf-8")
print(f"Pinned {len(seen)} runtime distributions")
