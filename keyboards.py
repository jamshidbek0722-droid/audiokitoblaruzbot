from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, KeyboardButton, InlineKeyboardButton

def get_main_menu(is_user_admin: bool = False) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📚 Janrlar"), KeyboardButton(text="🔍 Qidiruv"))
    builder.row(KeyboardButton(text="⭐ Sevimlilar"), KeyboardButton(text="🕒 Tarix"))
    builder.row(KeyboardButton(text="👤 Profil"), KeyboardButton(text="💡 Kitob Tavsiya Qilish"))
    builder.row(KeyboardButton(text="ℹ️ Yordam"))
    if is_user_admin:
        builder.row(KeyboardButton(text="⚙️ Admin Panel"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="❌ Bekor qilish"))
    return builder.as_markup(resize_keyboard=True)

def get_skip_cancel_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="⏭️ O'tkazib yuborish"))
    builder.row(KeyboardButton(text="❌ Bekor qilish"))
    return builder.as_markup(resize_keyboard=True)

def get_admin_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📁 Janrlarni boshqarish"))
    builder.row(KeyboardButton(text="📚 Kitoblarni boshqarish"), KeyboardButton(text="💡 Tavsiyalar"))
    builder.row(KeyboardButton(text="📢 Xabar yuborish"), KeyboardButton(text="👥 Adminlar"))
    builder.row(KeyboardButton(text="🔐 Majburiy obuna"), KeyboardButton(text="🔄 Bazani yangilash"))
    builder.row(KeyboardButton(text="📥 Bazani eksport qilish"), KeyboardButton(text="🏠 Asosiy menyu"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_category_manage_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Janr qo'shish", callback_data="admin_add_category"))
    builder.row(InlineKeyboardButton(text="❌ Janr o'chirish", callback_data="admin_del_category"))
    return builder.as_markup()

def get_book_manage_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Kitob qo'shish", callback_data="admin_add_book"))
    builder.row(InlineKeyboardButton(text="✏️ Kitob tahrirlash", callback_data="admin_edit_book"))
    builder.row(InlineKeyboardButton(text="❌ Kitob o'chirish", callback_data="admin_del_book"))
    return builder.as_markup()

def get_subscription_manage_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    status_text = "🟢 Yoqilgan (ON)" if enabled else "🔴 O'chirilgan (OFF)"
    toggle_text = "🔴 O'chirish" if enabled else "🟢 Yoqish"
    builder.row(InlineKeyboardButton(text=f"Holat: {status_text}", callback_data="none"))
    builder.row(InlineKeyboardButton(text=toggle_text, callback_data="admin_toggle_sub"))
    builder.row(
        InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="admin_add_sub_channel"),
        InlineKeyboardButton(text="❌ Kanal o'chirish", callback_data="admin_del_sub_channel")
    )
    builder.row(InlineKeyboardButton(text="📜 Kanallar ro'yxati", callback_data="admin_list_sub_channels"))
    return builder.as_markup()

def get_admin_recommendations_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⏳ Kutilayotgan tavsiyalar", callback_data="admin_view_recs_pending"))
    return builder.as_markup()

def get_admin_manage_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="admin_add_new"))
    builder.row(InlineKeyboardButton(text="❌ Admin o'chirish", callback_data="admin_remove_existing"))
    builder.row(InlineKeyboardButton(text="📜 Adminlar ro'yxati", callback_data="admin_list_all"))
    return builder.as_markup()

def get_categories_inline(categories_dict: dict, prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat_id, cat_info in categories_dict.items():
        if cat_info.get("status", "active") == "active":
            builder.row(InlineKeyboardButton(text=cat_info["name"], callback_data=f"{prefix}:{cat_id}"))
    return builder.as_markup()

def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="confirm_yes"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="confirm_no")
    )
    return builder.as_markup()

def get_book_details_keyboard(book_id: str, is_fav: bool, has_pdf: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎧 Tinglash", callback_data=f"play_book:{book_id}"),
        InlineKeyboardButton(text="📥 Yuklab olish", callback_data=f"download_audio:{book_id}")
    )
    if has_pdf:
        builder.row(InlineKeyboardButton(text="📄 PDF Yuklash", callback_data=f"download_pdf:{book_id}"))
    
    fav_text = "⭐ Sevimlilardan o'chirish" if is_fav else "⭐ Sevimlilarga qo'shish"
    builder.row(InlineKeyboardButton(text=fav_text, callback_data=f"toggle_fav:{book_id}"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_books"))
    return builder.as_markup()

def get_subscription_keyboard(channels: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, ch in enumerate(channels, 1):
        builder.row(InlineKeyboardButton(text=f"📢 Kanal #{index}", url=ch["url"]))
    builder.row(InlineKeyboardButton(text="✅ Hammasiga a'zo bo'ldim (Tekshirish)", callback_data="check_sub"))
    return builder.as_markup()

def get_broadcast_types_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📝 Oddiy Matn", callback_data="bc_text"))
    builder.row(InlineKeyboardButton(text="🖼️ Rasm + Matn", callback_data="bc_photo"))
    builder.row(InlineKeyboardButton(text="🎧 Audio + Matn", callback_data="bc_audio"))
    return builder.as_markup()

def get_recommendation_decide_keyboard(rec_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Ma'qullash", callback_data=f"rec_approve:{rec_id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"rec_reject:{rec_id}")
    )
    return builder.as_markup()

def get_pagination_keyboard(current_page: int, total_pages: int, prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buttons = []
    if current_page > 1:
        buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"{prefix}:{current_page - 1}"))
    buttons.append(InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data="none"))
    if current_page < total_pages:
        buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"{prefix}:{current_page + 1}"))
    builder.row(*buttons)
    return builder.as_markup()
