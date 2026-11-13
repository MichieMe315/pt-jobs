from functools import lru_cache
from pathlib import Path
import json

@lru_cache(maxsize=1)
def country_names():
    return json.loads((Path(__file__).parent/'data/location_countries.json').read_text(encoding='utf-8'))
