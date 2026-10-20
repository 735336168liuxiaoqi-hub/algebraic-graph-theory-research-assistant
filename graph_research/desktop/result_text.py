"""Readable English result labels without translating scientific/user data values."""
import json
from .i18n import language,tr
from graph_research.rendering.results import TITLES,LABELS,METRIC_KEYS,display_value,display_field,terminal_result


def result_text(observation):
    if language()=='zh':return terminal_result(observation)
    title=tr(TITLES.get(observation.get('tool'),observation.get('tool','Result')))
    if not observation.get('ok'):return 'Incomplete: '+title+'\n'+str(observation.get('error','No valid result'))
    data=observation.get('result');lines=['━ '+title+' ━']
    if not isinstance(data,dict):return lines[0]+'\n'+json.dumps(data,ensure_ascii=False,indent=2)[:1200]
    def value(key,item):
        text=display_field(key,item)
        return tr(text) if isinstance(item,bool) or key in ('status','preview_status') else text
    preferred=[key for key in METRIC_KEYS if key in data]
    for key in [*preferred,*(key for key in data if key not in preferred)]:
        if key in ('files','editor','execution'):continue
        item=data[key];name=tr(LABELS.get(key,key))
        if isinstance(item,list) and item and all(isinstance(row,list) for row in item):
            width=max(map(len,item));lines.append(f'{name}: {len(item)} rows × {width} columns')
            for row in item[:6]:lines.append('  '+'  '.join(value(key,cell) for cell in row[:8]))
            if len(item)>6 or width>8:lines.append('  … Preview only; full data is retained in JSON.')
        elif isinstance(item,list):lines.append(name+': '+', '.join(value(key,v) for v in item[:10])+(' …' if len(item)>10 else ''))
        elif isinstance(item,dict):lines.append(name+': saved; inspect complete data for details.')
        else:lines.append(name+': '+value(key,item)[:500])
        if len(lines)>24:lines.append('Other fields are retained in the complete data.');break
    if data.get('files'):lines.append('Output files: '+', '.join(map(str,data['files'])))
    lines.append('Numbers use display formatting; full precision is retained in JSON.')
    return '\n'.join(lines)
