import json
import re
from dataclasses import dataclass
from typing import Optional

from cert_study_app.models import Question


@dataclass(frozen=True)
class ConceptRule:
    category: str
    subcategory: str
    tags: tuple[str, ...]
    keywords: tuple[str, ...]


AZ104_CONCEPT_RULES: tuple[ConceptRule, ...] = (
    ConceptRule("identity", "entra_id", ("Microsoft Entra ID", "tenant", "user", "group"), ("entra", "azure ad", "tenant", "user account", "group", "사용자", "그룹", "테넌트")),
    ConceptRule("identity", "rbac", ("RBAC", "role assignment", "custom role"), ("rbac", "role assignment", "custom role", "role definition", "assignablescopes", "role1", "역할", "권한")),
    ConceptRule("governance", "policy", ("Azure Policy", "initiative", "compliance"), ("policy", "initiative", "compliance", "deny", "audit", "정책", "규정")),
    ConceptRule("governance", "resource_group", ("resource group", "subscription", "management group"), ("resource group", "subscription", "management group", "tag", "lock", "리소스 그룹", "구독", "태그", "잠금")),
    ConceptRule("storage", "blob", ("Blob Storage", "container", "access tier"), ("blob", "container", "access tier", "hot tier", "cool tier", "archive", "컨테이너")),
    ConceptRule("storage", "files", ("Azure Files", "file share", "sync"), ("azure files", "file share", "file sync", "파일 공유")),
    ConceptRule("storage", "storage_account", ("storage account", "replication", "SAS"), ("storage account", "sas", "shared access signature", "replication", "grs", "lrs", "zrs", "스토리지")),
    ConceptRule("compute_vm", "vm", ("virtual machine", "availability set", "disk"), ("virtual machine", "vm", "availability set", "disk", "managed disk", "가상 머신", "디스크")),
    ConceptRule("compute_vm", "vmss", ("VM scale set", "autoscale"), ("scale set", "vmss", "autoscale", "확장 집합", "자동 크기 조정")),
    ConceptRule("compute_vm", "app_service", ("App Service", "web app", "deployment slot"), ("app service", "web app", "deployment slot", "app plan", "웹앱")),
    ConceptRule("network", "vnet_subnet", ("VNet", "subnet", "peering"), ("vnet", "virtual network", "subnet", "peering", "address space", "가상 네트워크", "서브넷")),
    ConceptRule("network", "nsg", ("NSG", "security rule", "RDP", "SSH"), ("nsg", "network security group", "security rule", "inbound", "outbound", "rdp", "ssh", "네트워크 보안 그룹")),
    ConceptRule("network", "load_balancer", ("Load Balancer", "backend pool", "health probe"), ("load balancer", "backend pool", "health probe", "frontend ip", "부하 분산")),
    ConceptRule("network", "app_gateway", ("Application Gateway", "WAF", "listener"), ("application gateway", "waf", "listener", "routing rule", "애플리케이션 게이트웨이")),
    ConceptRule("network", "dns", ("DNS", "private DNS", "zone"), ("dns", "private dns", "zone", "record set", "name resolution", "이름 확인")),
    ConceptRule("network", "vpn_expressroute", ("VPN Gateway", "ExpressRoute", "connection"), ("vpn gateway", "expressroute", "local network gateway", "connection", "gateway subnet")),
    ConceptRule("monitoring", "monitor", ("Azure Monitor", "Log Analytics", "alert"), ("azure monitor", "log analytics", "alert", "metric", "activity log", "모니터", "경고")),
    ConceptRule("backup_recovery", "backup", ("Azure Backup", "recovery vault", "restore"), ("backup", "recovery services vault", "restore", "snapshot", "백업", "복원")),
    ConceptRule("containers", "aks_acr", ("AKS", "ACR", "container"), ("aks", "kubernetes", "acr", "container registry", "container instance", "컨테이너")),
    ConceptRule("migration", "migration", ("Azure Migrate", "replication", "assessment"), ("azure migrate", "migration", "replication appliance", "assessment", "마이그레이션")),
)


