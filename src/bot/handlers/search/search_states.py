"""FSM states for the search flow."""

from aiogram.fsm.state import State, StatesGroup


class SearchStates(StatesGroup):
    waiting_for_query = State()
    waiting_for_item_count = State()


__all__ = ["SearchStates"]


