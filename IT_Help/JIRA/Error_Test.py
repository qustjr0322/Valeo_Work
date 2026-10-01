import os
import requests
from dotenv import load_dotenv

load_dotenv()

JIRA_URL = os.getenv("JIRA_URL", "").rstrip("/")
JIRA_PAT = os.getenv("JIRA_PAT")

headers = {
    "Authorization": f"Bearer {JIRA_PAT}",
    "Accept": "application/json",
    "X-Experimental-Api": "opt-in"
}

#에러나는 티켓 번호 입력
issue_key = "VSD-1888915"

print("--- 1. 403 상세 에러 메시지 확인 ---")
url_std = f"{JIRA_URL}/rest/api/2/issue/{issue_key}"
res_std = requests.get(url_std, headers=headers)
print(f"일반 API 상태 코드: {res_std.status_code}")
print(f"일반 API 응답 내용: {res_std.text}\n")

print("--- 2. Service Desk 전용 API 테스트 ---")
url_sd = f"{JIRA_URL}/rest/servicedeskapi/request/{issue_key}"
res_sd = requests.get(url_sd, headers=headers)
print(f"Service Desk API 상태 코드: {res_sd.status_code}")
if res_sd.status_code == 200:
    print("Service Desk API 접속 성공!")
    print(res_sd.json())
else:
    print(f"Service Desk API 응답 내용: {res_sd.text}")
