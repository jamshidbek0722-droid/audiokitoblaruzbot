from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, KeyboardButton, InlineKeyboardButton
import urllib.parse
import database

def get_main_menu(is_user_admin: bool = False) -> ReplyKeyboardMarkup:
    # Read settings
    ai_enabled = database.settings.get("ai_enabled", True)
    
    # Read database.menu_settings
    menu_cfg = getattr(database, "menu_settings", {})
    rows = menu_cfg.get("rows", [
        ["📚 Kitoblar"],
        ["📚 Kutubxonam", "🕒 Tarix"],
        ["🧠 AI Tavsiya", "💬 AI bilan suhbat"],
        ["💡 Kitob Tavsiya Qilish", "🔍 Qidiruv"],
        ["👤 Profil", "ℹ️ Yordam"]
    ])
    labels = menu_cfg.get("labels", {})
    
    builder = ReplyKeyboardBuilder()
    
    # We will build rows one by one
    row_sizes = []
    for r in rows:
        filtered_row = []
        for btn_key in r:
            # Check if this is an AI button and AI is disabled
            if not ai_enabled and btn_key in ["🧠 AI Tavsiya", "💬 AI bilan suhbat"]:
                continue
            
            # Get label (fallback to key)
            label = labels.get(btn_key, btn_key)
            filtered_row.append(KeyboardButton(text=label))
            
        if filtered_row:
            builder.row(*filtered_row)
            row_sizes.append(len(filtered_row))
            
    if is_user_admin:
        builder.row(KeyboardButton(text="⚙️ Admin Panel"))
        row_sizes.append(1)
        
    builder.adjust(*row_sizes)
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
    builder.row(KeyboardButton(text="🔐 Majburiy obuna"), KeyboardButton(text="📝 Footer matnini sozlash"))
    builder.row(KeyboardButton(text="🤖 AI Sozlamalari"), KeyboardButton(text="⚙️ Menyuni Sozlash"))
    builder.row(KeyboardButton(text="👤 Profil Sozlamalari"), KeyboardButton(text="🏠 Asosiy menyu"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def get_category_manage_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Janr qo'shish", callback_data="admin_add_category"))
    builder.row(InlineKeyboardButton(text="❌ Janr o'chirish", callback_data="admin_del_category"))
    builder.row(InlineKeyboardButton(text="🔢 Ustunlar va Tartiblash", callback_data="admin_layout_category"))
    return builder.as_markup()

def get_book_manage_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Kitob qo'shish", callback_data="admin_add_book"))
    builder.row(InlineKeyboardButton(text="✏️ Kitob tahrirlash", callback_data="admin_edit_book"))
    builder.row(InlineKeyboardButton(text="❌ Kitob o'chirish", callback_data="admin_del_book"))
    builder.row(InlineKeyboardButton(text="⚙️ Global Tartiblash", callback_data="admin_config_sorting"))
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

def get_categories_layout_keyboard(categories_dict: dict, prefix: str, columns: int = 2, order: list = None, cancel_btn: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # Sort active categories
    active_cats = [c for c in categories_dict.values() if c.get("status", "active") == "active"]
    
    if order:
        # Sort based on categories_order list
        order_map = {cat_id: index for index, cat_id in enumerate(order)}
        active_cats.sort(key=lambda x: order_map.get(x["id"], 9999))
    else:
        active_cats.sort(key=lambda x: x["name"])
        
    for cat in active_cats:
        builder.add(InlineKeyboardButton(text=cat["name"], callback_data=f"{prefix}:{cat['id']}"))
        
    builder.adjust(columns)
    
    if cancel_btn:
        builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm"))
        
    return builder.as_markup()

def get_multi_category_selector(categories_dict: dict, selected_ids: list, prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    active_cats = [c for c in categories_dict.values() if c.get("status", "active") == "active"]
    active_cats.sort(key=lambda x: x["name"])
    
    for cat in active_cats:
        marker = "✅ " if cat["id"] in selected_ids else ""
        builder.add(InlineKeyboardButton(text=f"{marker}{cat['name']}", callback_data=f"{prefix}_toggle:{cat['id']}"))
        
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="💾 Tasdiqlash", callback_data=f"{prefix}_confirm"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")
    )

    return builder.as_markup()

def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="confirm_yes"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="confirm_no")
    )
    return builder.as_markup()

def get_book_details_keyboard(book_id: str, is_fav: bool, has_pdf: bool, src: str = "") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎧 Tinglash", callback_data=f"play_book:{book_id}"),
        InlineKeyboardButton(text="📥 Yuklab olish (Audio)", callback_data=f"download_audio:{book_id}")
    )
    if has_pdf:
        builder.row(InlineKeyboardButton(text="📄 PDF Yuklash", callback_data=f"download_pdf:{book_id}"))
    
    fav_text = "📚 Kutubxonamdan o'chirish" if is_fav else "📚 Kutubxonamga qo'shish"
    builder.row(InlineKeyboardButton(text=fav_text, callback_data=f"toggle_fav:{book_id}:{src}"))
    
    back_data = f"back_to_books:{book_id}:{src}" if src else f"back_to_books:{book_id}"
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data=back_data))
    return builder.as_markup()

