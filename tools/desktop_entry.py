"""pythonw entry with a local startup log instead of a console window."""
from pathlib import Path
import sys
import traceback

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from graph_research.runtime.storage import safe_path
logs=safe_path(root/'outputs/desktop');logs.mkdir(parents=True,exist_ok=True)
with safe_path(logs/'startup.log',root=logs).open('a',encoding='utf-8') as log:
    sys.stdout=log;sys.stderr=log
    try:
        from graph_research.runtime.diagnostics import environment_report
        diagnostics=environment_report()
        if not diagnostics['ok']:raise RuntimeError('运行环境不一致：'+'；'.join(diagnostics['issues'])+' 请参见 ENVIRONMENT.md。')
        from graph_research.cli import main
        sys.argv=['graph-research','desktop']
        raise SystemExit(main())
    except SystemExit:raise
    except Exception:
        traceback.print_exc();raise SystemExit(2)
