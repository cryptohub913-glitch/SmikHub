from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Продать ОП (Мои боты)", callback_data="cabinet:bots_list")],
        [InlineKeyboardButton(text="📢 Купить ОП (Реклама)", callback_data="cabinet:orders")],
        [InlineKeyboardButton(text="🤝 Партнёрка", callback_data="cabinet:referrals"), InlineKeyboardButton(text="💳 Выплаты", callback_data="cabinet:payouts")],
        [InlineKeyboardButton(text="⭐️ Пополнить Stars", callback_data="stars_menu")]
    ])
