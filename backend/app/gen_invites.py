"""生成邀请码（用于内测分发）。运行：python -m app.gen_invites [数量]。"""
import sys

from app.db import Base, SessionLocal, engine
from app.services.families import generate_invites


def main():
    count = 10
    if len(sys.argv) > 1:
        try:
            count = int(sys.argv[1])
        except ValueError:
            count = 10
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        codes = generate_invites(db, count)
        print(f"已生成 {len(codes)} 个邀请码（每个码绑定一个独立家庭）：")
        for c in codes:
            print(c)
    finally:
        db.close()


if __name__ == "__main__":
    main()
