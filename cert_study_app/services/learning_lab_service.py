from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CONTENT_STATUSES = ["generated", "reviewed", "approved", "rejected"]


@dataclass(frozen=True)
class RoadmapStep:
    title: str
    description: str
    level: str = "기초"


@dataclass(frozen=True)
class LessonCard:
    id: str
    track: str
    certification: str
    title: str
    summary: str
    example: str
    common_mistake: str
    keywords: list[str]
    source_id: str
    status: str = "approved"
    details: tuple[str, ...] = ()
    level: str = "입문"
    related_practices: tuple[str, ...] = ()


@dataclass(frozen=True)
class LabQuiz:
    id: str
    lesson_id: str
    track: str
    question_type: str
    question: str
    options: list[str]
    answer: str
    explanation: str
    difficulty: str = "easy"
    source_id: str = "manual-linux-basic"
    status: str = "approved"


@dataclass(frozen=True)
class PracticeTask:
    id: str
    track: str
    title: str
    task_description: str
    expected_command: str
    grading_conditions: list[str]
    hint: str
    explanation: str
    difficulty: str = "easy"
    status: str = "approved"
    takeaway: str = ""


TRACKS = [
    {
        "id": "linux",
        "name": "Linux",
        "description": "터미널, 파일, 권한, 프로세스, 서비스 관리 기초",
        "priority": 1,
        "is_active": True,
    },
    {
        "id": "azure",
        "name": "Azure",
        "description": "Azure 관리자 역할과 AZ-104 시험 대비",
        "priority": 2,
        "is_active": True,
    },
    {
        "id": "tool_docs",
        "name": "Tool Docs",
        "description": "Ollama, LangChain, Streamlit, Hugging Face 공식 문서 기반 학습",
        "priority": 3,
        "is_active": True,
    },
    {"id": "git", "name": "Git", "description": "버전 관리 기본기", "priority": 4, "is_active": False},
    {"id": "python", "name": "Python", "description": "기초 문법과 자동화", "priority": 5, "is_active": False},
    {"id": "sql", "name": "SQL", "description": "조회와 데이터 모델링 기초", "priority": 6, "is_active": False},
    {"id": "docker", "name": "Docker", "description": "컨테이너 이미지와 실행 환경", "priority": 7, "is_active": False},
    {"id": "kubernetes", "name": "Kubernetes", "description": "컨테이너 오케스트레이션 기초", "priority": 8, "is_active": False},
]


CERTIFICATIONS = {
    "azure": [
        {
            "id": "az-104",
            "name": "AZ-104",
            "description": "Microsoft Azure Administrator",
            "readiness": "ready_with_questions",
            "study_mode": "문제은행 기반",
        },
    ],
    "linux": [
        {
            "id": "lfcs",
            "name": "LFCS",
            "description": "Linux Foundation Certified Systems Administrator",
            "readiness": "practice_based",
            "study_mode": "실습 과제 기반",
        },
        {
            "id": "linux-master",
            "name": "리눅스마스터",
            "description": "리눅스 명령어와 운영체제 개념 중심 국내 자격증",
            "readiness": "concept_quiz_based",
            "study_mode": "개념/확인 퀴즈 기반",
        },
    ],
    "tool_docs": [
        {
            "id": "tool-docs",
            "name": "Docs Study",
            "description": "공식 문서 기반 도구 학습",
            "readiness": "docs_based",
            "study_mode": "공식 문서 기반",
        },
    ],
}


ROADMAPS = {
    "linux": [
        RoadmapStep("Essential Commands", "파일 탐색, 검색, 압축, 리다이렉션, 기본 텍스트 처리를 익힙니다.", "LFCS 핵심"),
        RoadmapStep("Users & Groups", "사용자, 그룹, sudo, 계정 정책을 관리합니다.", "LFCS 핵심"),
        RoadmapStep("Permissions", "rwx, chmod, chown, umask, 특수 권한을 정리합니다.", "LFCS 핵심"),
        RoadmapStep("Processes & Services", "ps, kill, systemctl, journalctl로 프로세스와 서비스를 다룹니다.", "LFCS 실무"),
        RoadmapStep("Networking", "ip, ss, ping, curl, DNS, 방화벽 기초를 학습합니다.", "LFCS 실무"),
        RoadmapStep("Storage", "파티션, 파일시스템, mount, swap, LVM 개념을 정리합니다.", "LFCS 실무"),
        RoadmapStep("Package & Software", "apt, dnf/yum, repository, 업데이트 흐름을 익힙니다.", "LFCS 실무"),
        RoadmapStep("Logs & Troubleshooting", "로그 위치와 장애 확인 루틴을 연습합니다.", "LFCS 실무"),
        RoadmapStep("Security Basics", "SSH, 권한, 서비스 노출, 기본 보안 점검을 정리합니다.", "LFCS 실무"),
        RoadmapStep("LFCS Style Labs", "명령어를 직접 입력해 조건을 만족하는지 확인합니다.", "실습"),
    ],
    "azure": [
        RoadmapStep("Identity & Governance", "Entra ID, RBAC, Policy, Resource Group, Management Group을 정리합니다.", "AZ-104 20-25%"),
        RoadmapStep("Storage", "Storage Account, Blob, Files, redundancy, lifecycle를 학습합니다.", "AZ-104 15-20%"),
        RoadmapStep("Compute", "VM, Scale Set, App Service, Container 리소스를 학습합니다.", "AZ-104 20-25%"),
        RoadmapStep("Networking", "VNet, Subnet, NSG, Peering, Load Balancer, DNS를 학습합니다.", "AZ-104 15-20%"),
        RoadmapStep("Monitor & Recovery", "Azure Monitor, Log Analytics, Backup, Site Recovery를 정리합니다.", "AZ-104 10-15%"),
        RoadmapStep("AZ-104 문제풀이", "기존 문제은행으로 시험 스타일을 연습합니다.", "시험 대비"),
    ],
    "tool_docs": [
        RoadmapStep("Ollama", "로컬 모델 실행, 모델 관리, API 호출 흐름을 학습합니다.", "공식 Docs"),
        RoadmapStep("LangChain", "Chain, Retriever, Tool, Agent의 기본 쓰임을 정리합니다.", "공식 Docs"),
        RoadmapStep("Streamlit", "상태 관리, 입력 위젯, 배포 흐름을 학습합니다.", "공식 Docs"),
        RoadmapStep("Hugging Face", "Spaces, Models, Datasets, Secrets 관리 흐름을 익힙니다.", "공식 Docs"),
    ],
}


