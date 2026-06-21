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
    "azure": {
        "id": "az-104",
        "name": "AZ-104",
        "description": "Microsoft Azure Administrator",
    },
    "linux": {
        "id": "lfcs",
        "name": "LFCS",
        "description": "Linux Foundation Certified Systems Administrator",
    },
    "tool_docs": {
        "id": "tool-docs",
        "name": "Docs Study",
        "description": "공식 문서 기반 도구 학습",
    },
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


LESSONS = [
    LessonCard(
        "linux-pwd",
        "linux",
        "LFCS / 리눅스마스터",
        "pwd 명령어",
        "현재 작업 중인 디렉터리의 절대 경로를 출력합니다.",
        "pwd",
        "상대경로와 절대경로를 헷갈리지 않아야 합니다.",
        ["pwd", "working directory", "absolute path"],
        "manual-linux-basic",
        details=(
            "`pwd`는 지금 명령어가 실행되는 기준 위치를 확인하는 명령어입니다.",
            "파일 생성, 이동, 삭제 명령은 현재 위치를 기준으로 동작하는 경우가 많아서 먼저 위치를 확인하는 습관이 중요합니다.",
            "시험에서는 `cd`로 이동한 뒤 `pwd` 결과가 어디인지 묻거나, 상대경로 명령이 어느 위치에 적용되는지 묻는 식으로 자주 연결됩니다.",
        ),
    ),
    LessonCard(
        "linux-ls",
        "linux",
        "LFCS / 리눅스마스터",
        "ls 명령어",
        "현재 디렉터리의 파일과 하위 디렉터리 목록을 보여줍니다.",
        "ls -al",
        "`-a`는 숨김 파일, `-l`은 자세한 정보를 의미합니다.",
        ["ls", "-a", "-l", "hidden files"],
        "manual-linux-basic",
        details=(
            "`ls`는 현재 위치에 무엇이 있는지 확인하는 가장 기본적인 탐색 명령어입니다.",
            "`ls -l`은 권한, 소유자, 크기, 수정 시간을 함께 보여주므로 권한 문제를 볼 때 특히 자주 씁니다.",
            "`ls -a`는 `.`으로 시작하는 숨김 파일까지 보여주며, 설정 파일이나 쉘 환경 파일을 찾을 때 필요합니다.",
        ),
    ),
    LessonCard(
        "linux-cd",
        "linux",
        "LFCS / 리눅스마스터",
        "cd 명령어",
        "작업 디렉터리를 다른 위치로 이동합니다.",
        "cd /var/log",
        "`cd ..`와 `cd /`의 이동 위치를 구분해야 합니다.",
        ["cd", "relative path", "absolute path"],
        "manual-linux-basic",
        details=(
            "`cd`는 작업 기준 위치를 바꾸는 명령어라서 이후 명령의 대상 경로에 직접 영향을 줍니다.",
            "`cd ..`는 부모 디렉터리로 한 단계 올라가고, `cd /`는 파일시스템 최상위 디렉터리로 이동합니다.",
            "`cd ~`는 현재 사용자의 홈 디렉터리로 이동하므로 사용자별 경로를 다룰 때 자주 등장합니다.",
        ),
    ),
    LessonCard(
        "linux-mkdir",
        "linux",
        "LFCS / 리눅스마스터",
        "mkdir 명령어",
        "새 디렉터리를 생성합니다.",
        "mkdir practice",
        "중첩 디렉터리는 `mkdir -p parent/child`가 필요할 수 있습니다.",
        ["mkdir", "directory", "-p"],
        "manual-linux-basic",
        details=(
            "`mkdir`는 새 디렉터리를 만들 때 사용합니다.",
            "이미 없는 부모 디렉터리까지 한 번에 만들려면 `-p` 옵션을 사용합니다.",
            "실습형 문제에서는 지정된 위치에 디렉터리를 만들고 권한이나 파일을 이어서 설정하는 흐름으로 자주 나옵니다.",
        ),
    ),
    LessonCard(
        "linux-touch",
        "linux",
        "LFCS / 리눅스마스터",
        "touch 명령어",
        "빈 파일을 만들거나 파일의 수정 시간을 갱신합니다.",
        "touch hello.txt",
        "이미 있는 파일에 쓰면 내용은 지우지 않고 timestamp만 갱신합니다.",
        ["touch", "file", "timestamp"],
        "manual-linux-basic",
        details=(
            "`touch`는 빈 파일을 빠르게 만들거나 파일의 수정 시간을 갱신할 때 사용합니다.",
            "파일이 없으면 새로 만들고, 파일이 이미 있으면 내용을 바꾸지 않은 채 시간 정보만 바뀝니다.",
            "시험에서는 파일 생성 후 `ls -l`로 존재 여부나 timestamp를 확인하는 흐름으로 이어질 수 있습니다.",
        ),
    ),
    LessonCard(
        "linux-cat",
        "linux",
        "LFCS / 리눅스마스터",
        "cat 명령어",
        "파일 내용을 표준 출력으로 보여줍니다.",
        "cat hello.txt",
        "큰 파일은 `less`, `head`, `tail`이 더 적합할 수 있습니다.",
        ["cat", "stdout", "text"],
        "manual-linux-basic",
        details=(
            "`cat`은 파일 내용을 터미널에 바로 출력합니다.",
            "작은 설정 파일이나 짧은 텍스트 확인에는 빠르지만, 큰 로그 파일에는 화면이 밀려 불편할 수 있습니다.",
            "긴 파일은 `less`, 처음 일부는 `head`, 마지막 일부는 `tail`을 쓰는 판단이 중요합니다.",
        ),
    ),
    LessonCard(
        "linux-grep",
        "linux",
        "LFCS / 리눅스마스터",
        "grep 명령어",
        "파일이나 출력 결과에서 특정 문자열 또는 패턴을 검색합니다.",
        "grep error app.log",
        "대소문자 구분이 기본이며, 필요하면 `-i` 옵션을 씁니다.",
        ["grep", "pattern", "search"],
        "manual-linux-basic",
        details=(
            "`grep`은 텍스트 안에서 원하는 문자열이나 패턴이 들어간 줄을 찾아냅니다.",
            "로그 분석, 설정 파일 점검, 명령 출력 필터링에서 매우 자주 쓰입니다.",
            "`ps aux | grep nginx`처럼 파이프와 함께 쓰면 긴 출력 중 필요한 줄만 빠르게 볼 수 있습니다.",
        ),
    ),
    LessonCard(
        "linux-chmod",
        "linux",
        "LFCS / 리눅스마스터",
        "chmod 명령어",
        "파일이나 디렉터리의 권한을 변경합니다.",
        "chmod 755 script.sh",
        "소유자/그룹/기타 사용자의 권한 위치를 구분해야 합니다.",
        ["chmod", "permission", "rwx"],
        "manual-linux-basic",
        details=(
            "`chmod`는 파일이나 디렉터리에 대해 읽기, 쓰기, 실행 권한을 조정합니다.",
            "`755`는 소유자에게 `rwx`, 그룹과 기타 사용자에게 `r-x`를 주는 대표적인 실행 파일 권한입니다.",
            "권한 문제는 명령어를 맞히는 것보다 숫자 권한과 `rwx` 의미를 연결해서 이해하는 것이 중요합니다.",
        ),
    ),
    LessonCard(
        "azure-rg",
        "azure",
        "AZ-104",
        "Resource Group",
        "Azure 리소스를 논리적으로 묶어 관리하는 단위입니다.",
        "VM, Storage Account, VNet을 같은 Resource Group에 배치",
        "Resource Group을 삭제하면 포함된 리소스도 함께 삭제될 수 있습니다.",
        ["resource group", "lifecycle", "management"],
        "manual-az104-basic",
        details=(
            "Resource Group은 Azure 리소스를 배포, 권한, 비용, 수명주기 관점에서 묶는 논리 단위입니다.",
            "같은 애플리케이션이나 같은 수명주기를 가진 리소스를 함께 두면 관리와 삭제가 쉬워집니다.",
            "AZ-104에서는 리소스 이동, 잠금, RBAC 적용 범위, 삭제 영향 범위를 묻는 문제와 자주 연결됩니다.",
        ),
    ),
    LessonCard(
        "azure-storage",
        "azure",
        "AZ-104",
        "Storage Account",
        "Blob, File, Queue, Table 같은 저장 서비스를 담는 Azure 리소스입니다.",
        "Blob Storage에 로그 또는 정적 파일 저장",
        "복제 옵션과 access tier는 비용과 복구 요구사항에 영향을 줍니다.",
        ["storage account", "blob", "redundancy"],
        "manual-az104-basic",
        details=(
            "Storage Account는 Azure Storage 서비스를 사용하는 상위 컨테이너입니다.",
            "Blob은 객체 저장, Files는 SMB 파일 공유, Queue는 메시지, Table은 NoSQL 형태의 간단한 구조화 데이터에 사용됩니다.",
            "시험에서는 LRS/ZRS/GRS 같은 복제 옵션, Hot/Cool/Archive tier, 접근 제어 방식을 구분하는 문제가 자주 나옵니다.",
        ),
    ),
    LessonCard(
        "azure-vnet",
        "azure",
        "AZ-104",
        "Virtual Network",
        "Azure 리소스 간 사설 네트워크 통신을 제공하는 네트워크 경계입니다.",
        "VM을 VNet의 Subnet에 연결",
        "주소 공간이 겹치면 피어링이나 연결 설계에 문제가 생길 수 있습니다.",
        ["vnet", "subnet", "peering"],
        "manual-az104-basic",
        details=(
            "Virtual Network는 Azure 안에서 사설 IP 기반 네트워크 경계를 만드는 핵심 리소스입니다.",
            "VM, Private Endpoint, Application Gateway 같은 리소스는 보통 Subnet 안에 배치됩니다.",
            "주소 공간, Subnet 분리, NSG, Peering을 함께 이해해야 네트워크 문제를 안정적으로 풀 수 있습니다.",
        ),
    ),
    LessonCard(
        "docs-ollama-models",
        "tool_docs",
        "Docs Study",
        "Ollama 모델 실행 흐름",
        "Ollama는 로컬에서 모델을 내려받고 실행해 API 또는 CLI로 사용할 수 있게 해줍니다.",
        "ollama run qwen2.5:14b",
        "모델 이름, 태그, 실행 중인 서버 주소를 혼동하지 않아야 합니다.",
        ["ollama", "local model", "model tag"],
        "official-docs-ollama",
    ),
    LessonCard(
        "docs-streamlit-state",
        "tool_docs",
        "Docs Study",
        "Streamlit session_state",
        "Streamlit은 rerun 기반이라 화면 상태는 session_state에 저장해 유지합니다.",
        "st.session_state.setdefault('page', '홈')",
        "일반 변수만 쓰면 버튼 클릭 후 rerun에서 값이 사라질 수 있습니다.",
        ["streamlit", "session_state", "rerun"],
        "official-docs-streamlit",
    ),
    LessonCard(
        "docs-hf-spaces",
        "tool_docs",
        "Docs Study",
        "Hugging Face Spaces",
        "Spaces는 Streamlit, Gradio, Docker 앱을 배포할 수 있는 호스팅 환경입니다.",
        "README metadata에 sdk와 app_file을 설정",
        "비밀값은 코드가 아니라 Space Secrets에 넣어야 합니다.",
        ["huggingface", "spaces", "secrets"],
        "official-docs-huggingface",
    ),
]


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
        source_id="manual-az104-basic",
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
        source_id="manual-az104-basic",
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


def active_tracks() -> list[dict[str, Any]]:
    return [track for track in TRACKS if track["is_active"]]


def normalize_track_id(track_id: str) -> str:
    if track_id == "azure-az104":
        return "azure"
    return track_id or "linux"


def track_by_id(track_id: str) -> dict[str, Any]:
    normalized = normalize_track_id(track_id)
    return next((track for track in TRACKS if track["id"] == normalized), TRACKS[0])


def certification_for_track(track_id: str) -> dict[str, str]:
    return CERTIFICATIONS.get(normalize_track_id(track_id), {"id": "", "name": "미정", "description": ""})


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


def evaluate_practice(task: PracticeTask, command: str) -> bool:
    normalized = _normalize(command)
    return all(_normalize(condition) in normalized for condition in task.grading_conditions)


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
