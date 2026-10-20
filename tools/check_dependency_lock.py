"""Compare installed runtime/check tools with the reviewed version pins."""
from importlib.metadata import version,PackageNotFoundError
from pathlib import Path


def main():
    root=Path(__file__).resolve().parents[1];mismatches=[];count=0
    for filename in ('requirements-lock.txt','requirements-dev.txt'):
        for line in (root/filename).read_text(encoding='utf-8').splitlines():
            line=line.strip()
            if not line or line.startswith('#'):continue
            name,expected=line.split('==',1);count+=1
            try:actual=version(name)
            except PackageNotFoundError:actual='not installed'
            if actual!=expected:mismatches.append(name+': expected '+expected+', got '+actual)
    if mismatches:raise SystemExit('Dependency lock mismatch:\n'+'\n'.join(mismatches))
    print('Installed dependency pins agree:',count,'distributions')


if __name__=='__main__':main()