LESSONS = []



QUIZZES = [
    LabQuiz(
        "linux-q1",
        "linux-pwd",
        "linux",
        "multiple_choice",
        "현재 디렉터리 위치를 확인하는 명령어는?",
        ["ls", "pwd", "cd", "mkdir"],
        "pwd",
        "`pwd`는 print working directory의 약자로 현재 작업 중인 디렉터리의 경로를 출력합니다.",
    ),
    LabQuiz(
        "linux-q2",
        "linux-chmod",
        "linux",
        "multiple_choice",
        "파일 권한을 변경하는 명령어는?",
        ["chmod", "chown", "grep", "kill"],
        "chmod",
        "`chmod`는 파일이나 디렉터리의 권한을 변경할 때 사용합니다.",
    ),
    LabQuiz(
        "linux-q3",
        "linux-grep",
        "linux",
        "multiple_choice",
        "텍스트에서 특정 문자열을 검색하는 명령어는?",
        ["cat", "grep", "touch", "mv"],
        "grep",
        "`grep`은 파일이나 출력 결과에서 특정 문자열 패턴을 검색합니다.",
        source_id="linux-grep-manual",
    ),
    LabQuiz(
        "linux-q4",
        "linux-mkdir",
        "linux",
        "command",
        "`practice` 디렉터리를 만드는 명령어를 입력하세요.",
        [],
        "mkdir practice",
        "`mkdir practice`는 현재 위치에 practice 디렉터리를 생성합니다.",
    ),
    LabQuiz(
        "linux-q5",
        "linux-touch",
        "linux",
        "command",
        "`hello.txt` 빈 파일을 만드는 명령어를 입력하세요.",
        [],
        "touch hello.txt",
        "`touch hello.txt`는 빈 파일을 만들거나 기존 파일의 수정 시간을 갱신합니다.",
    ),
    LabQuiz(
        "linux-q6",
        "linux-apt",
        "linux",
        "command",
        "Ubuntu에서 패키지 목록을 갱신하는 명령어를 입력하세요.",
        [],
        "sudo apt update",
        "`sudo apt update`는 저장소의 패키지 목록을 갱신합니다. 실제 패키지 업그레이드는 `sudo apt upgrade`입니다.",
        source_id="ubuntu-package-management",
    ),
    LabQuiz(
        "linux-q7",
        "linux-ufw",
        "linux",
        "command",
        "Ubuntu에서 SSH 접속 포트 22번을 허용하는 ufw 명령어를 입력하세요.",
        [],
        "sudo ufw allow 22",
        "`sudo ufw allow 22`는 22번 포트를 허용합니다. 원격 서버에서는 ufw enable 전에 SSH 포트 허용 여부를 확인해야 합니다.",
        source_id="ubuntu-firewall",
    ),
    LabQuiz(
        "azure-q1",
        "azure-rg",
        "azure",
        "multiple_choice",
        "AZ-104에서 Resource Group의 가장 중요한 특징으로 맞는 것은?",
        ["가상 네트워크 주소 공간을 정의한다", "Azure 리소스를 논리적으로 묶어 관리한다", "사용자 암호를 재설정한다", "VM 크기를 자동으로 조정한다"],
        "Azure 리소스를 논리적으로 묶어 관리한다",
        "Resource Group은 여러 Azure 리소스를 논리적으로 묶고 수명주기와 권한 관리를 돕는 단위입니다.",
        source_id="manual-az104-basic",
    ),
    LabQuiz(
        "azure-q2",
        "azure-storage",
        "azure",
        "multiple_choice",
        "Storage Account에서 Blob Storage가 주로 저장하는 데이터 유형은?",
        ["개체 데이터", "가상 네트워크 라우팅 테이블", "Entra ID 사용자", "Azure Policy 정의만"],
        "개체 데이터",
        "Blob Storage는 로그, 이미지, 백업 파일 같은 비정형 개체 데이터를 저장하는 데 사용됩니다.",
        source_id="azure-storage-account",
    ),
    LabQuiz(
        "azure-q3",
        "azure-vnet",
        "azure",
        "multiple_choice",
        "VNet을 설계할 때 먼저 확인해야 하는 것은?",
        ["주소 공간이 겹치지 않는지", "모든 VM이 같은 이름인지", "모든 리소스가 같은 태그인지", "Storage Account access tier가 Archive인지"],
        "주소 공간이 겹치지 않는지",
        "VNet 주소 공간이 다른 네트워크와 겹치면 피어링이나 하이브리드 연결 설계에 문제가 생길 수 있습니다.",
        source_id="azure-vnet-overview",
    ),
    LabQuiz(
        "docs-q1",
        "docs-streamlit-state",
        "tool_docs",
        "multiple_choice",
        "Streamlit에서 rerun 이후에도 값을 유지하는 데 가장 적합한 것은?",
        ["일반 지역 변수", "st.session_state", "print", "requirements.txt"],
        "st.session_state",
        "Streamlit은 상호작용 때 스크립트를 다시 실행하므로 지속 상태는 session_state에 저장하는 것이 적합합니다.",
        source_id="official-docs-streamlit",
    ),
    LabQuiz(
        "docs-q3",
        "docs-langchain-rag",
        "tool_docs",
        "multiple_choice",
        "LangChain RAG에서 질문과 관련 문서를 찾아 LLM에 넘기는 역할에 가장 가까운 것은?",
        ["Retriever", "Theme config", "Space Secret", "chmod"],
        "Retriever",
        "Retriever는 벡터 검색이나 키워드 검색 등을 통해 질문과 관련 있는 문서를 찾아 체인에 전달합니다.",
        source_id="official-docs-langchain",
    ),
    LabQuiz(
        "docs-q2",
        "docs-hf-spaces",
        "tool_docs",
        "multiple_choice",
        "Hugging Face Space에서 API 키 같은 비밀값을 저장해야 하는 위치는?",
        ["README 본문", "Git 커밋", "Space Secrets", "앱 화면 캡션"],
        "Space Secrets",
        "배포 환경의 비밀값은 Space Settings의 Secrets에 저장하고 코드에는 포함하지 않는 것이 안전합니다.",
        source_id="official-docs-huggingface",
    ),
]


