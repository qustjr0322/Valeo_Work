import os
import requests
import subprocess
from dotenv import load_dotenv

load_dotenv()

JIRA_URL = os.getenv("JIRA_URL", "").rstrip("/")
JIRA_PAT = os.getenv("JIRA_PAT")

if not JIRA_URL or not JIRA_PAT:
    print("오류: .env 파일에 JIRA_URL과 JIRA_PAT가 설정되어 있지 않습니다.")
    input("\n엔터 키를 누르면 종료됩니다...")
    exit(1)

headers = {
    "Authorization": f"Bearer {JIRA_PAT}",
    "Accept": "application/json",
    "X-Experimental-Api": "opt-in"
}

def get_sd_comments(issue_id_or_key):
    """Service Desk 전용 댓글(답변) 조회"""
    endpoint = f"{JIRA_URL}/rest/servicedeskapi/request/{issue_id_or_key}/comment"
    res = requests.get(endpoint, headers=headers)
    comments_list = []
    
    if res.status_code == 200:
        values = res.json().get("values", [])
        for c in values:
            author = c.get("author", {}).get("displayName", "익명")
            created = c.get("created", {}).get("friendly", c.get("created", {}).get("jira", ""))[:19].replace("T", " ")
            body = c.get("body", "").strip()
            comments_list.append({
                "author": author,
                "created": created,
                "body": body,
                "public": c.get("public", True)
            })
    return comments_list

def parse_service_desk_response(data):
    """Service Desk API 응답 해석"""
    summary = "제목 없음"
    description = "내용 없음"
    
    for field in data.get("requestFieldValues", []):
        field_id = field.get("fieldId")
        if field_id == "summary":
            summary = field.get("value", summary)
        elif field_id == "description":
            description = field.get("value", description)

    status = data.get("currentStatus", {}).get("status", "Unknown")
    reporter = data.get("reporter", {}).get("displayName", "없음")
    created = data.get("createdDate", {}).get("friendly", "")[:10]
    
    issue_id = data.get("issueId") or data.get("issueKey")
    comments = get_sd_comments(issue_id)

    return {
        "key": data.get("issueKey"),
        "summary": summary,
        "type": "Service Desk Request",
        "status": status,
        "reporter": reporter,
        "assignee": "Service Desk Portal",
        "created": created,
        "description": description,
        "comments": comments
    }

def parse_standard_response(data):
    """일반 Jira REST API 응답 해석"""
    fields = data.get("fields", {})
    
    comments_list = []
    comment_objs = fields.get("comment", {}).get("comments", [])
    for c in comment_objs:
        author = c.get("author", {}).get("displayName", "익명")
        created = c.get("created", "")[:19].replace("T", " ")
        body = c.get("body", "").strip()
        comments_list.append({
            "author": author,
            "created": created,
            "body": body
        })

    return {
        "key": data.get("key"),
        "summary": fields.get("summary", "제목 없음"),
        "type": fields.get("issuetype", {}).get("name", "Unknown"),
        "status": fields.get("status", {}).get("name", "Unknown"),
        "reporter": fields.get("reporter", {}).get("displayName", "없음") if fields.get("reporter") else "없음",
        "assignee": fields.get("assignee", {}).get("displayName", "미지정") if fields.get("assignee") else "미지정",
        "created": fields.get("created", "")[:10],
        "description": fields.get("description") or "내용 없음",
        "comments": comments_list
    }

def save_to_notepad(issue):
    """결과 내용을 텍스트 파일로 저장 후 메모장 열기"""
    filename = f"{issue['key']}.txt"
    
    content = []
    content.append("=" * 65)
    content.append(f"📌 [{issue['key']}] {issue['summary']}")
    content.append("=" * 65)
    content.append(f"• 유형    : {issue['type']}")
    content.append(f"• 상태    : {issue['status']}")
    content.append(f"• 보고자  : {issue['reporter']}")
    content.append(f"• 담당자  : {issue['assignee']}")
    content.append(f"• 생성일  : {issue['created']}")
    content.append("-" * 65)
    content.append("📄 [상세 설명 (Description)]")
    content.append(issue['description'].strip())
    content.append("-" * 65)
    
    comments = issue.get("comments", [])
    content.append(f"💬 [답변 및 댓글 목록 ({len(comments)}개)]")
    if comments:
        for idx, c in enumerate(comments, 1):
            public_tag = "" if c.get("public", True) else " 🔒[내부 메모]"
            content.append(f"\n [{idx}] {c['author']} ({c['created']}){public_tag}")
            content.append(f"    {c['body']}")
    else:
        content.append(" 등록된 답변(댓글)이 없습니다.")
        
    content.append("=" * 65 + "\n")
    
    file_text = "\n".join(content)

    with open(filename, "w", encoding="utf-8") as f:
        f.write(file_text)

    print(f"✅ '{filename}' 메모장 파일 저장 및 실행 완료!")
    
    try:
        os.startfile(filename)
    except AttributeError:
        subprocess.run(["xdg-open" if os.name == "posix" else "open", filename])

def fetch_jira_issue(issue_key):
    # 1. 일반 Jira REST API 시도
    std_endpoint = f"{JIRA_URL}/rest/api/2/issue/{issue_key}?expand=comment"
    res = requests.get(std_endpoint, headers=headers)

    if res.status_code == 200:
        issue = parse_standard_response(res.json())
        save_to_notepad(issue)
        return

    # 2. Service Desk API 시도
    sd_endpoint = f"{JIRA_URL}/rest/servicedeskapi/request/{issue_key}"
    res_sd = requests.get(sd_endpoint, headers=headers)

    if res_sd.status_code == 200:
        issue = parse_service_desk_response(res_sd.json())
        save_to_notepad(issue)
        return

    # 3. 실패 처리
    if res_sd.status_code == 404 and res.status_code == 404:
        print(f"❌ 티켓을 찾을 수 없습니다: '{issue_key}'")
    else:
        print(f"❌ 조회 실패 (일반 API: {res.status_code}, ServiceDesk API: {res_sd.status_code})")

if __name__ == "__main__":
    print("=" * 60)
    print(" 🎫 Jira 티켓 조회 자동화 프로그램")
    print(" (종료를 원하시면 'q' 또는 'exit'를 입력하세요)")
    print("=" * 60)

    # 무한 루프 적용으로 연속 입력 가능
    while True:
        try:
            issue_key = input("\n조회할 Jira 티켓 번호를 입력하세요: ").strip()
            
            # 종료 조건 체크
            if issue_key.lower() in ["q", "quit", "exit", ""]:
                print("프로그램을 종료합니다.")
                break
                
            fetch_jira_issue(issue_key)
            
        except KeyboardInterrupt:
            print("\n프로그램을 종료합니다.")
            break
        except Exception as e:
            print(f"오류가 발생했습니다: {e}")
