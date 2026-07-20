"""Seed demo company + sample compliance rules (SOX 302, AML threshold, KYC)."""

import asyncio

from sqlalchemy import select

from app.db import get_sessionmaker
from app.models import Company, Rule

SAMPLE_RULES = [
    dict(
        rule_id="SOX-302",
        title="CEO/CFO Certification",
        regulation="SOX",
        description="Section 302 requires principal officers to certify financial reports.",
        check_prompt="Does the filing contain CEO and CFO certifications of the financial statements as required by SOX Section 302?",
        severity_weight=9,
    ),
    dict(
        rule_id="AML-THRESHOLD",
        title="AML Transaction Threshold Disclosure",
        regulation="AML",
        description="Disclosure of controls for transactions above reporting thresholds.",
        check_prompt="Does the filing disclose anti-money-laundering controls and reporting of transactions above regulatory thresholds?",
        severity_weight=8,
    ),
    dict(
        rule_id="KYC-BENEFICIAL",
        title="KYC Beneficial Ownership Disclosure",
        regulation="KYC",
        description="Disclosure of beneficial ownership / customer identification program.",
        check_prompt="Does the filing describe a customer identification program and beneficial ownership disclosure consistent with KYC requirements?",
        severity_weight=6,
    ),
]


async def seed() -> None:
    async with get_sessionmaker()() as db:
        if not await db.get(Company, "DEMO"):
            db.add(Company(ticker="DEMO", name="Demo FinTech Corp"))
        for r in SAMPLE_RULES:
            exists = await db.execute(
                select(Rule).where(Rule.rule_id == r["rule_id"], Rule.is_active.is_(True))
            )
            if exists.scalar_one_or_none() is None:
                db.add(Rule(version=1, is_active=True, **r))
        await db.commit()
    print(f"Seeded 1 company and {len(SAMPLE_RULES)} rules.")


if __name__ == "__main__":
    asyncio.run(seed())