QUIZZES.extend(
    [
        LabQuiz(
            "linux-q8",
            "linux-chown",
            "linux",
            "multiple_choice",
            "`chmod`와 비교했을 때 `chown`의 주된 역할은?",
            ["파일 내용 출력", "소유자/그룹 변경", "프로세스 종료", "패키지 설치"],
            "소유자/그룹 변경",
            "`chown`은 owner/group을 바꾸고, `chmod`는 권한 비트를 바꿉니다.",
            source_id="manual-linux-basic",
        ),
        LabQuiz(
            "linux-q9",
            "linux-umask",
            "linux",
            "multiple_choice",
            "`umask 022`의 의미로 가장 가까운 것은?",
            ["모든 파일을 022 권한으로 만든다", "그룹/기타 사용자 쓰기 권한을 기본 제거한다", "root만 로그인하게 한다", "디스크를 마운트한다"],
            "그룹/기타 사용자 쓰기 권한을 기본 제거한다",
            "`umask`는 새 파일/디렉터리에서 제거할 권한을 뜻합니다.",
            source_id="manual-linux-basic",
        ),
        LabQuiz(
            "linux-q10",
            "linux-find",
            "linux",
            "command",
            "`/var/log` 아래의 `.log` 파일을 찾는 find 명령어를 입력하세요.",
            [],
            "find /var/log -type f -name '*.log'",
            "`find 경로 -type f -name 패턴` 형태로 파일 타입과 이름 패턴을 함께 지정할 수 있습니다.",
            source_id="manual-linux-basic",
        ),
        LabQuiz(
            "linux-q11",
            "linux-pipe-redirect",
            "linux",
            "multiple_choice",
            "`>>` 리다이렉션의 의미는?",
            ["파일 덮어쓰기", "파일 끝에 이어쓰기", "표준 에러 무시", "명령을 백그라운드 실행"],
            "파일 끝에 이어쓰기",
            "`>`는 덮어쓰기, `>>`는 이어쓰기입니다.",
            source_id="manual-linux-basic",
        ),
        LabQuiz(
            "linux-q12",
            "linux-tar",
            "linux",
            "command",
            "`logs` 디렉터리를 gzip 압축 tar 파일 `logs.tar.gz`로 만드는 명령어를 입력하세요.",
            [],
            "tar -czf logs.tar.gz logs",
            "`-c`는 생성, `-z`는 gzip, `-f`는 파일명을 지정합니다.",
            source_id="manual-linux-basic",
        ),
        LabQuiz(
            "linux-q13",
            "linux-systemctl",
            "linux",
            "multiple_choice",
            "`systemctl enable nginx`의 의미는?",
            ["지금 한 번만 실행", "부팅 시 자동 시작 등록", "패키지 제거", "로그 삭제"],
            "부팅 시 자동 시작 등록",
            "`start`는 즉시 실행, `enable`은 부팅 시 자동 시작 설정입니다.",
            source_id="linux-systemd-systemctl",
        ),
        LabQuiz(
            "linux-q14",
            "linux-journalctl",
            "linux",
            "command",
            "nginx 서비스 로그를 확인하는 journalctl 명령어를 입력하세요.",
            [],
            "journalctl -u nginx",
            "`journalctl -u 서비스명`은 특정 systemd unit 로그를 확인합니다.",
            source_id="linux-systemd-systemctl",
        ),
        LabQuiz(
            "linux-q15",
            "linux-ip-ss",
            "linux",
            "multiple_choice",
            "현재 시스템의 listening 포트를 확인하는 데 가장 가까운 명령은?",
            ["ss -tulpen", "touch port", "chmod 755", "tar -czf"],
            "ss -tulpen",
            "`ss -tulpen`은 TCP/UDP listening 소켓과 프로세스 정보를 확인할 때 유용합니다.",
            source_id="linux-man7-ip",
        ),
        LabQuiz(
            "linux-q16",
            "linux-df-du-mount",
            "linux",
            "multiple_choice",
            "`df -h`와 `du -sh /var/log`의 차이로 맞는 것은?",
            ["둘 다 패키지 설치 명령이다", "`df`는 파일시스템, `du`는 경로별 사용량 확인에 가깝다", "`du`만 네트워크 상태를 본다", "`df`는 사용자 암호 변경 명령이다"],
            "`df`는 파일시스템, `du`는 경로별 사용량 확인에 가깝다",
            "`df`는 마운트된 파일시스템 단위, `du`는 특정 파일/디렉터리 용량 확인에 적합합니다.",
            source_id="ubuntu-storage",
        ),
        LabQuiz(
            "azure-q4",
            "azure-rbac",
            "azure",
            "multiple_choice",
            "Azure RBAC에서 권한이 적용되는 범위를 뜻하는 말은?",
            ["Scope", "Access tier", "Subnet mask", "Archive"],
            "Scope",
            "RBAC role assignment는 management group, subscription, resource group, resource 같은 scope에 적용됩니다.",
            source_id="azure-rbac-overview",
        ),
        LabQuiz(
            "azure-q5",
            "azure-policy",
            "azure",
            "multiple_choice",
            "Azure Policy의 주된 목적은?",
            ["VM CPU를 즉시 늘린다", "리소스 상태를 조직 규칙에 맞게 평가/제어한다", "Blob을 다운로드한다", "DNS 레코드만 생성한다"],
            "리소스 상태를 조직 규칙에 맞게 평가/제어한다",
            "Azure Policy는 deny/audit 같은 효과로 리소스 규정 준수를 관리합니다.",
            source_id="azure-policy-overview",
        ),
        LabQuiz(
            "azure-q6",
            "azure-vm",
            "azure",
            "multiple_choice",
            "Azure VM을 이해할 때 함께 봐야 할 리소스로 가장 자연스러운 조합은?",
            ["Disk, NIC, VNet, NSG", "Only DNS TXT record", "Only Policy initiative", "Only Blob tier"],
            "Disk, NIC, VNet, NSG",
            "VM은 compute뿐 아니라 디스크와 네트워크 리소스가 함께 구성됩니다.",
            source_id="azure-vm-overview",
        ),
        LabQuiz(
            "azure-q7",
            "azure-nsg",
            "azure",
            "multiple_choice",
            "NSG 규칙 평가에서 먼저 적용되는 규칙은?",
            ["우선순위 숫자가 낮은 규칙", "이름이 긴 규칙", "나중에 만든 규칙", "항상 Deny 규칙"],
            "우선순위 숫자가 낮은 규칙",
            "NSG는 priority 숫자가 낮을수록 먼저 평가됩니다.",
            source_id="azure-nsg-overview",
        ),
        LabQuiz(
            "azure-q8",
            "azure-app-gateway",
            "azure",
            "multiple_choice",
            "Application Gateway가 Load Balancer와 비교해 더 잘 다루는 영역은?",
            ["HTTP path 기반 L7 라우팅", "파일 권한 변경", "패키지 목록 갱신", "프로세스 종료"],
            "HTTP path 기반 L7 라우팅",
            "Application Gateway는 HTTP/HTTPS L7 라우팅과 WAF 같은 웹 계층 기능에 적합합니다.",
            source_id="azure-app-gateway-overview",
        ),
        LabQuiz(
            "azure-q9",
            "azure-blob-tier",
            "azure",
            "multiple_choice",
            "Archive tier의 특징으로 가장 맞는 것은?",
            ["항상 즉시 읽기 가능", "오프라인 계층이라 읽기 전에 rehydrate가 필요할 수 있음", "VM 크기 설정", "RBAC 역할 이름"],
            "오프라인 계층이라 읽기 전에 rehydrate가 필요할 수 있음",
            "Archive는 장기 보관 비용을 낮추는 대신 즉시 접근성이 떨어질 수 있습니다.",
            source_id="azure-blob-access-tiers",
        ),
        LabQuiz(
            "azure-q10",
            "azure-log-analytics",
            "azure",
            "multiple_choice",
            "Log Analytics에서 로그 데이터를 조회할 때 주로 사용하는 쿼리 언어는?",
            ["KQL", "Bash", "YAML only", "Markdown"],
            "KQL",
            "Log Analytics는 KQL로 로그를 필터링하고 분석합니다.",
            source_id="azure-log-analytics-overview",
        ),
        LabQuiz(
            "docs-q4",
            "docs-lcel",
            "tool_docs",
            "multiple_choice",
            "LCEL에서 `prompt | llm | parser`처럼 연결하는 방식의 장점은?",
            ["체인 흐름을 명시적으로 조합할 수 있다", "서버 방화벽을 연다", "파일 권한을 바꾼다", "Blob tier를 변경한다"],
            "체인 흐름을 명시적으로 조합할 수 있다",
            "LCEL은 Runnable을 파이프처럼 연결해 입력/출력 흐름을 구성합니다.",
            source_id="official-docs-langchain",
        ),
        LabQuiz(
            "docs-q5",
            "docs-vectorstore",
            "tool_docs",
            "multiple_choice",
            "VectorStore를 사용할 때 임베딩 모델을 바꾸면 주의할 점은?",
            ["기존 벡터와 차원이 달라질 수 있다", "항상 같은 컬렉션에 섞어야 한다", "DB 암호가 자동 공개된다", "UI 버튼이 사라진다"],
            "기존 벡터와 차원이 달라질 수 있다",
            "임베딩 모델별로 컬렉션을 분리하면 차원 불일치 문제를 줄일 수 있습니다.",
            source_id="official-docs-langchain",
        ),
        LabQuiz(
            "docs-q6",
            "docs-streamlit-cache",
            "tool_docs",
            "multiple_choice",
            "Streamlit에서 모델/DB 연결 같은 리소스 초기화에 더 적합한 캐시는?",
            ["st.cache_resource", "st.write", "st.button", "st.caption"],
            "st.cache_resource",
            "`st.cache_resource`는 모델, DB connection 같은 공유 리소스 캐시에 적합합니다.",
            source_id="official-docs-streamlit",
        ),
        LabQuiz(
            "docs-q7",
            "docs-ollama-api",
            "tool_docs",
            "multiple_choice",
            "Ollama API를 호출하기 전에 필요한 조건으로 가장 맞는 것은?",
            ["Ollama 서버가 실행 중이고 모델이 준비되어 있어야 한다", "ufw가 반드시 꺼져 있어야 한다", "Azure VMSS가 있어야 한다", "README에 API 키를 적어야 한다"],
            "Ollama 서버가 실행 중이고 모델이 준비되어 있어야 한다",
            "로컬 Ollama 서버와 모델이 준비되지 않으면 generate/chat API 호출이 실패합니다.",
            source_id="official-docs-ollama",
        ),
    ]
)


