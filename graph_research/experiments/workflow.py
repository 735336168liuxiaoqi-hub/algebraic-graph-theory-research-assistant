"""Native Python + LangGraph experiments; no WSL, Sage or model required."""
import argparse
import copy
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from graph_research.experiments.backend import NativeBackend


ROOT = Path(__file__).resolve().parents[1]


def validate_task(task):
    """Validate the native experiment's mathematical domain before calculation."""
    if not isinstance(task, dict):
        raise ValueError("实验输入必须是 JSON 对象")
    graphs, alphas = task.get("graphs"), task.get("alphas")
    if not isinstance(graphs, list) or not 1 <= len(graphs) <= 8:
        raise ValueError("graphs 必须包含 1—8 个超图")
    if not isinstance(alphas, list) or not 1 <= len(alphas) <= 16:
        raise ValueError("alphas 必须包含 1—16 个参数")
    if any(type(a) not in (int, float) or not math.isfinite(a) or not 0 <= a < 1
           for a in alphas):
        raise ValueError("alpha 必须是 [0,1) 内的有限数值")
    if len(set(alphas)) != len(alphas):
        raise ValueError("alpha 参数不能重复")
    if type(task.get("seed", 42)) is not int or not 0 <= task.get("seed", 42) <= 2**32 - 2:
        raise ValueError("seed 必须是 0 至 2^32-2 的整数")
    if type(task.get("weighted_incidence", False)) is not bool:
        raise ValueError("weighted_incidence 必须是布尔值")
    names = set()
    for graph in graphs:
        if not isinstance(graph, dict):
            raise ValueError("每个超图必须是 JSON 对象")
        name = graph.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 100 or name in names:
            raise ValueError("每个超图需要唯一且非空的 name（最多100字符）")
        names.add(name)
        edges = graph.get("edges")
        if not isinstance(edges, list) or not 1 <= len(edges) <= 128:
            raise ValueError(f"{name}: 需要 1—128 条超边")
        if any(not isinstance(e, list) or not 2 <= len(e) <= 8 for e in edges):
            raise ValueError(f"{name}: 每条超边包含 2—8 个顶点")
        if len({len(e) for e in edges}) != 1:
            raise ValueError(f"{name}: 第一版只支持一致超图")
        if any(type(v) is not int or not 0 <= v < 64 for e in edges for v in e):
            raise ValueError(f"{name}: 顶点编号必须是 0—63 的整数")
        if any(len(set(e)) != len(e) for e in edges):
            raise ValueError(f"{name}: 超边内不能重复顶点")
        normalized = {tuple(sorted(e)) for e in edges}
        if len(normalized) != len(edges):
            raise ValueError(f"{name}: 不支持重复超边")
        vertices = set().union(*map(set, edges))
        if vertices != set(range(len(vertices))):
            raise ValueError(f"{name}: 顶点编号必须从0开始连续，暂不支持孤立顶点")
        seen = {0}
        while True:
            expanded = seen.union(*(set(e) for e in edges if seen.intersection(e)))
            if expanded == seen:
                break
            seen = expanded
        if seen != vertices:
            raise ValueError(f"{name}: 第一版只支持连通超图")
    return copy.deepcopy(task)


def verify_result(result, tolerance):
    rho = result["rho"]
    vector = result["perron_vector"]
    if not math.isfinite(rho) or rho <= 0:
        return "谱半径不是有限正数"
    if not vector or not all(math.isfinite(x) and x > 0 for x in vector):
        return "Perron 向量不是有限正向量"
    if not math.isclose(sum(vector), 1, rel_tol=0, abs_tol=1e-8):
        return "Perron 向量的1范数不为1"
    if not math.isfinite(result["relative_residual"]) or result["relative_residual"] > tolerance:
        return f"相对特征方程残差超过阈值 {tolerance:g}"
    margin = tolerance * max(1, abs(rho))
    if not result["min_degree"] - margin <= rho <= result["max_degree"] + margin:
        return "结果不满足最小度与最大度界"
    if not result["collatz_lower"] - margin <= rho <= result["collatz_upper"] + margin:
        return "结果不满足正向量比值界"
    return None


class ExperimentState(TypedDict, total=False):
    task: dict
    jobs: list
    rows: list
    pending: list
    round: int
    trace: list
    report: str
    status: str


