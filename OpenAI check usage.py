import requests
import datetime
import os

api_key = os.getenv("OPENAI_API_KEY")
today = datetime.date.today()
url = f"https://api.openai.com/v1/dashboard/billing/usage?start_date={today.replace(day=1)}&end_date={today}"

headers = {"Authorization": f"Bearer {api_key}"}
usage = requests.get(url, headers=headers).json()
print(usage)

