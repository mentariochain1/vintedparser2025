"""
Deprecated: Supabase REST user service has been removed.
This module remains only to avoid import errors; do not use.
"""

class UserServiceRest:  # pragma: no cover
	def __init__(self):
		raise RuntimeError("Supabase REST integration removed. Use PostgreSQL via SQLAlchemy.")


def get_user_service_rest():  # pragma: no cover
	raise RuntimeError("Supabase REST integration removed. Use PostgreSQL via SQLAlchemy.")