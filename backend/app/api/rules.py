from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_api_key
from app.db import get_session
from app.models import Rule
from app.schemas import RuleCreate, RuleOut, RuleUpdate

router = APIRouter(prefix="/rules", tags=["rules"])


async def _active_rule(db: AsyncSession, rule_id: str) -> Rule | None:
    res = await db.execute(
        select(Rule).where(Rule.rule_id == rule_id, Rule.is_active.is_(True))
    )
    return res.scalar_one_or_none()


@router.get("", response_model=list[RuleOut])
async def list_rules(db: AsyncSession = Depends(get_session)):
    res = await db.execute(
        select(Rule).where(Rule.is_active.is_(True)).order_by(Rule.rule_id)
    )
    return res.scalars().all()


@router.post(
    "", response_model=RuleOut, status_code=201, dependencies=[Depends(require_api_key)]
)
async def create_rule(payload: RuleCreate, db: AsyncSession = Depends(get_session)):
    if await _active_rule(db, payload.rule_id):
        raise HTTPException(status_code=409, detail="rule_id already exists")
    rule = Rule(**payload.model_dump(), version=1, is_active=True)
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.get("/{rule_id}", response_model=RuleOut)
async def get_rule(rule_id: str, db: AsyncSession = Depends(get_session)):
    rule = await _active_rule(db, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="rule not found")
    return rule


@router.put("/{rule_id}", response_model=RuleOut, dependencies=[Depends(require_api_key)])
async def update_rule(
    rule_id: str, payload: RuleUpdate, db: AsyncSession = Depends(get_session)
):
    """Updates create a new immutable version (R3) so past audits stay reproducible."""
    current = await _active_rule(db, rule_id)
    if current is None:
        raise HTTPException(status_code=404, detail="rule not found")
    current.is_active = False
    new = Rule(
        rule_id=rule_id, version=current.version + 1, is_active=True, **payload.model_dump()
    )
    db.add(new)
    await db.commit()
    await db.refresh(new)
    return new


@router.delete("/{rule_id}", status_code=204, dependencies=[Depends(require_api_key)])
async def delete_rule(rule_id: str, db: AsyncSession = Depends(get_session)):
    current = await _active_rule(db, rule_id)
    if current is None:
        raise HTTPException(status_code=404, detail="rule not found")
    current.is_active = False
    await db.commit()
