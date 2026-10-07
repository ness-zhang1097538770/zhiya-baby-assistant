"""家庭与邀请码：每个邀请码绑定一个独立家庭，实现数据隔离。"""
import secrets

from sqlalchemy.orm import Session

from app.models.models import Child, Family, InviteCode

INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 去掉易混淆字符


def _gen_code() -> str:
    return "".join(secrets.choice(INVITE_ALPHABET) for _ in range(8))


def ensure_bootstrap(db: Session, invite_count: int = 10) -> None:
    """幂等引导：收容既有数据到默认家庭，并生成首批邀请码（每个码一个独立家庭）。"""
    default_family = db.query(Family).order_by(Family.id).first()
    if default_family is None:
        default_family = Family(name="默认家庭")
        db.add(default_family)
        db.commit()
        db.refresh(default_family)

    # 把无归属的既有孩子归到默认家庭
    orphans = db.query(Child).filter(Child.family_id.is_(None)).all()
    for c in orphans:
        c.family_id = default_family.id
    db.commit()

    # 生成首批邀请码（每个码绑定一个新家庭）
    if db.query(InviteCode).count() == 0:
        for _ in range(invite_count):
            family = Family(name="我的家庭")
            db.add(family)
            db.flush()
            db.add(InviteCode(code=_gen_code(), family_id=family.id))
        db.commit()


def generate_invites(db: Session, count: int = 10) -> list[str]:
    """生成新的邀请码，返回码列表（用于分发）。每个码绑定一个独立家庭。"""
    codes: list[str] = []
    for _ in range(count):
        family = Family(name="我的家庭")
        db.add(family)
        db.flush()
        code = _gen_code()
        db.add(InviteCode(code=code, family_id=family.id))
        codes.append(code)
    db.commit()
    return codes
