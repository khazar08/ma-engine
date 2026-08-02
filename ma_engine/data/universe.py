"""Sector universe definition + loader.

For v1 the sector is enterprise software (clean comps, disclosed segment data).
The starter list holds ticker, CIK, name, a short business description and
segment tags for each name. A curated *seed* fundamentals snapshot lives in
``seed_fundamentals.py`` so the full pipeline runs offline and deterministically;
``ingest_edgar`` can refresh these from live SEC data.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UniverseEntry:
    ticker: str
    cik: str
    name: str
    description: str
    segments: tuple[str, ...]


# Enterprise software universe. Descriptions are concise business summaries used
# for embedding/adjacency; segments are coarse product-category tags.
ENTERPRISE_SOFTWARE: list[UniverseEntry] = [
    UniverseEntry("CRM", "0001108524", "Salesforce, Inc.",
                  "Cloud-based customer relationship management, sales, service, marketing and analytics software delivered as SaaS.",
                  ("crm", "sales", "service", "marketing", "analytics")),
    UniverseEntry("NOW", "0001373715", "ServiceNow, Inc.",
                  "Cloud platform for digital workflows, IT service management, IT operations and enterprise automation.",
                  ("itsm", "workflow", "automation", "platform")),
    UniverseEntry("WDAY", "0001327811", "Workday, Inc.",
                  "Cloud applications for human capital management, financial management and enterprise planning.",
                  ("hcm", "financials", "planning", "analytics")),
    UniverseEntry("ADBE", "0000796343", "Adobe Inc.",
                  "Software for digital media creation, document management and digital experience and marketing.",
                  ("creative", "documents", "marketing", "analytics")),
    UniverseEntry("INTU", "0000896878", "Intuit Inc.",
                  "Financial and accounting software for consumers and small businesses, tax preparation and payroll.",
                  ("accounting", "tax", "payroll", "smb")),
    UniverseEntry("SNOW", "0001640147", "Snowflake Inc.",
                  "Cloud data platform for data warehousing, data lakes, analytics and secure data sharing.",
                  ("data-platform", "analytics", "warehouse")),
    UniverseEntry("DDOG", "0001561550", "Datadog, Inc.",
                  "Observability and security monitoring platform for cloud infrastructure, applications and logs.",
                  ("observability", "monitoring", "security", "platform")),
    UniverseEntry("TEAM", "0001650372", "Atlassian Corporation",
                  "Team collaboration and software development tools including issue tracking and agile planning.",
                  ("collaboration", "devtools", "itsm", "workflow")),
    UniverseEntry("ZS", "0001713683", "Zscaler, Inc.",
                  "Cloud-native zero-trust security platform for secure internet and private application access.",
                  ("security", "network", "zero-trust")),
    UniverseEntry("CRWD", "0001535527", "CrowdStrike Holdings, Inc.",
                  "Cloud-delivered endpoint and cloud workload protection, threat intelligence and security operations.",
                  ("security", "endpoint", "threat-intel")),
    UniverseEntry("PANW", "0001327567", "Palo Alto Networks, Inc.",
                  "Enterprise cybersecurity platform spanning network security, cloud security and security operations.",
                  ("security", "network", "cloud-security", "soc")),
    UniverseEntry("HUBS", "0001404655", "HubSpot, Inc.",
                  "Inbound marketing, sales and customer service software platform for small and mid-market businesses.",
                  ("crm", "marketing", "sales", "service", "smb")),
    UniverseEntry("DOCU", "0001261333", "DocuSign, Inc.",
                  "Electronic signature and agreement cloud for preparing, signing and managing contracts.",
                  ("documents", "workflow", "signature")),
    UniverseEntry("MDB", "0001441816", "MongoDB, Inc.",
                  "General-purpose developer data platform built on a modern document database, offered as a managed cloud service.",
                  ("data-platform", "database", "devtools")),
    UniverseEntry("NET", "0001477333", "Cloudflare, Inc.",
                  "Global cloud network delivering security, performance and reliability services for internet applications.",
                  ("security", "network", "cdn", "zero-trust")),
    UniverseEntry("OKTA", "0001660134", "Okta, Inc.",
                  "Identity and access management platform providing single sign-on, multi-factor authentication and identity governance.",
                  ("security", "identity", "iam")),
    UniverseEntry("TWLO", "0001447669", "Twilio Inc.",
                  "Cloud communications platform with programmable messaging, voice and customer engagement APIs.",
                  ("communications", "api", "engagement", "marketing")),
    UniverseEntry("ZM", "0001585521", "Zoom Communications Inc.",
                  "Cloud video communications, meetings, phone and contact center collaboration platform.",
                  ("communications", "collaboration", "video")),
    UniverseEntry("BILL", "0001141391", "BILL Holdings, Inc.",
                  "Cloud financial operations platform automating accounts payable, receivable and spend management for SMBs.",
                  ("accounting", "payments", "smb", "workflow")),
    UniverseEntry("PATH", "0001734722", "UiPath Inc.",
                  "Enterprise automation platform for robotic process automation, orchestration and AI-driven workflows.",
                  ("automation", "workflow", "platform", "ai")),
    UniverseEntry("GTLB", "0001653482", "GitLab Inc.",
                  "AI-powered DevSecOps platform for software development, security and operations across the lifecycle.",
                  ("devtools", "security", "collaboration", "platform")),
    UniverseEntry("FROG", "0001679826", "JFrog Ltd.",
                  "Software supply chain platform for binary artifact management, distribution and DevSecOps.",
                  ("devtools", "security", "platform")),
]


def load_universe(sector: str = "enterprise_software") -> list[UniverseEntry]:
    if sector == "enterprise_software":
        return list(ENTERPRISE_SOFTWARE)
    raise ValueError(f"Unknown sector: {sector}")


def tickers(sector: str = "enterprise_software") -> list[str]:
    return [e.ticker for e in load_universe(sector)]


def entry_by_ticker(ticker: str, sector: str = "enterprise_software") -> UniverseEntry:
    for e in load_universe(sector):
        if e.ticker == ticker.upper():
            return e
    raise KeyError(f"{ticker} not in universe {sector}")
