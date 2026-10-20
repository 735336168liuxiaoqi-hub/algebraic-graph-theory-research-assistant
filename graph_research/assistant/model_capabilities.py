"""Conservative reasoning capabilities; model discovery never implies support.

Known IDs follow official model pages reviewed 2026-10-17. Unknown aliases and
third-party endpoints require an explicit OpenAI-compatible override. No network.
"""
from urllib.parse import urlsplit

EFFORT_LABELS={None:'服务默认','none':'关闭','minimal':'最少','low':'低','medium':'中','high':'高','xhigh':'特高','max':'最高'}
KNOWN_EFFORTS={
    'gpt-5':('minimal','low','medium','high'),
    'gpt-5.1':('none','low','medium','high'),
    'gpt-5.4':('none','low','medium','high','xhigh'),
    'gpt-6-astra':('low','medium','high','xhigh','max'),
    'gpt-6.1-sol':('low','medium','high','xhigh','max'),
    'gpt-6-sol':('none','low','medium','high','xhigh','max'),
}


def reasoning_choices(base_url,model,profile='auto'):
    """Return only default unless support is known or the user opts in."""
    if profile=='off':return (None,)
    if profile=='openai':return (None,*tuple(k for k in EFFORT_LABELS if k is not None))
    try:official=urlsplit(base_url).hostname=='api.openai.com'
    except ValueError:official=False
    if not official:return (None,)
    return (None,*KNOWN_EFFORTS.get(model,()))
