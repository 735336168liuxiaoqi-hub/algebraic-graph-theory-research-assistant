"""Inventory retained release definitions without requiring or executing Sage."""
import hashlib
import io
import tokenize
import importlib
import inspect
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = None
NAMES = ["myCombinatorics","MyPolynomial","MyTools","MyUtility","Tensor","GraphTheory","GraphTheory1",
         "hypergraph_v2","hypergraph_v22","HyperMatrix","LinearAlgebra"]
MODULES = {"myCombinatorics":"combinatorics","MyPolynomial":"polynomials","MyTools":"utilities",
           "MyUtility":"utilities","Tensor":"tensors","HyperMatrix":"tensors",
           "GraphTheory":"graphs","GraphTheory1":"graphs","hypergraph_v2":"hypergraphs",
           "hypergraph_v22":"hypergraphs","LinearAlgebra":"linear_algebra"}
REPLACEMENTS={('myCombinatorics.sage','solve_rec'):('graph_research.algebra.recurrences','solve_linear_recurrence')}
EXCLUDED_RELEASE_SYMBOLS={('myCombinatorics.sage','magicsquare_normal_odd'),
                          ('myCombinatorics.sage','Siamese_magic_square')}
for _name in ('edge','edge.issuperset','edge.__sub__','edge.intersection','edge.__add__','edge.__and__','edge.__getitem__'):
    REPLACEMENTS[('GraphTheory.sage',_name)]=('graph_research.hypergraphs.model',_name)



