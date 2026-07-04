from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class DocsSource:
    id: str
    track: str
    provider: str
    title: str
    url: str
    category: str
    tags: tuple[str, ...] = ()
    role: str = "reference"
    enabled: bool = True


DOCS_SOURCES: tuple[DocsSource, ...] = (
    DocsSource(
        "manual-az104-basic",
        "azure",
        "Microsoft Learn",
        "AZ-104 study guide",
        "https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/az-104",
        "exam-guide",
        ("az-104", "study-guide"),
    ),
    DocsSource(
        "azure-vnet-overview",
        "azure",
        "Microsoft Learn",
        "Azure Virtual Network overview",
        "https://learn.microsoft.com/en-us/azure/virtual-network/virtual-networks-overview",
        "network",
        ("vnet", "subnet", "networking"),
    ),
    DocsSource(
        "azure-nsg-overview",
        "azure",
        "Microsoft Learn",
        "Network security groups",
        "https://learn.microsoft.com/en-us/azure/virtual-network/network-security-groups-overview",
        "network",
        ("nsg", "security"),
    ),
    DocsSource(
        "azure-private-endpoint",
        "azure",
        "Microsoft Learn",
        "Private Endpoint overview",
        "https://learn.microsoft.com/en-us/azure/private-link/private-endpoint-overview",
        "network",
        ("private-link", "private-endpoint"),
    ),
    DocsSource(
        "azure-load-balancer",
        "azure",
        "Microsoft Learn",
        "Azure Load Balancer overview",
        "https://learn.microsoft.com/en-us/azure/load-balancer/load-balancer-overview",
        "network",
        ("load-balancer",),
    ),
    DocsSource(
        "azure-vm-overview",
        "azure",
        "Microsoft Learn",
        "Azure Virtual Machines overview",
        "https://learn.microsoft.com/en-us/azure/virtual-machines/overview",
        "compute",
        ("vm", "compute"),
    ),
    DocsSource(
        "azure-storage-account",
        "azure",
        "Microsoft Learn",
        "Storage account overview",
        "https://learn.microsoft.com/en-us/azure/storage/common/storage-account-overview",
        "storage",
        ("storage-account", "blob"),
    ),
    DocsSource(
        "azure-rbac-overview",
        "azure",
        "Microsoft Learn",
        "Azure RBAC overview",
        "https://learn.microsoft.com/en-us/azure/role-based-access-control/overview",
        "identity",
        ("rbac", "role"),
    ),
    DocsSource(
        "azure-monitor-overview",
        "azure",
        "Microsoft Learn",
        "Azure Monitor overview",
        "https://learn.microsoft.com/en-us/azure/azure-monitor/overview",
        "monitor",
        ("monitor", "log-analytics"),
    ),
    DocsSource(
        "azure-backup-overview",
        "azure",
        "Microsoft Learn",
        "Azure Backup overview",
        "https://learn.microsoft.com/en-us/azure/backup/backup-overview",
        "backup",
        ("backup", "recovery"),
    ),
    DocsSource(
        "azure-policy-overview",
        "azure",
        "Microsoft Learn",
        "Azure Policy overview",
        "https://learn.microsoft.com/en-us/azure/governance/policy/overview",
        "governance",
        ("policy", "initiative", "compliance"),
    ),
    DocsSource(
        "azure-app-gateway-overview",
        "azure",
        "Microsoft Learn",
        "Application Gateway overview",
        "https://learn.microsoft.com/en-us/azure/application-gateway/overview",
        "network",
        ("application-gateway", "waf", "layer-7"),
    ),
    DocsSource(
        "azure-dns-overview",
        "azure",
        "Microsoft Learn",
        "Azure DNS overview",
        "https://learn.microsoft.com/en-us/azure/dns/dns-overview",
        "network",
        ("dns", "private-dns", "resolver"),
    ),
    DocsSource(
        "azure-blob-access-tiers",
        "azure",
        "Microsoft Learn",
        "Blob access tiers",
        "https://learn.microsoft.com/en-us/azure/storage/blobs/access-tiers-overview",
        "storage",
        ("blob", "hot", "cool", "archive"),
    ),
    DocsSource(
        "azure-vmss-overview",
        "azure",
        "Microsoft Learn",
        "Virtual Machine Scale Sets overview",
        "https://learn.microsoft.com/en-us/azure/virtual-machine-scale-sets/overview",
        "compute",
        ("vmss", "autoscale", "availability"),
    ),
    DocsSource(
        "azure-log-analytics-overview",
        "azure",
        "Microsoft Learn",
        "Log Analytics overview",
        "https://learn.microsoft.com/en-us/azure/azure-monitor/logs/log-analytics-overview",
        "monitor",
        ("log-analytics", "kql", "monitor"),
    ),
    DocsSource(
        "azure-recovery-services-vault",
        "azure",
        "Microsoft Learn",
        "Recovery Services vault overview",
        "https://learn.microsoft.com/en-us/azure/backup/backup-azure-recovery-services-vault-overview",
        "backup",
        ("recovery-services-vault", "backup-policy"),
    ),
    DocsSource(
        "azure-bastion-overview",
        "azure",
        "Microsoft Learn",
        "Azure Bastion overview",
        "https://learn.microsoft.com/en-us/azure/bastion/bastion-overview",
        "network",
        ("bastion", "ssh", "rdp"),
    ),
    DocsSource(
        "azure-nat-gateway",
        "azure",
        "Microsoft Learn",
        "Azure NAT Gateway overview",
        "https://learn.microsoft.com/en-us/azure/nat-gateway/nat-overview",
        "network",
        ("nat-gateway", "outbound"),
    ),
    DocsSource(
        "azure-app-service-overview",
        "azure",
        "Microsoft Learn",
        "App Service overview",
        "https://learn.microsoft.com/en-us/azure/app-service/overview",
        "compute",
        ("app-service", "web-app"),
    ),
    DocsSource(
        "azure-container-instances",
        "azure",
        "Microsoft Learn",
        "Azure Container Instances overview",
        "https://learn.microsoft.com/en-us/azure/container-instances/container-instances-overview",
        "compute",
        ("aci", "container"),
    ),
    DocsSource(
        "azure-key-vault-overview",
        "azure",
        "Microsoft Learn",
        "Azure Key Vault overview",
        "https://learn.microsoft.com/en-us/azure/key-vault/general/overview",
        "security",
        ("key-vault", "secret", "key"),
    ),
    DocsSource(
        "manual-linux-basic",
        "linux",
        "GNU Coreutils Manual",
        "GNU Coreutils basic operations",
        "https://www.gnu.org/software/coreutils/manual/coreutils.html",
        "essential-commands",
        ("pwd", "ls", "mkdir", "touch", "chmod"),
        "command-reference",
    ),
    DocsSource(
        "linux-bash-cd",
        "linux",
        "GNU Bash Manual",
        "Bash builtins",
        "https://www.gnu.org/software/bash/manual/html_node/Bourne-Shell-Builtins.html",
        "shell",
        ("cd", "shell-builtin"),
        "command-reference",
    ),
    DocsSource(
        "linux-grep-manual",
        "linux",
        "GNU Grep Manual",
        "GNU Grep manual",
        "https://www.gnu.org/software/grep/manual/grep.html",
        "text-processing",
        ("grep", "search"),
        "command-reference",
    ),
    DocsSource(
        "linux-systemd-systemctl",
        "linux",
        "freedesktop.org",
        "systemctl manual",
        "https://www.freedesktop.org/software/systemd/man/latest/systemctl.html",
        "services",
        ("systemctl", "service"),
        "command-reference",
    ),
    DocsSource(
        "linux-man7-ip",
        "linux",
        "man7.org",
        "ip command manual",
        "https://man7.org/linux/man-pages/man8/ip.8.html",
        "networking",
        ("ip", "networking"),
        "command-reference",
    ),
    DocsSource(
        "ubuntu-server-docs",
        "linux",
        "Ubuntu Server Docs",
        "Ubuntu Server documentation",
        "https://ubuntu.com/server/docs/",
        "server-operations",
        ("ubuntu", "server", "operations"),
        "practice-guide",
    ),
    DocsSource(
        "ubuntu-package-management",
        "linux",
        "Ubuntu Server Docs",
        "Install and manage packages",
        "https://ubuntu.com/server/docs/how-to/software/package-management/",
        "package-management",
        ("apt", "package", "software"),
        "practice-guide",
    ),
    DocsSource(
        "ubuntu-user-management",
        "linux",
        "Ubuntu Server Docs",
        "User management",
        "https://ubuntu.com/server/docs/how-to/security/user-management/",
        "users-groups",
        ("user", "group", "sudo"),
        "practice-guide",
    ),
    DocsSource(
        "ubuntu-networking",
        "linux",
        "Ubuntu Server Docs",
        "Networking",
        "https://ubuntu.com/server/docs/how-to/networking/",
        "networking",
        ("netplan", "dns", "network-tools"),
        "practice-guide",
    ),
    DocsSource(
        "ubuntu-firewall",
        "linux",
        "Ubuntu Server Docs",
        "Firewall",
        "https://ubuntu.com/server/docs/how-to/security/firewalls/",
        "security",
        ("ufw", "firewall", "port"),
        "practice-guide",
    ),
    DocsSource(
        "ubuntu-storage",
        "linux",
        "Ubuntu Server Docs",
        "Storage",
        "https://ubuntu.com/server/docs/how-to/storage/",
        "storage",
        ("lvm", "storage", "iscsi"),
        "practice-guide",
    ),
    DocsSource(
        "official-docs-ollama",
        "tool_docs",
        "Ollama Docs",
        "Ollama documentation",
        "https://docs.ollama.com/",
        "ollama",
        ("ollama", "local-model"),
    ),
    DocsSource(
        "official-docs-langchain",
        "tool_docs",
        "LangChain Docs",
        "LangChain documentation",
        "https://python.langchain.com/docs/",
        "langchain",
        ("langchain", "rag"),
    ),
    DocsSource(
        "official-docs-streamlit",
        "tool_docs",
        "Streamlit Docs",
        "Streamlit documentation",
        "https://docs.streamlit.io/",
        "streamlit",
        ("streamlit", "session-state"),
    ),
    DocsSource(
        "official-docs-huggingface",
        "tool_docs",
        "Hugging Face Docs",
        "Hugging Face documentation",
        "https://huggingface.co/docs",
        "huggingface",
        ("huggingface", "spaces"),
    ),
)


def active_docs_sources(track_id: str | None = None) -> list[DocsSource]:
    sources = [source for source in DOCS_SOURCES if source.enabled]
    if track_id and track_id != "all":
        sources = [source for source in sources if source.track == track_id]
    return sources


def doc_source_by_id(source_id: str | None) -> DocsSource | None:
    if not source_id:
        return None
    return next((source for source in DOCS_SOURCES if source.id == source_id), None)


def doc_source_urls(track_id: str | None = None) -> list[str]:
    return [source.url for source in active_docs_sources(track_id)]


def docs_source_options() -> list[tuple[str, str]]:
    return [
        ("all", "전체 Docs"),
        ("azure", "Azure Docs"),
        ("linux", "Linux Docs"),
        ("tool_docs", "Tool Docs"),
    ]


def urls_from_sources(sources: Iterable[DocsSource]) -> list[str]:
    return [source.url for source in sources]