def get_audio_play_keyboard(book_id: str, bot_username: str, rated: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Eshitib tugatdim", callback_data=f"finish_book:{book_id}"))
    
    rate_btn = InlineKeyboardButton(text="⭐ Baholash", callback_data=f"show_rating:{book_id}")
    share_promo = "Sizga ajoyib audiokitobni tavsiya qilaman! Eng sara o'zbekcha audiokitoblar faqat shu botda 👇"
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_username}?start=book_{book_id}&text={urllib.parse.quote(share_promo)}"
    
    share_btn = InlineKeyboardButton(text="📢 Do'stlarga ulashish", url=share_url)
    builder.row(rate_btn, share_btn)
    return builder.as_markup()

def get_book_rating_keyboard(book_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⭐ 1", callback_data=f"rate_b:{book_id}:1"),
        InlineKeyboardButton(text="⭐ 2", callback_data=f"rate_b:{book_id}:2"),
        InlineKeyboardButton(text="⭐ 3", callback_data=f"rate_b:{book_id}:3"),
        InlineKeyboardButton(text="⭐ 4", callback_data=f"rate_b:{book_id}:4"),
        InlineKeyboardButton(text="⭐ 5", callback_data=f"rate_b:{book_id}:5")
    )
    builder.row(InlineKeyboardButton(text="❌ Yopish", callback_data="close_rating"))
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

def get_library_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📖 Mening kitoblarim (Kutubxonam)", callback_data="lib_my_books"))
    builder.row(InlineKeyboardButton(text="🕒 Tarix (Oxirgi tinglanganlar)", callback_data="lib_history"))
    builder.row(InlineKeyboardButton(text="📊 Mening statistikam", callback_data="lib_stats"))
    return builder.as_markup()

def get_admin_sorting_keyboard(current: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    options = [
        ("Tasodifiy (Random)", "random"),
        ("Yuklangan vaqti bo'yicha", "upload_time"),
        ("Qo'yilgan baho bo'yicha", "rating"),
        ("Kitob nomi bo'yicha", "title"),
        ("Kitob muallifi bo'yicha", "author")
    ]
    for label, val in options:
        marker = "✅ " if val == current else ""
        builder.row(InlineKeyboardButton(text=f"{marker}{label}", callback_data=f"set_sort:{val}"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="cancel_fsm"))
    return builder.as_markup()

def get_admin_layout_options_keyboard(current_cols: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="1-ustun" + (" ✅" if current_cols == 1 else ""), callback_data="set_cols:1"),
        InlineKeyboardButton(text="2-ustun" + (" ✅" if current_cols == 2 else ""), callback_data="set_cols:2"),
        InlineKeyboardButton(text="3-ustun" + (" ✅" if current_cols == 3 else ""), callback_data="set_cols:3")
    )
    builder.row(InlineKeyboardButton(text="🔢 Janrlar tartibini o'zgartirish", callback_data="admin_reorder_cats"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="cancel_fsm"))
    return builder.as_markup()

