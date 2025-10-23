# classify.py
import re
from typing import Tuple

# 대분류 상수
ID_GOV = "Identities & Governance"
STORAGE = "Storage"
COMPUTE = "Compute"
NETWORK = "Networking"
MONITOR = "Monitoring & Maintenance"

def _contains(text: str, *words) -> bool:
    t = text.lower()
    return any(w.lower() in t for w in words)

def classify_category_subcategory(stem: str) -> Tuple[str, str]:
    """문항 본문 텍스트(stem)로 대/소분류를 추정"""
    s = stem or ""

    # --- Networking ---
    if _contains(s, "vnet", "subnet", "cidr", "peering", "nsg", "application security group",
                    "bastion", "azure firewall", "udr", "route table", "vpn", "expressroute"):
        if _contains(s, "peering"):
            return NETWORK, "VNet Peering"
        if _contains(s, "nsg", "application security group"):
            return NETWORK, "NSG/ASG"
        if _contains(s, "vpn", "expressroute"):
            return NETWORK, "Hybrid Connectivity"
        if _contains(s, "bastion"):
            return NETWORK, "Bastion"
        if _contains(s, "route", "udr"):
            return NETWORK, "Routing/UDR"
        return NETWORK, "VNet/Subnet"

    # --- Compute ---
    if _contains(s, "virtual machine", "vm", "scale set", "availability set", "image", "managed disk"):
        if _contains(s, "scale set", "vmss"):
            return COMPUTE, "VM Scale Set"
        if _contains(s, "availability set", "availability zone"):
            return COMPUTE, "Availability/Resiliency"
        if _contains(s, "image"):
            return COMPUTE, "Image/Template"
        if _contains(s, "disk"):
            return COMPUTE, "Disks/Snapshots"
        return COMPUTE, "VM Deployment/Config"

    # --- Storage ---
    if _contains(s, "storage account", "blob", "file share", "azure files", "sas", "lrs", "grs", "access tier"):
        if _contains(s, "blob"):
            return STORAGE, "Blob"
        if _contains(s, "file share", "azure files", "files sync"):
            return STORAGE, "Azure Files/SMB"
        if _contains(s, "sas", "firewall", "private endpoint"):
            return STORAGE, "Security/Access"
        if _contains(s, "lrs", "grs", "gzs", "zrs"):
            return STORAGE, "Redundancy"
        if _contains(s, "access tier", "hot", "cool", "archive"):
            return STORAGE, "Tiering"
        return STORAGE, "General"

    # --- Identities & Governance ---
    if _contains(s, "azure ad", "entra id", "rbac", "role assignment", "subscription", "policy", "blueprint"):
        if _contains(s, "rbac", "role"):
            return ID_GOV, "RBAC"
        if _contains(s, "policy", "blueprint", "initiative", "assignment"):
            return ID_GOV, "Policy/Blueprint"
        if _contains(s, "subscription", "management group"):
            return ID_GOV, "Subscription/MG"
        if _contains(s, "user", "group", "entra"):
            return ID_GOV, "Users/Groups"
        return ID_GOV, "General"

    # --- Monitoring & Maintenance ---
    if _contains(s, "azure monitor", "metrics", "log analytics", "kusto", "alert", "action group",
                 "backup", "site recovery", "update management"):
        if _contains(s, "log analytics", "kusto", "workspace"):
            return MONITOR, "LA/Logs"
        if _contains(s, "alert", "action group"):
            return MONITOR, "Alerts"
        if _contains(s, "backup", "site recovery"):
            return MONITOR, "Backup/ASR"
        if _contains(s, "update management", "patch"):
            return MONITOR, "Updates"
        return MONITOR, "General"

    # 기타
    return "Unknown", "Unknown"

## 규칙 기반 키워드 매칭. ( 향후 LLM 분류 가능 )