PRACTICE_TASKS = [
    PracticeTask(
        "linux-lab-1",
        "linux",
        "현재 위치 확인",
        "현재 작업 중인 디렉터리를 확인하세요.",
        "pwd",
        ["pwd"],
        "현재 위치는 working directory라고 부릅니다.",
        "`pwd`를 입력하면 현재 디렉터리의 절대 경로를 볼 수 있습니다.",
    ),
    PracticeTask(
        "linux-lab-2",
        "linux",
        "디렉터리 생성",
        "`practice` 디렉터리를 생성하세요.",
        "mkdir practice",
        ["mkdir", "practice"],
        "디렉터리를 만들 때는 mkdir을 사용합니다.",
        "`mkdir practice`는 practice라는 새 디렉터리를 만듭니다.",
    ),
    PracticeTask(
        "linux-lab-3",
        "linux",
        "파일 생성",
        "`hello.txt` 파일을 생성하세요.",
        "touch hello.txt",
        ["touch", "hello.txt"],
        "빈 파일을 빠르게 만들 때 touch를 쓸 수 있습니다.",
        "`touch hello.txt`는 hello.txt 파일을 만듭니다.",
    ),
    PracticeTask(
        "linux-lab-4",
        "linux",
        "파일 내용 출력",
        "`hello.txt` 내용을 출력하세요.",
        "cat hello.txt",
        ["cat", "hello.txt"],
        "파일 내용을 표준 출력으로 볼 때 cat을 사용합니다.",
        "`cat hello.txt`는 파일 내용을 화면에 출력합니다.",
    ),
    PracticeTask(
        "linux-lab-5",
        "linux",
        "자세한 목록 확인",
        "현재 디렉터리의 파일 목록을 자세히 확인하세요.",
        "ls -al",
        ["ls", "-"],
        "`-a`와 `-l`을 함께 쓰면 숨김 파일과 자세한 정보를 볼 수 있습니다.",
        "`ls -al` 또는 `ls -la`를 사용할 수 있습니다.",
    ),
]