CATEGORY_LABELS = {
    "identity": "ID 및 액세스",
    "governance": "거버넌스",
    "storage": "스토리지",
    "compute_vm": "VM/컴퓨팅",
    "network": "네트워크",
    "monitoring": "모니터링",
    "backup_recovery": "백업/복구",
    "containers": "컨테이너",
    "migration": "마이그레이션",
    "uncategorized": "미분류",
}


SUBCATEGORY_LABELS = {
    "entra_id": "Entra ID",
    "rbac": "RBAC/역할",
    "policy": "Policy",
    "resource_group": "구독/리소스 그룹",
    "blob": "Blob",
    "files": "Azure Files",
    "storage_account": "Storage Account",
    "vm": "VM",
    "vmss": "VM Scale Set",
    "app_service": "App Service",
    "vnet_subnet": "VNet/Subnet",
    "nsg": "NSG",
    "load_balancer": "Load Balancer",
    "app_gateway": "Application Gateway",
    "dns": "DNS",
    "vpn_expressroute": "VPN/ExpressRoute",
    "monitor": "Azure Monitor",
    "backup": "Backup",
    "aks_acr": "AKS/ACR",
    "migration": "Migration",
}


def _visual_text(question: Question) -> str:
    try:
        visual = json.loads(question.visual_analysis_json) if question.visual_analysis_json else {}
    except Exception:
        return ""
    if not isinstance(visual, dict):
        return ""
    parts = [
        visual.get("stem"),
        visual.get("source_content"),
        visual.get("notes"),
        json.dumps(visual.get("answer_areas") or [], ensure_ascii=False),
        json.dumps(visual.get("statements") or [], ensure_ascii=False),
    ]
    return "\n".join(str(part) for part in parts if part)


def question_concept_text(question: Question) -> str:
    parts = [
        question.stem,
        question.raw_text,
        question.explanation,
        question.parent_stem,
        " ".join(str(option) for option in question.get_options() or []),
        _visual_text(question),
    ]
    return "\n".join(str(part) for part in parts if part).lower()


def classify_question_concept(question: Question) -> dict:
    text = question_concept_text(question)
    scores: list[tuple[int, ConceptRule]] = []
    for rule in AZ104_CONCEPT_RULES:
        score = 0
        for keyword in rule.keywords:
            pattern = re.escape(keyword.lower())
            matches = len(re.findall(pattern, text))
            score += matches * (3 if " " in keyword else 1)
        if score:
            scores.append((score, rule))

    if not scores:
        return {
            "category": "uncategorized",
            "subcategory": None,
            "concept_tags": [],
            "confidence": 0,
        }

    scores.sort(key=lambda item: item[0], reverse=True)
    top_score, top_rule = scores[0]
    second_score = scores[1][0] if len(scores) > 1 else 0
    confidence = min(95, 45 + top_score * 8 + max(0, top_score - second_score) * 5)
    related_tags = list(top_rule.tags)
    return {
        "category": top_rule.category,
        "subcategory": top_rule.subcategory,
        "concept_tags": related_tags[:8],
        "confidence": confidence,
    }


def apply_question_concept(question: Question, overwrite: bool = False) -> dict:
    result = classify_question_concept(question)
    if overwrite or not question.category:
        question.category = result["category"]
    if overwrite or not question.subcategory:
        question.subcategory = result["subcategory"]
    if overwrite or not question.get_concept_tags():
        question.set_concept_tags(result["concept_tags"])
    return result


def concept_label(category: Optional[str], subcategory: Optional[str] = None) -> str:
    category_label = CATEGORY_LABELS.get(category or "uncategorized", category or "미분류")
    if subcategory:
        return f"{category_label} · {SUBCATEGORY_LABELS.get(subcategory, subcategory)}"
    return category_label


def classify_question_batch(db, source: Optional[str] = None, limit: int = 1000, overwrite: bool = False) -> dict:
    query = db.query(Question)
    if source:
        query = query.filter(Question.source == source)
    if not overwrite:
        query = query.filter(Question.category.is_(None))
    questions = query.order_by(Question.id.asc()).limit(limit).all()
    summary = {"checked": 0, "classified": 0, "uncategorized": 0}
    for question in questions:
        result = apply_question_concept(question, overwrite=overwrite)
        summary["checked"] += 1
        if result["category"] == "uncategorized":
            summary["uncategorized"] += 1
        else:
            summary["classified"] += 1
    db.commit()
    return summary
