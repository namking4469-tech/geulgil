"""데이터베이스 모델. 기본은 로컬 SQLite, DATABASE_URL 이 있으면 Postgres(Supabase 등)를 쓴다.
파일(원고·전자책·영상)도 DB 에 바이너리로 저장하므로 DATABASE_URL 하나로 모든 데이터가 영구 보관된다."""
from contextlib import contextmanager
from datetime import datetime, date

import streamlit as st
from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, LargeBinary,
                        String, Text, create_engine, select, func)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import ROOT, secret


class Base(DeclarativeBase):
    pass


def _now():
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    pw_hash: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100), default="")
    pen_name: Mapped[str] = mapped_column(String(100), default="")
    birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str] = mapped_column(String(20), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    country: Mapped[str] = mapped_column(String(60), default="")
    address: Mapped[str] = mapped_column(String(300), default="")
    writer_types: Mapped[list] = mapped_column(JSON, default=list)
    debut: Mapped[str] = mapped_column(String(300), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    major_works: Mapped[str] = mapped_column(Text, default="")
    sns: Mapped[dict] = mapped_column(JSON, default=dict)
    photo: Mapped[bytes | None] = mapped_column(LargeBinary)
    provider: Mapped[str] = mapped_column(String(30), default="local")
    provider_id: Mapped[str] = mapped_column(String(255), default="")
    totp_secret: Mapped[str] = mapped_column(String(64), default="")
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    face_enc: Mapped[bytes | None] = mapped_column(LargeBinary)  # 암호화된 얼굴 특징 벡터
    face_login: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    agree_marketing: Mapped[bool] = mapped_column(Boolean, default=False)
    public_profile: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    @property
    def display(self):
        return self.pen_name or self.name or self.username


class Passkey(Base):
    __tablename__ = "passkeys"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    cred_id: Mapped[str] = mapped_column(String(600), unique=True, index=True)
    public_key: Mapped[bytes] = mapped_column(LargeBinary)
    sign_count: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class SessionToken(Base):
    __tablename__ = "session_tokens"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires: Mapped[datetime] = mapped_column(DateTime)


class OneTimeCode(Base):
    __tablename__ = "one_time_codes"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    purpose: Mapped[str] = mapped_column(String(20))
    expires: Mapped[datetime] = mapped_column(DateTime)
    tries: Mapped[int] = mapped_column(Integer, default=0)


class LoginLog(Base):
    __tablename__ = "login_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, index=True)
    method: Mapped[str] = mapped_column(String(30))
    ok: Mapped[bool] = mapped_column(Boolean)
    at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Work(Base):
    __tablename__ = "works"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    filename: Mapped[str] = mapped_column(String(300), default="")
    kind: Mapped[str] = mapped_column(String(10))  # docx / hwp / pdf / image / txt
    blob: Mapped[bytes | None] = mapped_column(LargeBinary)  # 현재 파일(편집 반영)
    text: Mapped[str] = mapped_column(Text, default="")
    html: Mapped[str] = mapped_column(Text, default="")
    lang: Mapped[str] = mapped_column(String(8), default="ko")
    genre: Mapped[str] = mapped_column(String(60), default="")
    length_class: Mapped[str] = mapped_column(String(30), default="")
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="집필 중")
    isbn: Mapped[str] = mapped_column(String(20), default="")
    cover: Mapped[bytes | None] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Version(Base):
    __tablename__ = "versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    text: Mapped[str] = mapped_column(Text, default="")
    html: Mapped[str] = mapped_column(Text, default="")
    blob: Mapped[bytes | None] = mapped_column(LargeBinary)
    note: Mapped[str] = mapped_column(String(300), default="")
    at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Translation(Base):
    __tablename__ = "translations"
    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    lang: Mapped[str] = mapped_column(String(8))
    title: Mapped[str] = mapped_column(String(300), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    engine: Mapped[str] = mapped_column(String(40), default="")
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Ebook(Base):
    __tablename__ = "ebooks"
    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    lang: Mapped[str] = mapped_column(String(8))
    fmt: Mapped[str] = mapped_column(String(8))  # epub / pdf
    title: Mapped[str] = mapped_column(String(300), default="")
    blob: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Promo(Base):
    __tablename__ = "promos"
    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # copy / video / image
    lang: Mapped[str] = mapped_column(String(8), default="ko")
    label: Mapped[str] = mapped_column(String(100), default="")
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    blob: Mapped[bytes | None] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Contest(Base):
    __tablename__ = "contests"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    organizer: Mapped[str] = mapped_column(String(200), default="")
    country: Mapped[str] = mapped_column(String(60), default="")
    genres: Mapped[list] = mapped_column(JSON, default=list)
    length: Mapped[str] = mapped_column(String(200), default="")
    period: Mapped[str] = mapped_column(String(200), default="")  # 통상 접수 시기
    deadline: Mapped[date | None] = mapped_column(Date)  # 확인된 올해 마감일(관리자 입력)
    prize: Mapped[str] = mapped_column(String(300), default="")
    eligibility: Mapped[str] = mapped_column(String(300), default="")
    url: Mapped[str] = mapped_column(String(400), default="")
    note: Mapped[str] = mapped_column(Text, default="")


class DirEntry(Base):
    __tablename__ = "directory"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))  # 에이전시 / 출판사 / 플랫폼 / 지원기관
    name: Mapped[str] = mapped_column(String(300))
    country: Mapped[str] = mapped_column(String(60), default="")
    genres: Mapped[list] = mapped_column(JSON, default=list)
    accepts: Mapped[str] = mapped_column(String(200), default="")  # 투고 방식
    url: Mapped[str] = mapped_column(String(400), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    note: Mapped[str] = mapped_column(Text, default="")


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    work_id: Mapped[int | None] = mapped_column(Integer)
    target_type: Mapped[str] = mapped_column(String(20))  # 공모전 / 에이전시 / 출판사 ...
    target_name: Mapped[str] = mapped_column(String(300))
    sent_to: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(30), default="준비 중")
    body: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    on: Mapped[date] = mapped_column(Date, default=date.today)


