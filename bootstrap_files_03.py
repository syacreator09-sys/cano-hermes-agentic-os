FILES = {'scripts/validate.py': 'from __future__ import annotations\n'
                        'import json\n'
                        'from pathlib import Path\n'
                        'import yaml\n'
                        'ROOT = Path(__file__).resolve().parents[1]\n'
                        'errors=[]\n'
                        "agents=list((ROOT/'agents').rglob('*.yaml'))\n"
                        "skills=list((ROOT/'skills').rglob('manifest.json'))\n"
                        "if len(agents)<38: errors.append(f'expected >=38 agents, found {len(agents)}')\n"
                        "if len(skills)<40: errors.append(f'expected >=40 skills, found {len(skills)}')\n"
                        'for path in agents:\n'
                        "    data=yaml.safe_load(path.read_text(encoding='utf-8')) or {}\n"
                        "    for key in ('id','team','objective','status'):\n"
                        "        if key not in data: errors.append(f'{path}: missing {key}')\n"
                        'for path in skills:\n'
                        "    data=json.loads(path.read_text(encoding='utf-8'))\n"
                        "    for key in ('id','version','purpose'):\n"
                        "        if key not in data: errors.append(f'{path}: missing {key}')\n"
                        'if errors:\n'
                        "    raise SystemExit('\\n'.join(errors))\n"
                        "print(f'validated agents={len(agents)} skills={len(skills)}')\n",
 'src/cano_hermes/__init__.py': '__version__ = "0.2.0"\n'}
