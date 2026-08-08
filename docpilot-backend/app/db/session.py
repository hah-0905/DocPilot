from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import get_settings

settings = get_settings()

# 创建异步引擎
async_engine = create_async_engine(
    settings.database_url,
    echo=True,  # 打印SQL语句
    pool_size=10,  # 设置连接池活跃的连接数
    max_overflow=20,  # 允许额外的连接数
)


# 创建异步会话工厂
AsyncSessional = async_sessionmaker(
    bind=async_engine,  # 绑定数据库引擎
    class_=AsyncSession,  # 指定会话类
    expire_on_commit=False  # 提交后会话不过期，不会重新查询数据库
)


# 依赖项
async def get_db():
    async with AsyncSessional() as session:
        yield session