class WritingLog(Base):
    __tablename__ = "writing_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    on: Mapped[date] = mapped_column(Date)
    chars: Mapped[int] = mapped_column(Integer, default=0)
    memo: Mapped[str] = mapped_column(String(300), default="")


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    on: Mapped[date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(30), default="마감")
    done: Mapped[bool] = mapped_column(Boolean, default=False)


class Finance(Base):
    __tablename__ = "finance"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    on: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(30))  # 인세 / 원고료 / 상금 / 계약금 / 지출
    work_title: Mapped[str] = mapped_column(String(300), default="")
    counterparty: Mapped[str] = mapped_column(String(200), default="")
    amount: Mapped[float] = mapped_column(Float, default=0)
    memo: Mapped[str] = mapped_column(String(300), default="")


class Contract(Base):
    __tablename__ = "contracts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    work_title: Mapped[str] = mapped_column(String(300), default="")
    counterparty: Mapped[str] = mapped_column(String(200), default="")
    kind: Mapped[str] = mapped_column(String(60), default="출판권")
    start: Mapped[date | None] = mapped_column(Date)
    end: Mapped[date | None] = mapped_column(Date)
    royalty: Mapped[str] = mapped_column(String(100), default="")
    memo: Mapped[str] = mapped_column(Text, default="")


class Setting(Base):
    __tablename__ = "settings"
    user_id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


@st.cache_resource(show_spinner=False)
def _engine():
    url = secret("DATABASE_URL")
    if url:
        url = str(url)
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg2://" + url[len("postgresql://"):]
        eng = create_engine(url, pool_pre_ping=True, pool_recycle=300)
    else:
        path = ROOT / "geulgil.db"
        eng = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    from .seed import seed
    seed(sessionmaker(eng, expire_on_commit=False))
    return eng


def is_persistent() -> bool:
    return bool(secret("DATABASE_URL"))


@contextmanager
def db():
    s = sessionmaker(_engine(), expire_on_commit=False)()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


__all__ = [n for n in dir() if not n.startswith("_")] + ["select", "func"]
