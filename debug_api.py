import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from research.aliexpress_fetcher import search_products

results = search_products("pet accessories", max_results=3)
print(json.dumps(results, indent=2))