def get_admin_reorder_keyboard(categories_list: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # categories_list is list of tuples: (cat_id, cat_name)
    for index, (cat_id, name) in enumerate(categories_list, 1):
        builder.row(
            InlineKeyboardButton(text=f"{index}. {name}", callback_data="none"),
            InlineKeyboardButton(text="⬆️", callback_data=f"reorder_move:{cat_id}:up"),
            InlineKeyboardButton(text="⬇️", callback_data=f"reorder_move:{cat_id}:down")
        )
    builder.row(
        InlineKeyboardButton(text="💾 Tasdiqlash", callback_data="reorder_confirm"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")
    )
    return builder.as_markup()

def get_help_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📩 Adminga xabar yuborish", callback_data="user_contact_admin"))
    return builder.as_markup()

def get_admin_reply_keyboard(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✍️ Javob berish", callback_data=f"admin_reply_user:{user_id}"))
    return builder.as_markup()

def get_profile_options_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📝 Profilni to'ldirish / Tahrirlash", callback_data="complete_profile"))
    return builder.as_markup()

def get_gender_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🙋‍♂️ Erkak", callback_data="profile_gender:Erkak"),
        InlineKeyboardButton(text="🙋‍♀️ Ayol", callback_data="profile_gender:Ayol")
    )
    return builder.as_markup()

def get_regions_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    regions = [
        "Toshkent", "Andijon", "Buxoro", "Farg'ona", "Jizzax", 
        "Xorazm", "Namangan", "Navoiy", "Qashqadaryo", "Samarqand", 
        "Sirdaryo", "Surxondaryo", "Qoraqalpog'iston Res."
    ]
    for r in regions:
        builder.row(InlineKeyboardButton(text=r, callback_data=f"profile_region:{r}"))
    builder.adjust(2)
    return builder.as_markup()

def get_ai_settings_keyboard(enabled: bool, provider: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    status_text = "🟢 Yoqilgan (ON)" if enabled else "🔴 O'chirilgan (OFF)"
    toggle_text = "🔴 O'chirish" if enabled else "🟢 Yoqish"
    builder.row(InlineKeyboardButton(text=f"AI Holati: {status_text}", callback_data="none"))
    builder.row(InlineKeyboardButton(text=toggle_text, callback_data="admin_toggle_ai"))
    
    prov_text = f"Provayder: {provider}"
    if provider == "GEMINI":
        toggle_prov_text = "🤖 DeepSeek ga o'tish"
    elif provider == "DEEPSEEK":
        toggle_prov_text = "🤖 Groq ga o'tish"
    else:
        toggle_prov_text = "🤖 Gemini ga o'tish"
    builder.row(InlineKeyboardButton(text=prov_text, callback_data="none"))
    builder.row(InlineKeyboardButton(text=toggle_prov_text, callback_data="admin_toggle_ai_provider"))
    
    builder.row(InlineKeyboardButton(text="📊 Statistikani tozalash", callback_data="admin_clear_ai_stats"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="cancel_fsm"))
    return builder.as_markup()

def get_menu_settings_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📝 Button Nomlarini Tahrirlash", callback_data="menu_edit_labels"))
    builder.row(InlineKeyboardButton(text="🔢 Qatorlar (Rows) Tahrirlash", callback_data="menu_edit_rows"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="cancel_fsm"))
    return builder.as_markup()

def get_quiz_keyboard(options: list, prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for idx, opt in enumerate(options):
        builder.row(InlineKeyboardButton(text=opt, callback_data=f"{prefix}:{idx}"))
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm"))
    return builder.as_markup()

def get_profile_settings_keyboard(mandatory: bool, interests: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    mand_text = "🟢 Majburiy Profil: ON" if mandatory else "🔴 Majburiy Profil: OFF"
    int_text = "🟢 Qiziqishlar: ON" if interests else "🔴 Qiziqishlar: OFF"
    
    builder.row(InlineKeyboardButton(text=mand_text, callback_data="admin_toggle_profile_mandatory"))
    builder.row(InlineKeyboardButton(text=int_text, callback_data="admin_toggle_profile_interests"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="cancel_fsm"))
    return builder.as_markup()
