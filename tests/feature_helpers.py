"""Offline, explicitly simulated human consent for development tests only."""
import copy
import json
from pathlib import Path
from graph_research.tools.change_control import ChangeController


def proposal():
    return json.loads((Path(__file__).resolve().parents[1]/'graph_research/data/h_index_proposal.json').read_text(encoding='utf-8'))


def request_for(tool):
    return {'name':tool['name'],'goal':'计算图的度序列h指数',
            'requirements':'输入最多128项非负整数度序列；输出h_index，空序列约定为0。',
            'checked_tools':[{'tool':'graph_invariants','reason':'可给度序列，但没有h指数算法分支'}],
            'composition_possible':False,'why_not_composition':'需新增按h指数定义扫描序列的算法；原图信息由外层工具准备。',
            'new_algorithm':'排序后扫描，求至少h项>=h的最大h，不在新包内调用工具。',
            'parameters':copy.deepcopy(tool['parameters']),
            'acceptance_tests':[{**copy.deepcopy(f),'basis':'按h指数定义手工验算的小例；测试只覆盖列出的输入'} for f in tool['tests']],
            'complexity':'small'}


def approve_for_tests(store,tool,registry):
    controller=ChangeController(store.directory/'_test_changes')
    assessment=controller.assess(request_for(tool),registry)
    return controller.approve(assessment['id'],registry)
