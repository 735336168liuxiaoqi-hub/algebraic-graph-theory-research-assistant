"""Fail closed until the owner clears provenance and supplies a real license."""
import argparse
import json
from pathlib import Path
import tomllib


def publication_status(root):
    root=Path(root)
    record=json.loads((root/'docs/provenance/rights-status.json').read_text(encoding='utf-8'))
    reasons=[]
    if record.get('status')!='cleared' or record.get('public_release_allowed') is not True or record.get('confirmed_by_owner') is not True:
        reasons.append('Original-code publication authorization has not been confirmed by the owner.')
    license_id=record.get('project_license')
    if not isinstance(license_id,str) or not license_id.strip():reasons.append('A compatible project license has not been selected.')
    license_file=root/'LICENSE'
    if not license_file.is_file() or license_file.stat().st_size<100:reasons.append('The final LICENSE text is missing.')
    project=tomllib.loads((root/'pyproject.toml').read_text(encoding='utf-8'))['project']
    if project.get('license')!=license_id:reasons.append('Package license metadata does not match the confirmed license.')
    return {'allowed':not reasons,'status':record.get('status'),'project_license':license_id,'reasons':reasons}


def main(arguments=None):
    parser=argparse.ArgumentParser(description='Check authorization before any public upload or release')
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    result=publication_status(parser.parse_args(arguments).root)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['allowed'] else 2


if __name__=='__main__':raise SystemExit(main())