PRACTICE_TASKS.extend(
    [
        PracticeTask(
            "linux-lab-6",
            "linux",
            "소유자 변경",
            "`app.log` 파일의 소유자를 `app` 사용자와 `app` 그룹으로 변경하세요.",
            "sudo chown app:app app.log",
            ["chown", "app:app", "app.log"],
            "소유자와 그룹은 `user:group` 형태로 함께 지정할 수 있습니다.",
            "`sudo chown app:app app.log`는 app.log의 소유자와 그룹을 app으로 변경합니다.",
        ),
        PracticeTask(
            "linux-lab-7",
            "linux",
            "로그 파일 검색",
            "`/var/log` 아래에서 `.log` 파일을 검색하세요.",
            "find /var/log -type f -name '*.log'",
            ["find", "/var/log", "-type", "f", "-name"],
            "파일 조건 검색은 find가 적합합니다.",
            "`find /var/log -type f -name '*.log'`는 /var/log 아래의 .log 파일을 찾습니다.",
        ),
        PracticeTask(
            "linux-lab-8",
            "linux",
            "출력 이어쓰기",
            "`hello` 문자열을 `note.txt` 파일 끝에 이어 쓰세요.",
            "echo hello >> note.txt",
            ["echo", "hello", ">>", "note.txt"],
            "`>>`는 파일 끝에 이어 씁니다.",
            "`echo hello >> note.txt`는 note.txt 뒤에 hello 한 줄을 추가합니다.",
        ),
        PracticeTask(
            "linux-lab-9",
            "linux",
            "tar 아카이브 생성",
            "`logs` 디렉터리를 `logs.tar.gz` 파일로 압축하세요.",
            "tar -czf logs.tar.gz logs",
            ["tar", "-czf", "logs.tar.gz", "logs"],
            "`-c` 생성, `-z` gzip, `-f` 파일명 지정입니다.",
            "`tar -czf logs.tar.gz logs`는 logs 디렉터리를 gzip 압축 tar 파일로 만듭니다.",
        ),
        PracticeTask(
            "linux-lab-10",
            "linux",
            "서비스 상태 확인",
            "`nginx` 서비스 상태를 확인하세요.",
            "systemctl status nginx",
            ["systemctl", "status", "nginx"],
            "서비스 상태는 systemctl status로 먼저 확인합니다.",
            "`systemctl status nginx`는 nginx 서비스의 실행 상태와 최근 로그 힌트를 보여줍니다.",
        ),
        PracticeTask(
            "linux-lab-11",
            "linux",
            "서비스 로그 확인",
            "`nginx` 서비스 로그를 확인하세요.",
            "journalctl -u nginx",
            ["journalctl", "-u", "nginx"],
            "특정 unit 로그는 `journalctl -u`로 확인합니다.",
            "`journalctl -u nginx`는 nginx systemd unit 로그를 보여줍니다.",
        ),
        PracticeTask(
            "linux-lab-12",
            "linux",
            "패키지 목록 갱신",
            "Ubuntu 패키지 목록을 갱신하세요.",
            "sudo apt update",
            ["apt", "update"],
            "`update`와 `upgrade`를 구분하세요.",
            "`sudo apt update`는 저장소 패키지 목록을 갱신합니다.",
        ),
        PracticeTask(
            "linux-lab-13",
            "linux",
            "SSH 포트 허용",
            "ufw에서 SSH 22번 포트를 허용하세요.",
            "sudo ufw allow 22",
            ["ufw", "allow", "22"],
            "원격 서버에서는 방화벽 활성화 전에 SSH 허용 여부를 확인하세요.",
            "`sudo ufw allow 22`는 22번 포트를 허용합니다.",
        ),
    ]
)




