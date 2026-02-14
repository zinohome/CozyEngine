import asyncio
import os
import sys

# Add backend to sys.path
sys.path.append(os.getcwd())

from app.storage.database import db_manager, Base
# Import all models to register them with Base.metadata
# We need to import the modules where models are defined
from app.storage.models import User, Session, Message, AuditEvent
from app.core.personalities import models as personality_models 
# Add other models if necessary, or just rely on imports in app/storage/models/__init__.py if it re-exports

async def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set")
        return

    print(f"Initializing DB at {db_url}")
    print(f"Registered tables: {list(Base.metadata.tables.keys())}")
    
    # Initialize manager
    db_manager.initialize(db_url)
    
    try:
        # Create all tables
        async with db_manager._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print("Tables created successfully.")
    except Exception as e:
        print(f"Error creating tables: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db_manager.close()

if __name__ == "__main__":
    asyncio.run(main())