def render_report(state, tolerance):
    task = state["task"]
    title = str(task.get("title", "超图α谱实验")).replace("\n", " ")
    lines = [f"# {title}", "", "模式：无模型的 LangGraph 实验工作流。", "",
             "计算核心：原生Python/NumPy超图α谱工具，无Sage或WSL依赖。",
             "支持连通、无重边、无孤立点的一致超图；邻接张量采用 1/(k-1)! 归一化。",
             f"独立检查：正向量、1范数、特征方程残差（阈值 {tolerance:g}）、度界和比值界。",
             "数值实验不构成数学证明。未通过检查的结果不参与排序。", "",
             "| 超图 | 顶点数 | 边数 | 秩 | α | 谱半径 | 相对残差 | 状态 |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |"]
    for row in state["rows"]:
        name = row["name"].replace("|", "\\|").replace("\n", " ")
        if "result" in row:
            r = row["result"]
            lines.append(f"| {name} | {r['order']} | {r['size']} | {r['rank']} | {row['alpha']:g} | {r['rho']:.10f} | "
                         f"{r['relative_residual']:.2e} | {'通过' if row['passed'] else '未通过'} |")
        else:
            lines.append(f"| {name} | — | — | — | {row['alpha']:g} | — | — | 计算失败 |")
    lines += ["", "## 本次采样点的比较", ""]
    for alpha in task["alphas"]:
        rows = [r for r in state["rows"] if r["alpha"] == alpha and r["passed"]]
        rows.sort(key=lambda row: row["result"]["rho"], reverse=True)
        if len(rows) != len(task["graphs"]):
            lines.append(f"- α={alpha:g}：存在失败项，暂不作完整比较。")
        else:
            # Never claim strict inequality when numerical intervals overlap.
            comparisons = []
            for left, right in zip(rows, rows[1:]):
                a, b = left["result"], right["result"]
                relation = ">" if a["collatz_lower"] > b["collatz_upper"] else "≈（数值区间重叠）"
                comparisons.append(f"{left['name']} {relation} {right['name']}")
            lines.append(f"- α={alpha:g}：" + ("；".join(comparisons) if comparisons else "仅一个超图。"))
    failures = [row for row in state["rows"] if not row["passed"]]
    if failures:
        lines += ["", "## 需要检查的项目", ""]
        lines += [f"- {row['name']} / α={row['alpha']:g}：{row['error']}" for row in failures]
    lines += ["", "## 可复现实验记录", "",
              "完整超边列表、随机种子、Perron向量、全精度关联矩阵、迭代次数和每次尝试保存在result.json。",
              "计算器使用所有顶点的比值区间停止条件，并另行重建特征方程检查残差。",
              "赋权关联矩阵保留双精度数值，不作旧包的四舍五入/有理化。",
              "", "执行轨迹：" + " → ".join(state["trace"]), ""]
    return "\n".join(lines)


def build_workflow(backend=None, tolerance=1e-9):
    if not math.isfinite(tolerance) or not 0 < tolerance <= 1e-3:
        raise ValueError("tolerance 必须位于 (0, 0.001]")
    backend = backend or NativeBackend()

    def plan(state):
        task = validate_task(state["task"])
        jobs = [{"name": g["name"], "edges": g["edges"], "alpha": a,
                 "seed": task.get("seed", 42),
                 "weighted_incidence": task.get("weighted_incidence", False)}
                for g in task["graphs"] for a in task["alphas"]]
        return {"task": task, "jobs": jobs, "pending": list(range(len(jobs))),
                "rows": [{"name": j["name"], "alpha": j["alpha"], "attempts": [],
                          "passed": False} for j in jobs], "round": 0,
                "trace": ["校验输入并展开参数"]}

    def calculate(state):
        rows = copy.deepcopy(state["rows"])
        round_number = state["round"] + 1
        for index in state["pending"]:
            job = dict(state["jobs"][index])
            job["seed"] += round_number - 1
            attempt = {"round": round_number, "seed": job["seed"]}
            # Remove stale values before a retry; failed attempts remain in history.
            rows[index].pop("result", None)
            rows[index].pop("error", None)
            try:
                result = backend(job)
                rows[index]["result"] = result
                attempt["result"] = result
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                rows[index]["error"] = error
                attempt["error"] = error
            rows[index]["attempts"].append(attempt)
        return {"rows": rows, "round": round_number,
                "trace": state["trace"] + [f"Python计算（第{round_number}次）"]}

    def review(state):
        rows = copy.deepcopy(state["rows"])
        pending = []
        for index, row in enumerate(rows):
            if "result" in row:
                error = verify_result(row["result"], tolerance)
                if error:
                    row["error"] = error
                row["passed"] = error is None
                row["attempts"][-1]["verification_error"] = error
            else:
                row["passed"] = False
            if not row["passed"]:
                pending.append(index)
        return {"rows": rows, "pending": pending,
                "trace": state["trace"] + ["独立验证结果"]}

    def route(state):
        return "calculate" if state["pending"] and state["round"] < 2 else "report"

    def report(state):
        return {"report": render_report(state, tolerance),
                "status": "complete" if not state["pending"] else "needs_review"}

    graph = StateGraph(ExperimentState)
    graph.add_node("plan", plan)
    graph.add_node("calculate", calculate)
    graph.add_node("review", review)
    graph.add_node("report", report)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "calculate")
    graph.add_edge("calculate", "review")
    graph.add_conditional_edges("review", route, {"calculate": "calculate", "report": "report"})
    graph.add_edge("report", END)
    return graph.compile()


def main():
    parser = argparse.ArgumentParser(description="使用原生Python执行LangGraph超图谱实验")
    parser.add_argument("task", nargs="?", type=Path, default=ROOT / "data/hypergraph_compare.json")
    parser.add_argument("--tolerance", type=float, default=1e-9)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        task = json.loads(args.task.read_text(encoding="utf-8-sig"))
        validate_task(task)
        from graph_research.runtime.storage import safe_path,atomic_text,write_json
        output=safe_path(args.output or Path.cwd()/'outputs'/datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        graph = build_workflow(NativeBackend(), args.tolerance)
        result = graph.invoke({"task": task}, {"recursion_limit": 20})
        output.mkdir(parents=True, exist_ok=False)
        write_json(output/'result.json',result)
        atomic_text(output/'report.md',result['report'])
        atomic_text(output/'workflow.mmd',graph.get_graph().draw_mermaid())
        print(result["report"])
        print(f"实验目录：{output.resolve()}")
        return 0 if result["status"] == "complete" else 2
    except (ValueError, OSError) as exc:
        print(f"输入或环境错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