QUIZZES.extend(
    [
        LabQuiz(
            "linux-q17",
            "linux-useradd",
            "linux",
            "command",
            "`devuser` 사용자를 홈 디렉터리와 함께 생성하는 명령어를 입력하세요.",
            [],
            "sudo useradd -m devuser",
            "`useradd -m`은 홈 디렉터리 생성을 함께 처리합니다.",
            source_id="ubuntu-user-management",
        ),
        LabQuiz("linux-q18", "linux-usermod", "linux", "command", "`devuser`를 sudo 그룹에 추가하는 명령어를 입력하세요.", [], "sudo usermod -aG sudo devuser", "`-aG`는 기존 보조 그룹을 유지하면서 새 그룹을 추가합니다.", source_id="ubuntu-user-management"),
        LabQuiz("linux-q19", "linux-sudoers", "linux", "multiple_choice", "sudoers 파일을 안전하게 편집하는 명령은?", ["visudo", "cat", "touch", "tar"], "visudo", "`visudo`는 sudoers 문법 검사를 도와 sudo 설정 오류를 줄입니다.", source_id="ubuntu-user-management"),
        LabQuiz("linux-q20", "linux-special-perms", "linux", "multiple_choice", "공용 디렉터리에서 타인 파일 삭제를 제한하는 특수 권한은?", ["sticky bit", "setuid", "umask", "swap"], "sticky bit", "sticky bit는 /tmp 같은 공용 디렉터리에서 자주 쓰입니다.", source_id="manual-linux-basic"),
        LabQuiz("linux-q21", "linux-ssh-key", "linux", "multiple_choice", "SSH 키 인증에서 서버의 authorized_keys에 들어가는 것은?", ["공개키", "개인키", "root 암호", "swap 파일"], "공개키", "개인키는 클라이언트가 보관하고 공개키를 서버에 등록합니다.", source_id="ubuntu-server-docs"),
        LabQuiz("linux-q22", "linux-dns-resolve", "linux", "multiple_choice", "IP 통신은 되는데 도메인 접속만 실패할 때 먼저 의심할 영역은?", ["DNS", "chmod", "tar", "umask"], "DNS", "도메인 이름 해석 실패는 DNS 설정 문제일 수 있습니다.", source_id="ubuntu-networking"),
        LabQuiz("linux-q23", "linux-route", "linux", "command", "기본 라우팅 정보를 확인하는 명령어를 입력하세요.", [], "ip route", "`ip route`는 기본 게이트웨이와 라우팅 테이블을 확인합니다.", source_id="linux-man7-ip"),
        LabQuiz("linux-q24", "linux-cron", "linux", "multiple_choice", "사용자별 반복 작업을 편집하는 명령은?", ["crontab -e", "journalctl -u", "lsblk", "swapon"], "crontab -e", "`crontab -e`는 사용자 cron 작업을 편집합니다.", source_id="ubuntu-server-docs"),
        LabQuiz("linux-q25", "linux-lsblk", "linux", "multiple_choice", "블록 장치와 파티션 구조를 확인하는 명령은?", ["lsblk", "grep", "passwd", "curl"], "lsblk", "`lsblk`는 디스크/파티션/마운트 관계를 보기 좋습니다.", source_id="ubuntu-storage"),
        LabQuiz("linux-q26", "linux-fstab", "linux", "multiple_choice", "부팅 시 자동 마운트 설정을 담는 파일은?", ["/etc/fstab", "/etc/hosts", "/etc/passwd", "/var/log/auth.log"], "/etc/fstab", "`/etc/fstab`은 파일시스템 자동 마운트 설정을 담습니다.", source_id="ubuntu-storage"),
        LabQuiz("linux-q27", "linux-exit-code", "linux", "multiple_choice", "직전 명령의 exit code를 확인하는 표현은?", ["echo $?", "echo $PATH", "pwd", "id"], "echo $?", "`$?`는 직전 명령의 종료 코드를 담습니다.", source_id="linux-bash-cd"),
        LabQuiz("linux-q28", "linux-remove-purge", "linux", "multiple_choice", "`apt purge`가 `apt remove`와 비교해 더 정리하는 것은?", ["설정 파일", "CPU core", "VNet", "DNS zone"], "설정 파일", "`purge`는 패키지 설정 파일까지 제거하는 데 사용합니다.", source_id="ubuntu-package-management"),
        LabQuiz("azure-q11", "azure-entra-id", "azure", "multiple_choice", "인증과 사용자/그룹 ID 관리의 중심 서비스는?", ["Microsoft Entra ID", "Azure Blob Tier", "Load Balancer Probe", "Recovery Point"], "Microsoft Entra ID", "Entra ID는 ID와 인증의 중심이고 RBAC는 Azure 리소스 권한 제어에 연결됩니다.", source_id="manual-az104-basic"),
        LabQuiz("azure-q12", "azure-management-group", "azure", "multiple_choice", "여러 subscription에 정책을 계층적으로 적용하기 좋은 범위는?", ["Management Group", "NIC", "Blob", "VM disk"], "Management Group", "Management Group은 subscription을 묶어 거버넌스를 적용하는 상위 범위입니다.", source_id="manual-az104-basic"),
        LabQuiz("azure-q13", "azure-resource-lock", "azure", "multiple_choice", "중요 리소스의 실수 삭제를 막는 데 적합한 기능은?", ["Resource Lock", "Access tier", "NAT rule", "KQL"], "Resource Lock", "CanNotDelete lock은 삭제 방지에 사용됩니다.", source_id="manual-az104-basic"),
        LabQuiz("azure-q14", "azure-sas", "azure", "multiple_choice", "Storage에 제한된 기간/권한으로 접근하게 하는 URL 토큰은?", ["SAS", "NSG", "VMSS", "KQL"], "SAS", "Shared Access Signature는 Storage 접근 권한을 제한적으로 위임합니다.", source_id="azure-storage-account"),
        LabQuiz("azure-q15", "azure-storage-redundancy", "azure", "multiple_choice", "지역 간 복제를 고려하는 Storage redundancy 옵션으로 가장 가까운 것은?", ["GRS", "LRS only", "NSG", "UFW"], "GRS", "GRS는 geo-redundant storage로 지역 간 복제를 제공합니다.", source_id="azure-storage-account"),
        LabQuiz("azure-q16", "azure-availability-set", "azure", "multiple_choice", "Availability Set에서 VM 장애 분산에 쓰이는 개념은?", ["Fault domain", "Blob container", "SAS token", "Private DNS record"], "Fault domain", "Fault domain/update domain은 Availability Set의 핵심 개념입니다.", source_id="azure-vm-overview"),
        LabQuiz("azure-q17", "azure-vnet-peering", "azure", "multiple_choice", "VNet Peering이 실패할 수 있는 대표 원인은?", ["주소 공간 겹침", "파일 권한 755", "cron 미설정", "Archive tier 사용"], "주소 공간 겹침", "VNet 주소 공간이 겹치면 peering할 수 없습니다.", source_id="azure-vnet-overview"),
        LabQuiz("azure-q18", "azure-load-balancer-probe", "azure", "multiple_choice", "Backend VM이 트래픽을 받을 수 있는지 판단하는 Load Balancer 구성은?", ["Health probe", "Tag", "SAS", "Key Vault secret"], "Health probe", "Probe가 실패하면 backend pool VM은 트래픽 대상에서 제외될 수 있습니다.", source_id="azure-load-balancer"),
        LabQuiz("azure-q19", "azure-private-dns", "azure", "multiple_choice", "Private Endpoint 접속 문제에서 함께 확인해야 할 대표 영역은?", ["Private DNS", "umask", "tar", "cron"], "Private DNS", "Private Endpoint는 DNS가 올바른 private IP로 해석되는지 중요합니다.", source_id="azure-dns-overview"),
        LabQuiz("azure-q20", "azure-alert", "azure", "multiple_choice", "Azure Monitor Alert에서 실제 알림 대상을 정의하는 구성은?", ["Action Group", "Availability Set", "Storage tier", "Subnet mask"], "Action Group", "Alert rule은 조건, action group은 알림/조치 대상을 정의합니다.", source_id="azure-monitor-overview"),
        LabQuiz("azure-q21", "azure-backup-policy", "azure", "multiple_choice", "백업 빈도와 보존 기간을 정의하는 것은?", ["Backup Policy", "NSG Rule", "VNet Peering", "Access Tier"], "Backup Policy", "Backup Policy는 백업 일정과 retention을 정의합니다.", source_id="azure-recovery-services-vault"),
        LabQuiz("azure-q22", "azure-key-vault", "azure", "multiple_choice", "비밀값과 인증서를 안전하게 저장하는 Azure 서비스는?", ["Key Vault", "Load Balancer", "VMSS", "Activity Log"], "Key Vault", "Key Vault는 secret/key/certificate 관리를 위한 서비스입니다.", source_id="manual-az104-basic"),
        LabQuiz("azure-q23", "azure-bastion", "azure", "multiple_choice", "공인 IP 없이 VM에 안전하게 RDP/SSH 접속할 때 적합한 서비스는?", ["Azure Bastion", "Blob lifecycle", "UFW", "Cron"], "Azure Bastion", "Azure Bastion은 VM public IP 없이 포털/브라우저 기반 접속을 제공합니다.", source_id="azure-bastion-overview"),
        LabQuiz("azure-q24", "azure-nat-gateway", "azure", "multiple_choice", "Private subnet의 아웃바운드 인터넷 연결을 고정 공인 IP로 제공하는 서비스는?", ["NAT Gateway", "Private DNS", "Recovery Vault", "Policy Initiative"], "NAT Gateway", "NAT Gateway는 subnet outbound 연결에 적합합니다.", source_id="azure-nat-gateway"),
        LabQuiz("azure-q25", "azure-deployment-slot", "azure", "multiple_choice", "App Service에서 staging 검증 후 production으로 전환하는 기능은?", ["Deployment slot swap", "VNet peering", "SAS rotation", "Fault domain"], "Deployment slot swap", "Deployment Slot은 App Service 배포 안정화에 사용됩니다.", source_id="azure-app-service-overview"),
        LabQuiz("azure-q26", "azure-managed-identity", "azure", "multiple_choice", "코드에 비밀값 없이 Azure 리소스가 Key Vault에 접근하게 하는 방식은?", ["Managed Identity", "Access tier", "Sticky bit", "Archive restore"], "Managed Identity", "Managed Identity는 Azure 리소스에 Entra ID 기반 ID를 부여합니다.", source_id="azure-key-vault-overview"),
        LabQuiz("azure-q27", "azure-template-deployment", "azure", "multiple_choice", "Bicep/ARM 배포에서 resource group/subscription 같은 배포 범위를 뜻하는 개념은?", ["target scope", "health probe", "authorized_keys", "umask"], "target scope", "배포 scope에 따라 사용할 수 있는 함수와 리소스 범위가 달라질 수 있습니다.", source_id="manual-az104-basic"),
    ]
)