def main(source=None):
    source=Path(source) if source is not None else SOURCE
    if source is None:raise ValueError('请用--source显式指定原始Sage文件目录；应用运行不需要这些文件。')
    files, definitions, known = [], [], {}
    for name in NAMES:
        path = source/(name+".sage")
        raw = path.read_bytes(); digest = hashlib.sha256(raw).hexdigest()
        duplicate = known.get(digest)
        known.setdefault(digest,name+".sage")
        text=raw.decode('utf-8-sig');lines=text.splitlines()
        string_lines={line for token in tokenize.generate_tokens(io.StringIO(text).readline)
                      if token.type==tokenize.STRING and token.end[0]>token.start[0] for line in range(token.start[0]+1,token.end[0]+1)}
        files.append({"file":path.name,"sha256":digest,"duplicate_of":duplicate,"lines":len(lines)})
        module = importlib.import_module("graph_research."+MODULES[name])
        stack = []
        for i,line in enumerate(lines):
            if i+1 in string_lines:continue
            match = re.match(r"^(\s*)(class|def)\s+([A-Za-z_][A-Za-z0-9_]*)",line)
            if not match: continue
            indent,kind,symbol = len(match[1]),match[2],match[3]
            while stack and stack[-1][0] >= indent: stack.pop()
            qualified = ".".join([entry[1] for entry in stack]+[symbol])
            stack.append((indent,symbol,kind))
            if any(entry[2] == "def" for entry in stack[:-1]): continue
            if (path.name,qualified) in EXCLUDED_RELEASE_SYMBOLS:continue
            end = i+1
            while end < len(lines):
                next_line = lines[end]
                if end+1 not in string_lines and next_line.strip() and not next_line.lstrip().startswith("#") and len(next_line)-len(next_line.lstrip()) <= indent:
                    break
                end += 1
            target = module
            parts = qualified.split(".")
            if parts[0] == "HyperG": parts[0] = "Hypergraph"
            for part in parts:
                if target is None:break
                if inspect.isclass(target) and not any(part in base.__dict__ for base in target.__mro__):
                    target = None
                else:
                    target = getattr(target,part,None)
            status = "native_implementation_available" if callable(target) else "pending"
            native_module=module.__name__;native_symbol='.'.join(parts)
            replacement=REPLACEMENTS.get((path.name,qualified))
            if path.name in ('GraphTheory.sage','GraphTheory1.sage') and (qualified=='edge' or qualified.startswith('edge.')):
                replacement=('graph_research.hypergraphs.model',qualified)
            if not callable(target) and replacement:
                native_module,native_symbol=replacement
                target=importlib.import_module(native_module)
                for component in native_symbol.split('.'):target=getattr(target,component)
                status='native_implementation_available'
            if duplicate: status = "duplicate_source"
            note='API adapted; consult native docstrings and tests; not a blanket Sage-equivalence claim'
            if qualified in ('set_edge_weight','weight_edges','complex_weight'):
                note+='; NetworkX copies by default; no implicit mutation except explicit copy=False; numeric ndarray output; weighted matrices do not change the unweighted spectrum tools'
            if (qualified=='edge' or qualified.startswith('edge.')) and path.name.startswith('GraphTheory'):
                note+='; reuse the immutable hyperedge vertex container; positive real edge metadata only; use NetworkX adapters for negative/complex ordinary-graph weights'
            if qualified in ('getGridPath','gridPath','lattice_path','rectangle','chess_board'):
                note+='; Matplotlib Figure output; optional visual dependency; rectangular board labels corrected'
            if qualified=='getCycleIndex1':note+='; legacy partition-as-exponents encoding retained, not the standard cycle index; use getCycleIndex for Polya'
            if qualified=='cayley_graph':note+='; SymPy groups or explicit finite semigroup elements/generators; loopless directed graph only when simple=True'
            if qualified in ('el_rop2','el_rop3','el_cop2','el_cop3','do_Actions','Op_links','do_show_ops','lst2ltx','sum_hold','split_row','split_vector','show_equtions','stdequs','Mat2PR','matrix_round','map_round'):
                note+='; SymPy Matrix/DomainMatrix or explicit LaTeX replaces implicit Sage rich display; standardization is affine-linear; tolerance rounding preserves exact values'
            if qualified=='polynomials_for_addstarsgraph':note+='; unweighted simple L/Q only; old incorrect A branch rejected; symbolic counts need nonnegative integer assumptions'
            if qualified in ('HyperG.add_star','HyperG.add_stars'):note+='; preserve weights/isolates; new edges weight 1; reject silently changing an independent D diagonal'
            if qualified=='HyperG.eigenVfun':note+='; nonempty uniform hypergraph; SymPy column vector for lambda*x^(k-1)-L*x^(k-1), not a solver'
            definitions.append({"source_file":path.name,"symbol":qualified,"line":i+1,"kind":kind,
                                "status":status,"native_module":native_module if callable(target) else None,
                                "native_symbol":native_symbol if callable(target) else None,
                                "validation_scope":note if callable(target) else "Not exposed as a callable tool",
                                "source":"\n".join(lines[i:end])})
    result = {"source_files":files,"definitions":definitions,
              "catalog_scope":"retained_release_definitions","omitted_definition_count":len(EXCLUDED_RELEASE_SYMBOLS),
              "counts":{status:sum(d["status"]==status for d in definitions) for status in
                        ["native_implementation_available","pending","duplicate_source"]}}
    out = ROOT/"docs/provenance/migration_catalog.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    report = ["# Sage包迁移清单", "", "逐函数记录见docs/provenance/migration_catalog.json；该历史记录不进入运行时工具包。", "",
              "本表仅用于旧源码追溯，不作为功能完成率或开发待办。pending表示旧定义尚未逐项适配，不等于科研功能缺失；能力验收见[功能说明](../FEATURES.md)。原生实现也不声称所有参数均与Sage等价。", "",
              "| 原文件 | 原生实现可用 | 待迁移 | 重复定义 |", "| --- | ---: | ---: | ---: |"]
    for file in files:
        values = [d for d in definitions if d["source_file"]==file["file"]]
        report.append("| "+file["file"]+" | "+" | ".join(str(sum(d["status"]==status for d in values)) for status in
                     ["native_implementation_available","pending","duplicate_source"])+" |")
    report += ["", "## 尚未迁移的定义", ""]
    report += [f"- {d['source_file']}:{d['line']} `{d['symbol']}`" for d in definitions if d["status"]=="pending"]
    (ROOT/"docs/provenance/MIGRATION.md").write_text("\n".join(report)+"\n",encoding="utf-8")
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    import argparse
    parser=argparse.ArgumentParser(description='离线重建源码迁移记录，不执行Sage代码')
    parser.add_argument('--source',required=True,type=Path)
    main(parser.parse_args().source)
