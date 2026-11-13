import json
from pathlib import Path
ROWS=json.loads((Path(__file__).parent/'data/countries.json').read_text(encoding='utf-8'))
COUNTRIES=[r['name'] for r in ROWS]
CODES={r['name']:r['code'] for r in ROWS}
def canonical(value):
    aliases={'usa':'United States','uk':'United Kingdom','united states of america':'United States'}
    value=aliases.get(str(value).strip().casefold(),str(value).strip())
    result=next((n for n in COUNTRIES if n.casefold()==value.casefold()),None)
    if not result:raise ValueError('Choose a country from the list.')
    return result
