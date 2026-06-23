"""DataStore — DB 접근의 단일 진입점.

DB는 이 모듈을 통해서만 접근한다.
공개: DataStore(클래스), DTO들(불변), init_db, get_store(FastAPI 의존성), session(컨텍스트).
ORM 엔티티·engine·세션은 이 모듈 내부에 두고 외부에 노출하지 않는다.
읽기 메서드는 살아있는 ORM 엔티티가 아니라 **불변 DTO(frozen dataclass)**를 반환한다 —
외부에서 DB 상태를 바꾸는 유일한 경로는 DataStore 쓰기 메서드로 구조적으로 강제된다.
커밋 전략(혼합): 배치 쓰기는 add_*/update_* 후 호출자가 commit(),
단건 CRUD·유지보수(create/delete/cleanup/reset)는 메서드 내부에서 즉시 commit.
"""
from contextlib import contextmanager
from dataclasses import dataclass, fields as _dc_fields
from datetime import datetime

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, Text, Index,
    text, func, and_, desc, or_,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# ── 연결 인프라 ───────────────────────────────────────────
DATABASE_URL = "sqlite:///./data/ai_stocks.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── ORM 엔티티 (내부) ─────────────────────────────────────
class StockSnapshot(Base):
    """일별 주가 스냅샷 - 수집할 때마다 저장 (tier 없음 — 분류는 DataView가 도출)"""
    __tablename__ = "stock_snapshots"

    # (ticker, collected_at) 복합 인덱스 — latest_snapshots GROUP BY,
    # price_history 정렬, latest_snapshot_date max 조회를 인덱스로 커버.
    __table_args__ = (
        Index("ix_snapshots_ticker_collected", "ticker", "collected_at"),
    )

    id          = Column(Integer, primary_key=True, index=True)
    ticker      = Column(String, index=True, nullable=False)
    name        = Column(String, nullable=False)
    sector      = Column(String)
    market      = Column(String)                   # US / KR
    price       = Column(Float)
    price_prev  = Column(Float)                    # 전일 종가
    change_pct  = Column(Float)                    # 당일 등락률(%)
    volume      = Column(Float)
    mkt_cap     = Column(Float)                    # 시총 (USD)
    pe_ratio    = Column(Float)
    pbr         = Column(Float)
    capex        = Column(Float)   # 설비투자 (USD)
    fcf          = Column(Float)   # 잉여현금흐름 (USD)
    payout_ratio = Column(Float)   # 주주환원율 (%)
    week52_high = Column(Float)
    week52_low  = Column(Float)
    collected_at = Column(DateTime, default=datetime.utcnow)


class StockMeta(Base):
    """종목 마스터 - 사용자가 직접 추가/삭제 가능"""
    __tablename__ = "stock_meta"

    id      = Column(Integer, primary_key=True, index=True)
    ticker  = Column(String, unique=True, nullable=False)
    name    = Column(String, nullable=False)
    tier    = Column(String, nullable=False)
    sector  = Column(String)
    market  = Column(String, default="US")
    note    = Column(Text)
    active  = Column(Integer, default=1)   # 0: 비활성


class GroupStock(Base):
    """그룹 전용 종목 (StockMeta와 독립)"""
    __tablename__ = "group_stocks"

    id       = Column(Integer, primary_key=True)
    ticker   = Column(String, unique=True, nullable=False, index=True)
    name     = Column(String, nullable=False)
    market   = Column(String, default="US")
    added_at = Column(DateTime, default=datetime.utcnow)


class UserGroup(Base):
    """사용자 정의 종목 그룹"""
    __tablename__ = "user_groups"

    id         = Column(Integer, primary_key=True)
    name       = Column(String, nullable=False, unique=True)
    note       = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class GroupMember(Base):
    """그룹 구성 종목"""
    __tablename__ = "group_members"

    id       = Column(Integer, primary_key=True)
    group_id = Column(Integer, index=True, nullable=False)
    ticker   = Column(String, index=True, nullable=False)


class CollectLog(Base):
    """수집 이력 로그"""
    __tablename__ = "collect_logs"

    id          = Column(Integer, primary_key=True)
    collected_at = Column(DateTime, default=datetime.utcnow)
    total       = Column(Integer)
    success     = Column(Integer)
    failed      = Column(Integer)
    message     = Column(Text)


def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        for col in ["pbr REAL", "capex REAL", "fcf REAL", "payout_ratio REAL"]:
            try:
                conn.execute(text(f"ALTER TABLE stock_snapshots ADD COLUMN {col}"))
                conn.commit()
            except Exception:
                pass
        # tier는 스냅샷에서 비정규화 제거 — 분류는 DataView가 뷰 시점에 도출
        try:
            conn.execute(text("ALTER TABLE stock_snapshots DROP COLUMN tier"))
            conn.commit()
        except Exception:
            pass
        # (ticker, collected_at) 복합 인덱스 — 기존 DB 소급 생성 (멱등)
        try:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_snapshots_ticker_collected "
                "ON stock_snapshots (ticker, collected_at)"
            ))
            conn.commit()
        except Exception:
            pass