PRACTICE_TASKS.extend(
    [
        PracticeTask("linux-lab-14", "linux", "사용자 생성", "`devuser` 사용자를 홈 디렉터리와 함께 생성하세요.", "sudo useradd -m devuser", ["useradd", "-m", "devuser"], "홈 디렉터리 생성 옵션을 함께 써야 합니다.", "`sudo useradd -m devuser`가 대표 명령입니다."),
        PracticeTask("linux-lab-15", "linux", "sudo 그룹 추가", "`devuser`를 sudo 그룹에 추가하세요.", "sudo usermod -aG sudo devuser", ["usermod", "-aG", "sudo", "devuser"], "`-aG`를 함께 써 기존 그룹을 유지하세요.", "`sudo usermod -aG sudo devuser`를 사용합니다."),
        PracticeTask("linux-lab-16", "linux", "그룹 확인", "`devuser`의 UID/GID와 그룹을 확인하세요.", "id devuser", ["id", "devuser"], "`id`는 UID, GID, groups를 함께 보여줍니다.", "`id devuser`를 사용합니다."),
        PracticeTask("linux-lab-17", "linux", "라우팅 확인", "현재 라우팅 테이블을 확인하세요.", "ip route", ["ip", "route"], "외부 통신 장애 때 default route를 확인하세요.", "`ip route`를 사용합니다."),
        PracticeTask("linux-lab-18", "linux", "포트 확인", "현재 listening 포트를 확인하세요.", "ss -tulpen", ["ss", "-"], "listening TCP/UDP 소켓을 확인합니다.", "`ss -tulpen`을 사용할 수 있습니다."),
        PracticeTask("linux-lab-19", "linux", "cron 편집", "현재 사용자의 cron 작업을 편집하세요.", "crontab -e", ["crontab", "-e"], "사용자별 반복 작업은 crontab으로 관리합니다.", "`crontab -e`를 사용합니다."),
        PracticeTask("linux-lab-20", "linux", "디스크 구조 확인", "블록 장치와 파티션 구조를 확인하세요.", "lsblk", ["lsblk"], "디스크/파티션/마운트 구조를 봅니다.", "`lsblk`를 사용합니다."),
        PracticeTask("linux-lab-21", "linux", "swap 확인", "현재 활성화된 swap을 확인하세요.", "swapon --show", ["swapon", "--show"], "swap 사용 여부를 확인합니다.", "`swapon --show`를 사용합니다."),
        PracticeTask("linux-lab-22", "linux", "직전 명령 결과 확인", "직전 명령의 exit code를 확인하세요.", "echo $?", ["echo", "$?"], "`$?`는 직전 명령의 종료 코드입니다.", "`echo $?`를 사용합니다."),
        PracticeTask("linux-lab-23", "linux", "패키지 후보 확인", "`nginx` 패키지 후보 버전을 확인하세요.", "apt-cache policy nginx", ["apt-cache", "policy", "nginx"], "repository 문제를 볼 때 패키지 후보를 확인합니다.", "`apt-cache policy nginx`를 사용합니다."),
        PracticeTask("linux-lab-24", "linux", "SSH 키 생성", "ed25519 방식 SSH 키를 생성하세요.", "ssh-keygen -t ed25519", ["ssh-keygen", "-t", "ed25519"], "키 기반 인증은 공개키/개인키 쌍을 만듭니다.", "`ssh-keygen -t ed25519`를 사용합니다."),
        PracticeTask("linux-lab-25", "linux", "DNS 상태 확인", "현재 DNS resolver 상태를 확인하세요.", "resolvectl status", ["resolvectl", "status"], "DNS 문제는 네트워크 장애와 구분해서 봐야 합니다.", "`resolvectl status`를 사용합니다."),
        PracticeTask("linux-lab-26", "linux", "HTTP 헤더 확인", "example.com의 HTTP 헤더만 확인하세요.", "curl -I https://example.com", ["curl", "-I", "example.com"], "서비스 응답 확인은 curl이 편합니다.", "`curl -I https://example.com`를 사용합니다."),
        PracticeTask("linux-lab-27", "linux", "스토리지 사용량 확인", "`/var/log` 디렉터리 사용량을 요약해서 확인하세요.", "du -sh /var/log", ["du", "-sh", "/var/log"], "디렉터리별 사용량은 du가 적합합니다.", "`du -sh /var/log`를 사용합니다."),
        PracticeTask("linux-lab-28", "linux", "fstab 확인", "자동 마운트 설정 파일을 출력하세요.", "cat /etc/fstab", ["cat", "/etc/fstab"], "부팅 시 마운트 문제는 fstab을 확인합니다.", "`cat /etc/fstab`를 사용합니다."),
        PracticeTask("linux-lab-29", "linux", "환경 변수 PATH 확인", "현재 PATH 환경 변수를 출력하세요.", "echo $PATH", ["echo", "$PATH"], "명령 검색 경로 확인에 필요합니다.", "`echo $PATH`를 사용합니다."),
        PracticeTask("linux-lab-30", "linux", "커널 로그 확인", "커널 로그 마지막 부분을 확인하세요.", "dmesg | tail", ["dmesg", "tail"], "부팅/하드웨어 힌트는 dmesg에서 볼 수 있습니다.", "`dmesg | tail`을 사용합니다."),
    ]
)


