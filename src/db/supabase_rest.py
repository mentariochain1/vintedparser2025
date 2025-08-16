"""
Deprecated: Supabase REST adapter removed. This file remains to avoid import errors.
"""

def get_supabase_rest():  # pragma: no cover
	raise RuntimeError("Supabase REST integration removed. Use PostgreSQL via SQLAlchemy.")


async def close_supabase_rest():  # pragma: no cover
	return None