# ── DTO (외부 공개 — 불변, 세션 비바인딩) ──────────────────
# 필드명은 ORM 컬럼명을 그대로 미러링한다 → 소비 코드의 속성 접근(s.ticker 등)이
# 엔티티든 DTO든 동일하게 동작한다. _to_dto가 이 일치를 전제로 매핑한다.
@dataclass(frozen=True)
class SnapshotDTO:
    id: int
    ticker: str
    name: str
    sector: str | None
    market: str | None
    price: float | None
    price_prev: float | None
    change_pct: float | None
    volume: float | None
    mkt_cap: float | None
    pe_ratio: float | None
    pbr: float | None
    capex: float | None
    fcf: float | None
    payout_ratio: float | None
    week52_high: float | None
    week52_low: float | None
    collected_at: datetime | None


@dataclass(frozen=True)
class MetaDTO:
    id: int
    ticker: str
    name: str
    tier: str
    sector: str | None
    market: str | None
    note: str | None
    active: int


@dataclass(frozen=True)
class GroupStockDTO:
    id: int
    ticker: str
    name: str
    market: str | None
    added_at: datetime | None


@dataclass(frozen=True)
class GroupDTO:
    id: int
    name: str
    note: str | None
    created_at: datetime | None


@dataclass(frozen=True)
class MemberDTO:
    id: int
    group_id: int
    ticker: str


@dataclass(frozen=True)
class LogDTO:
    id: int
    collected_at: datetime | None
    total: int | None
    success: int | None
    failed: int | None
    message: str | None


def _to_dto(dto_cls, entity):
    """ORM 엔티티 → DTO. DTO 필드명 = 엔티티 속성명 전제. None이면 None."""
    if entity is None:
        return None
    return dto_cls(**{f.name: getattr(entity, f.name) for f in _dc_fields(dto_cls)})


