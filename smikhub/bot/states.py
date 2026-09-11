from aiogram.fsm.state import State, StatesGroup


class AddBotStates(StatesGroup):
    waiting_for_token = State()


class IntegrationStates(StatesGroup):
    waiting_for_token = State()


class CreateOrderStates(StatesGroup):
    waiting_for_destination_input = State()


class OrderSettingsStates(StatesGroup):
    waiting_for_new_link = State()
    waiting_for_users_per_day = State()
    waiting_for_users_total = State()


class CabinetStates(StatesGroup):
    waiting_for_deposit_amount = State()
    waiting_for_withdrawal_amount = State()


class AdminStates(StatesGroup):
    waiting_for_user_search = State()
    waiting_for_balance_delta = State()
    waiting_for_platform_field = State()
    waiting_for_category_title = State()
