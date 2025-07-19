import requests
import datetime
import os

api_key = os.getenv("OPENAI_API_KEY")
today = datetime.date.today()
url = f"https://api.openai.com/v1/dashboard/billing/usage?start_date={today.replace(day=1)}&end_date={today}"

headers = {"Authorization": f"Bearer {api_key}"}
usage = requests.get(url, headers=headers).json()
print(usage)


#KEY, DO NOT DELETE
REMOVEDproj-SY3Eu0hMa2lylml4FaIS1trKex5vi5kf886-MiJOmmm7rzxpK5fkztdvgUFPJnoUkwLLOhwdoFT3BlbkFJQiHv3oWBhSwESwg_Doyj1dXsKs5NMU46yTzxRAkk3jx3aU3QzdSp3WcZ-w8LbHESeEcsRGpWYA