# ── DataStore ─────────────────────────────────────────────
class DataStore:
    def __init__(self, db: Session):
        self.db = db

    def commit(self):
        self.db.commit()

    # ── 스냅샷 읽기 ────────────────────────────────────────
    def latest_snapshots(self) -> list:
        """종목별 가장 최근 스냅샷 (SnapshotDTO 리스트)."""
        subq = (
            self.db.query(
                StockSnapshot.ticker,
                func.max(StockSnapshot.collected_at).label("max_at"),
            )
            .group_by(StockSnapshot.ticker)
            .subquery()
        )
        rows = (
            self.db.query(StockSnapshot)
            .join(subq, and_(
                StockSnapshot.ticker == subq.c.ticker,
                StockSnapshot.collected_at == subq.c.max_at,
            ))
            .order_by(StockSnapshot.ticker)
            .all()
        )
        return [_to_dto(SnapshotDTO, s) for s in rows]

    def price_history(self, ticker: str, days: int = 30) -> list:
        """특정 종목의 최근 N일 스냅샷 (시간순, SnapshotDTO 리스트)."""
        rows = (
            self.db.query(StockSnapshot)
            .filter(StockSnapshot.ticker == ticker)
            .order_by(desc(StockSnapshot.collected_at))
            .limit(days)
            .all()
        )
        return [_to_dto(SnapshotDTO, s) for s in reversed(rows)]

    def latest_snapshot_date(self, ticker: str):
        """특정 종목의 최신 collected_at (없으면 None) — 중복확인용."""
        return self.db.query(func.max(StockSnapshot.collected_at)).filter(
            StockSnapshot.ticker == ticker
        ).scalar()

    def snapshot_keys(self) -> set:
        """전체 {(ticker, 'YYYY-MM-DD')} 집합 — 백필 중복확인용."""
        rows = self.db.query(StockSnapshot.ticker, StockSnapshot.collected_at).all()
        return {(t, ca.strftime("%Y-%m-%d")) for t, ca in rows if ca}

    def snapshot_dates(self, ticker: str) -> set:
        """특정 종목의 {'YYYY-MM-DD'} 집합 — 단일 백필 중복확인용."""
        rows = self.db.query(StockSnapshot.collected_at).filter(
            StockSnapshot.ticker == ticker
        ).all()
        return {ca.strftime("%Y-%m-%d") for (ca,) in rows if ca}

    def snapshots_missing_metrics(self, ticker: str) -> list:
        """지표(PER/PBR/CAPEX/FCF/주주환원율) 중 하나라도 null인 스냅샷 (SnapshotDTO).

        반환 DTO의 id로 update_snapshot_metrics를 호출해 소급 갱신한다.
        """
        rows = (
            self.db.query(StockSnapshot)
            .filter(
                StockSnapshot.ticker == ticker,
                or_(
                    StockSnapshot.pe_ratio     == None,
                    StockSnapshot.pbr          == None,
                    StockSnapshot.capex        == None,
                    StockSnapshot.fcf          == None,
                    StockSnapshot.payout_ratio == None,
                ),
            )
            .all()
        )
        return [_to_dto(SnapshotDTO, s) for s in rows]

    # ── 스냅샷 쓰기 (배치: stage만, 호출자가 commit) ────────
    def add_snapshot(self, **fields):
        """스냅샷 생성·stage. 외부는 엔티티를 모르고 값만 넘긴다."""
        self.db.add(StockSnapshot(**fields))

    def update_snapshot_metrics(self, snapshot_id: int, **fields):
        """스냅샷 지표 부분 갱신 (배치: stage만, 호출자 commit).

        엔티티를 외부에 넘기지 않고 id+값으로 UPDATE — 소급(fill-metrics)의 쓰기 경로.
        """
        if fields:
            self.db.query(StockSnapshot).filter(
                StockSnapshot.id == snapshot_id
            ).update(fields)

    # ── 유지보수 (즉시 commit) ─────────────────────────────
    def cleanup_duplicates(self) -> int:
        """(ticker, 날짜) 중복 스냅샷 제거 — 각 그룹에서 id 최소만 유지."""
        result = self.db.execute(text("""
            DELETE FROM stock_snapshots
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM stock_snapshots
                GROUP BY ticker, date(collected_at)
            )
        """))
        self.db.commit()
        return result.rowcount

    def reset_all(self):
        """스냅샷·수집로그 전체 삭제 (종목 목록은 유지)."""
        self.db.execute(text("DELETE FROM stock_snapshots"))
        self.db.execute(text("DELETE FROM collect_logs"))
        self.db.commit()

    # ── 수집 로그 ──────────────────────────────────────────
    def add_log(self, **kwargs):
        """수집 로그 추가 (배치: stage만)."""
        self.db.add(CollectLog(**kwargs))

    def latest_log(self):
        """가장 최근 수집 로그 (LogDTO 또는 None)."""
        return _to_dto(LogDTO, self.db.query(CollectLog).order_by(CollectLog.id.desc()).first())

    def recent_logs(self, n: int = 10) -> list:
        rows = self.db.query(CollectLog).order_by(CollectLog.id.desc()).limit(n).all()
        return [_to_dto(LogDTO, r) for r in rows]

    # ── 종목 마스터(StockMeta) ─────────────────────────────
    def _meta_entity(self, ticker: str):
        """내부 쓰기용 살아있는 엔티티 (외부 노출 금지)."""
        return self.db.query(StockMeta).filter(StockMeta.ticker == ticker).first()

    def active_metas(self) -> list:
        rows = self.db.query(StockMeta).filter(StockMeta.active == 1).all()
        return [_to_dto(MetaDTO, m) for m in rows]

    def all_metas_sorted(self) -> list:
        rows = self.db.query(StockMeta).order_by(StockMeta.tier, StockMeta.ticker).all()
        return [_to_dto(MetaDTO, m) for m in rows]

    def get_meta(self, ticker: str):
        """종목 마스터 조회 (MetaDTO 또는 None)."""
        return _to_dto(MetaDTO, self._meta_entity(ticker))

    def meta_count(self) -> int:
        return self.db.query(StockMeta).count()

    def add_meta(self, **kwargs):
        """StockMeta 추가 (즉시 commit). MetaDTO 반환."""
        meta = StockMeta(**kwargs)
        self.db.add(meta)
        self.db.commit()
        return _to_dto(MetaDTO, meta)

    def seed_metas(self, rows: list):
        """초기 마스터 데이터 일괄 삽입 (한 번 commit)."""
        for row in rows:
            self.db.add(StockMeta(**row))
        self.db.commit()

    def set_meta_active(self, ticker: str, active: bool):
        """종목 활성/비활성 설정 (즉시 commit). MetaDTO 또는 None."""
        meta = self._meta_entity(ticker)
        if not meta:
            return None
        meta.active = 1 if active else 0
        self.db.commit()
        return _to_dto(MetaDTO, meta)

    def toggle_meta_active(self, ticker: str):
        """종목 활성 상태 토글 (즉시 commit). MetaDTO 또는 None."""
        meta = self._meta_entity(ticker)
        if not meta:
            return None
        meta.active = 0 if meta.active else 1
        self.db.commit()
        return _to_dto(MetaDTO, meta)

    # ── 그룹 전용 종목(GroupStock) ─────────────────────────
    def get_group_stock(self, ticker: str):
        """그룹 전용 종목 조회 (GroupStockDTO 또는 None)."""
        return _to_dto(GroupStockDTO, self.db.query(GroupStock).filter(
            GroupStock.ticker == ticker).first())

    def all_group_stocks(self) -> list:
        return [_to_dto(GroupStockDTO, s) for s in self.db.query(GroupStock).all()]

    def kr_group_stocks(self) -> list:
        rows = self.db.query(GroupStock).filter(
            GroupStock.ticker.like("%.KS") | GroupStock.ticker.like("%.KQ")
        ).all()
        return [_to_dto(GroupStockDTO, s) for s in rows]

    def add_group_stock(self, ticker: str, name: str, market: str = "US"):
        """GroupStock 추가 (즉시 commit). GroupStockDTO 반환."""
        gs = GroupStock(ticker=ticker, name=name, market=market)
        self.db.add(gs)
        self.db.commit()
        return _to_dto(GroupStockDTO, gs)

    def rename_group_stocks(self, names: dict) -> int:
        """{ticker: 새 이름}으로 GroupStock 이름 일괄 변경 (한 번 commit).
        실제 변경된 건수만 반환 (기존과 같은 이름은 제외)."""
        updated = 0
        for gs in self.db.query(GroupStock).all():   # 내부 쓰기 — 살아있는 엔티티
            new_name = names.get(gs.ticker)
            if new_name and new_name != gs.name:
                gs.name = new_name
                updated += 1
        if updated:
            self.db.commit()
        return updated

    # ── 사용자 그룹(UserGroup) ─────────────────────────────
    def _group_entity(self, group_id: int):
        """내부 쓰기용 살아있는 엔티티 (외부 노출 금지)."""
        return self.db.query(UserGroup).filter(UserGroup.id == group_id).first()

    def all_groups(self) -> list:
        rows = self.db.query(UserGroup).order_by(UserGroup.created_at).all()
        return [_to_dto(GroupDTO, g) for g in rows]

    def get_group(self, group_id: int):
        """그룹 조회 (GroupDTO 또는 None)."""
        return _to_dto(GroupDTO, self._group_entity(group_id))

    def group_by_name(self, name: str):
        """그룹명으로 조회 (GroupDTO 또는 None)."""
        return _to_dto(GroupDTO, self.db.query(UserGroup).filter(
            UserGroup.name == name).first())

    def create_group(self, name: str, note: str = ""):
        """그룹 생성 (즉시 commit). GroupDTO 반환."""
        g = UserGroup(name=name, note=note)
        self.db.add(g)
        self.db.commit()
        self.db.refresh(g)
        return _to_dto(GroupDTO, g)

    def delete_group(self, group_id: int):
        """그룹과 구성원 삭제 (즉시 commit). 존재 여부 bool 반환."""
        g = self._group_entity(group_id)
        if not g:
            return False
        self.db.query(GroupMember).filter(GroupMember.group_id == group_id).delete()
        self.db.delete(g)
        self.db.commit()
        return True

    def rename_group(self, group_id: int, name: str, note: str = ""):
        """그룹명·노트 수정 (즉시 commit). GroupDTO 또는 None."""
        g = self._group_entity(group_id)
        if not g:
            return None
        g.name = name
        g.note = note
        self.db.commit()
        return _to_dto(GroupDTO, g)

    # ── 그룹 구성원(GroupMember) ───────────────────────────
    def all_members(self) -> list:
        return [_to_dto(MemberDTO, m) for m in self.db.query(GroupMember).all()]

    def members_of(self, group_id: int) -> list:
        rows = self.db.query(GroupMember).filter(GroupMember.group_id == group_id).all()
        return [_to_dto(MemberDTO, m) for m in rows]

    def member_exists(self, group_id: int, ticker: str) -> bool:
        return self.db.query(GroupMember).filter(
            GroupMember.group_id == group_id, GroupMember.ticker == ticker
        ).first() is not None

    def add_member(self, group_id: int, ticker: str):
        """그룹에 종목 추가 (즉시 commit)."""
        self.db.add(GroupMember(group_id=group_id, ticker=ticker))
        self.db.commit()

    def remove_member(self, group_id: int, ticker: str):
        """그룹에서 종목 제거 (즉시 commit)."""
        self.db.query(GroupMember).filter(
            GroupMember.group_id == group_id, GroupMember.ticker == ticker
        ).delete()
        self.db.commit()


# ── 세션 팩토리 (세션을 외부에 노출하지 않음) ─────────────
def get_store():
    """FastAPI 의존성 — 요청 단위 DataStore (세션 자동 정리)."""
    db = SessionLocal()
    try:
        yield DataStore(db)
    finally:
        db.close()


@contextmanager
def session():
    """백그라운드(스케줄러·시드)용 DataStore 컨텍스트."""
    db = SessionLocal()
    try:
        yield DataStore(db)
    finally:
        db.close()
