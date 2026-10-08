"""Execute production ORM statements locally, without external services."""

from sqlalchemy import BigInteger, DateTime, DefaultClause, Integer, MetaData, Text, create_engine, text
from sqlalchemy.dialects.mysql import DATETIME, LONGTEXT, MEDIUMTEXT, TINYINT
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from tests.test_user_account_security import SQLiteAsyncSession


def make_engine():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    metadata = MetaData()
    for table in Base.metadata.tables.values():
        table.to_metadata(metadata)
    # Change only DDL incompatibilities; all queries still use production models.
    for table in metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, (BigInteger, TINYINT)):
                column.type = Integer()
            elif isinstance(column.type, DATETIME):
                column.type = DateTime()
            elif isinstance(column.type, (LONGTEXT, MEDIUMTEXT)):
                column.type = Text()
            if column.server_default is not None and "CURRENT_TIMESTAMP" in str(column.server_default.arg):
                column.server_default = DefaultClause(text("CURRENT_TIMESTAMP"))
    metadata.create_all(engine)
    return engine


class SecuritySession(SQLiteAsyncSession):
    def __init__(self, engine):
        super().__init__(engine)
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return await super().execute(statement)

    async def get(self, model, key, **kwargs):
        return self.session.get(model, key, **kwargs)

    def add(self, instance):
        self.session.add(instance)

    async def flush(self):
        self.session.flush()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        self.session.close()
