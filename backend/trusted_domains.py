import os
from typing import Set

# e-mail domains whose people may open a laboratory without waiting for the platform administrator, read
# from TRUSTED_EMAIL_DOMAINS (comma separated). A domain also covers its subdomains: ufmg.br trusts
# icb.ufmg.br too. A request from any other domain waits for approval.
# Kept short on purpose: students also have university addresses, so each domain is a decision, not a list
# downloaded from somewhere
DEFAULT_TRUSTED_DOMAINS = "ufmg.br"

# suffixes shared by many unrelated institutions; trusting one of them would trust all of them
SHARED_SUFFIXES = {"edu.br", "com.br", "org.br", "net.br", "gov.br", "br", "edu", "com", "org", "net", "gov"}


def clean_domain(entry: str) -> str:
    return entry.strip().lower().lstrip("@.").rstrip(".")


# entries without a dot (a whole country, say) or that are a shared suffix are ignored, not trusted
def trusted_domains() -> Set[str]:
    raw = os.getenv("TRUSTED_EMAIL_DOMAINS", DEFAULT_TRUSTED_DOMAINS)
    domains = {clean_domain(entry) for entry in raw.split(",")}
    return {d for d in domains if "." in d and d not in SHARED_SUFFIXES and " " not in d}


def domain_of(email: str) -> str:
    return email.rsplit("@", 1)[-1].strip().lower().rstrip(".") if "@" in (email or "") else ""


def is_trusted(email: str) -> bool:
    domain = domain_of(email)
    return any(domain == trusted or domain.endswith("." + trusted) for trusted in trusted_domains())
