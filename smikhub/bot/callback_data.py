from aiogram.filters.callback_data import CallbackData


class MenuCB(CallbackData, prefix="menu"):
    target: str  # main | sell_ap | buy_ap | cabinet


class AddBotCB(CallbackData, prefix="addbot"):
    action: str  # method | token | cancel


class BotCB(CallbackData, prefix="bot"):
    action: str  # open | refresh | toggle_active | back
    bot_id: int


class CategoryModeCB(CallbackData, prefix="catmode"):
    action: str  # show | set
    bot_id: int
    mode: str = ""


class DisabledCategoryCB(CallbackData, prefix="catdis"):
    action: str  # show | toggle
    bot_id: int
    category_id: int = 0


class PriceCB(CallbackData, prefix="price"):
    action: str  # show | set
    bot_id: int
    value: str = ""


class SponsorsCB(CallbackData, prefix="sponsors"):
    action: str  # show | set
    bot_id: int
    value: int = 0


class IntegrationCB(CallbackData, prefix="integ"):
    action: str  # show | back
    bot_id: int
    provider: str


class PriorityCB(CallbackData, prefix="prio"):
    action: str  # show | move
    bot_id: int
    provider: str = ""
    direction: int = 0


class TokenCB(CallbackData, prefix="token"):
    bot_id: int


class StatsCB(CallbackData, prefix="stats"):
    bot_id: int


class IntegrationsCheckCB(CallbackData, prefix="integcheck"):
    bot_id: int


class DeleteCB(CallbackData, prefix="delbot"):
    action: str  # confirm | yes | cancel
    bot_id: int


class BuyApCB(CallbackData, prefix="buyap"):
    step: str  # create | traffic | destination | cancel
    value: str = ""


class OrderCB(CallbackData, prefix="order"):
    action: str  # open | refresh | toggle_status | back
    order_id: int


class OrderPriceCB(CallbackData, prefix="oprice"):
    action: str  # show | set
    order_id: int
    value: str = ""


class OrderCategoryCB(CallbackData, prefix="ocat"):
    action: str  # show | toggle
    order_id: int
    category_id: int = 0


class OrderLanguageCB(CallbackData, prefix="olang"):
    action: str  # show | toggle
    order_id: int
    code: str = ""


class OrderCountryCB(CallbackData, prefix="ocountry"):
    action: str  # show | toggle
    order_id: int
    code: str = ""


class OrderGenderCB(CallbackData, prefix="ogender"):
    action: str  # show | set
    order_id: int
    value: str = ""


class OrderAgeCB(CallbackData, prefix="oage"):
    action: str  # show | set
    order_id: int
    value: str = ""


class OrderPremiumCB(CallbackData, prefix="oprem"):
    action: str  # show | set
    order_id: int
    value: str = ""


class OrderSettingsCB(CallbackData, prefix="osettings"):
    action: str  # show | change_link | per_day | total | toggle_distribute
    order_id: int


class OrderPlacesCB(CallbackData, prefix="oplaces"):
    order_id: int


class OrderStatsCB(CallbackData, prefix="ostats"):
    order_id: int


class OrderLogCB(CallbackData, prefix="olog"):
    order_id: int


class OrderVerifyAdminCB(CallbackData, prefix="overify"):
    order_id: int


class OrderDeleteCB(CallbackData, prefix="odel"):
    action: str  # confirm | yes | cancel
    order_id: int


class CabinetCB(CallbackData, prefix="cabinet"):
    action: str  # deposit | withdraw | cancel


class DepositCheckCB(CallbackData, prefix="depcheck"):
    invoice_id: int


class AdminMenuCB(CallbackData, prefix="admin"):
    target: str  # main | withdrawals | stats | users | settings | diagnostics


class AdminWithdrawalCB(CallbackData, prefix="adminwd"):
    action: str  # show | approve | reject
    withdrawal_id: int


class AdminStatsCB(CallbackData, prefix="adminstats"):
    target: str  # bots | users


class AdminSettingsCB(CallbackData, prefix="adminset"):
    action: str  # show_prices | toggle_sell | toggle_buy | edit_field
    field: str = ""


class AdminUserCB(CallbackData, prefix="adminuser"):
    action: str  # ban | balance | search_again
    user_id: int = 0


class AdminCategoryCB(CallbackData, prefix="admincat"):
    action: str  # show | detail | add | rename | delete_confirm | delete_yes | delete_cancel
    category_id: int = 0
