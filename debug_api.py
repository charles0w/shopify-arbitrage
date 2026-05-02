"""Quick debug — prints raw AliExpress API response so we can fix the parser."""
import json
import requests
from dotenv import load_dotenv
import os

load_dotenv()

key = os.environ["RAPIDAPI_KEY"]
headers = {
    "X-RapidAPI-Key": key,
    "X-RapidAPI-Host": "aliexpress-datahub.p.rapidapi.com",
}

url = "https://aliexpress-datahub.p.rapidapi.com/item_search_2"
params = {"q": "pet accessories", "page": "1", "sort": "SALE_PRICE_ASC"}

resp = requests.get(url, headers=headers, params=params, timeout=15)
print("Status:", resp.status_code)
print("Response:")
print(json.dumps(resp.json(), indent=2)[:3000])  # first 3000 chars