def active_tracks() -> list[dict[str, Any]]:
    return [track for track in TRACKS if track["is_active"]]


def normalize_track_id(track_id: str) -> str:
    if track_id == "azure-az104":
        return "azure"
    return track_id or "linux"


def track_by_id(track_id: str) -> dict[str, Any]:
    normalized = normalize_track_id(track_id)
    return next((track for track in TRACKS if track["id"] == normalized), TRACKS[0])


def certifications_for_track(track_id: str) -> list[dict[str, str]]:
    return CERTIFICATIONS.get(normalize_track_id(track_id), [])


def certification_by_id(certification_id: str) -> dict[str, str]:
    for certifications in CERTIFICATIONS.values():
        for certification in certifications:
            if certification["id"] == certification_id:
                return certification
    return {"id": "", "name": "미정", "description": "", "readiness": "unknown", "study_mode": "미정"}


def certification_for_track(track_id: str) -> dict[str, str]:
    certifications = certifications_for_track(track_id)
    return certifications[0] if certifications else {"id": "", "name": "미정", "description": "", "readiness": "unknown", "study_mode": "미정"}


def lessons_for_track(track_id: str) -> list[LessonCard]:
    track_id = normalize_track_id(track_id)
    return [lesson for lesson in LESSONS if lesson.track == track_id and lesson.status == "approved"]


def quizzes_for_track(track_id: str) -> list[LabQuiz]:
    track_id = normalize_track_id(track_id)
    return [quiz for quiz in QUIZZES if quiz.track == track_id and quiz.status == "approved"]


def roadmap_for_track(track_id: str) -> list[RoadmapStep]:
    return ROADMAPS.get(normalize_track_id(track_id), [])


def evaluate_lab_quiz(quiz: LabQuiz, answer: str) -> bool:
    normalized_answer = _normalize(answer)
    expected = _normalize(quiz.answer)
    if quiz.question_type == "command":
        return all(part in normalized_answer for part in expected.split())
    return normalized_answer == expected


def evaluate_lab_quiz_detail(quiz: LabQuiz, answer: str) -> tuple[bool, list[tuple[str, bool]]]:
    """(전체_정답, [(토큰, 일치여부), ...]) — command 타입만 토큰 분해, 나머지는 단일 항목."""
    normalized_answer = _normalize(answer)
    expected = _normalize(quiz.answer)
    if quiz.question_type == "command":
        tokens = expected.split()
        results = [(tok, tok in normalized_answer) for tok in tokens]
        return all(ok for _, ok in results), results
    matched = normalized_answer == expected
    return matched, [(quiz.answer, matched)]


def evaluate_practice(task: PracticeTask, command: str) -> bool:
    normalized = _normalize(command)
    return all(_normalize(condition) in normalized for condition in task.grading_conditions)


def evaluate_practice_detail(task: PracticeTask, command: str) -> tuple[bool, list[tuple[str, bool]]]:
    """(전체_정답, [(조건문자열, 충족여부), ...])."""
    normalized = _normalize(command)
    results = [(_normalize(c), _normalize(c) in normalized) for c in task.grading_conditions]
    return all(ok for _, ok in results), results


def track_progress(track_id: str, completed_lessons: set[str], completed_quizzes: set[str], completed_practices: set[str]) -> dict[str, int]:
    lessons = lessons_for_track(track_id)
    quizzes = quizzes_for_track(track_id)
    practices = [task for task in PRACTICE_TASKS if task.track == track_id and task.status == "approved"]
    total = len(lessons) + len(quizzes) + len(practices)
    completed = (
        len({lesson.id for lesson in lessons} & completed_lessons)
        + len({quiz.id for quiz in quizzes} & completed_quizzes)
        + len({task.id for task in practices} & completed_practices)
    )
    return {"completed": completed, "total": total, "percent": int((completed / total) * 100) if total else 0}


def _normalize(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


# ── JSON content files (cert_study_app/content/{track}/*.json) ───────────────

def _lessons_from_content(track_id: str) -> list[LessonCard]:
    try:
        from cert_study_app.content.loader import load_lesson_dicts
        return [
            LessonCard(
                d["id"], track_id,
                d.get("certification", ""),
                d["title"], d["summary"],
                d.get("example", ""), d.get("common_mistake", ""),
                d.get("keywords", []), d.get("source_id", "manual"),
                details=tuple(d.get("details", [])),
                level=d.get("level", "입문"),
                related_practices=tuple(d.get("related_practices", [])),
            )
            for d in load_lesson_dicts(track_id)
        ]
    except Exception:
        return []


def _quizzes_from_content(track_id: str) -> list[LabQuiz]:
    try:
        from cert_study_app.content.loader import load_quiz_dicts
        return [
            LabQuiz(
                d["id"], d.get("lesson_id", ""), track_id,
                d.get("question_type", "multiple_choice"),
                d["question"], d.get("options", []),
                d["answer"], d.get("explanation", ""),
                difficulty=d.get("difficulty", "easy"),
                source_id=d.get("source_id", "manual"),
            )
            for d in load_quiz_dicts(track_id)
        ]
    except Exception:
        return []


def _practices_from_content(track_id: str) -> list[PracticeTask]:
    try:
        from cert_study_app.content.loader import load_practice_dicts
        return [
            PracticeTask(
                d["id"], track_id, d["title"],
                d["task_description"], d["expected_command"],
                d.get("grading_conditions", []),
                d.get("hint", ""), d.get("explanation", ""),
                difficulty=d.get("difficulty", "easy"),
                takeaway=d.get("takeaway", ""),
            )
            for d in load_practice_dicts(track_id)
        ]
    except Exception:
        return []


for _tid in ("linux", "azure", "tool_docs"):
    LESSONS.extend(_lessons_from_content(_tid))
    QUIZZES.extend(_quizzes_from_content(_tid))
    PRACTICE_TASKS.extend(_practices_from_content(_tid))
