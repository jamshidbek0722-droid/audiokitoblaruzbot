import uuid
import logging
import io
import asyncio

from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import OWNER_ID, STORAGE_CHANNEL_ID
import database
import keyboards
from states import (
    AdminState, AdminBookForm, AdminReplyForm, 
    AdminEditBookState, AdminCategoryLayoutState, AdminSortingState,
    AdminMenuSettingsState, AdminAISettingsState
)

logger = logging.getLogger(__name__)
router = Router()

# Global cancel handler for Admin FSM
@router.message(StateFilter("*"), F.text == "❌ Bekor qilish")
@router.message(StateFilter("*"), Command("cancel"))
async def cancel_admin_fsm(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not database.is_admin(user_id):
        return
        
    await state.clear()
    await message.answer(
        "Amaliyot bekor qilindi.",
        reply_markup=keyboards.get_admin_menu()
    )

ADMIN_MENU_BUTTONS = [
    "⚙️ Admin Panel",
    "🏠 Asosiy menyu",
    "📊 Statistika",
    "📁 Janrlarni boshqarish",
    "📚 Kitoblarni boshqarish",
    "💡 Tavsiyalar",
    "📢 Xabar yuborish",
    "👥 Adminlar",
    "🔐 Majburiy obuna",
    "📝 Footer matnini sozlash",
    "🤖 AI Sozlamalari",
    "⚙️ Menyuni Sozlash"
]

def is_admin_filter(message: Message) -> bool:
    return database.is_admin(message.from_user.id)

@router.message(is_admin_filter, F.text.in_(ADMIN_MENU_BUTTONS))
async def admin_check_message(message: Message, state: FSMContext):
    text = message.text
    if text == "⚙️ Admin Panel":
        await message.answer("⚙️ *Admin Paneliga xush kelibsiz.*", reply_markup=keyboards.get_admin_menu())
        return
        
    elif text == "🏠 Asosiy menyu":
        await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=keyboards.get_main_menu(True))
        return
        
    elif text == "📊 Statistika":
        users_count = len(database.users)
        cats_count = len([c for c in database.categories.values() if c.get("status", "active") == "active"])
        
        active_books = [b for b in database.books.values() if b.get("status", "approved") == "approved"]
        books_count = len(active_books)
        audio_books_count = len([b for b in active_books if b.get("audio_files")])
        pdf_books = len([b for b in active_books if b.get("pdf_file_id")])
        
        # User profile demographics
        completed_profiles = 0
        genders = {"Erkak": 0, "Ayol": 0}
        regions = {}
        total_listened_seconds = 0
        
        for u in database.users.values():
            profile = u.get("profile")
            if profile:
                completed_profiles += 1
                g = profile.get("gender")
                if g in genders:
                    genders[g] += 1
                r = profile.get("region")
                if r:
                    regions[r] = regions.get(r, 0) + 1
            
            # Aggregate listening statistics
            stats = u.get("listening_stats", {})
            total_listened_seconds += stats.get("total_seconds", 0)
                    
        gender_stats = f"  • Erkak: {genders['Erkak']} ta\n  • Ayol: {genders['Ayol']} ta" if completed_profiles > 0 else "  • Ma'lumot yo'q"
        
        region_list = []
        for reg, cnt in sorted(regions.items(), key=lambda x: x[1], reverse=True):
            region_list.append(f"  • {reg}: {cnt} ta")
        region_stats = "\n".join(region_list) if region_list else "  • Ma'lumot yo'q"
        
        # Format total listened hours
        total_hours = total_listened_seconds / 3600.0
        
        stats_text = (
            "📊 *Bot Statistikasi:*\n\n"
            f"• *Foydalanuvchilar soni*: {users_count} ta\n"
            f"• *To'ldirilgan profillar*: {completed_profiles} ta\n"
            f"• *Jami eshitilgan kitoblar soati*: *{total_hours:.2f} soat*\n"
            f"\n*Jins taqsimoti:*\n{gender_stats}\n"
            f"\n*Hududlar bo'yicha taqsimot:*\n{region_stats}\n\n"
            f"• *Faol janrlar soni*: {cats_count} ta\n"
            f"• *Faol kitoblar soni*: {books_count} ta\n"
            f"• *Audio kitoblar*: {audio_books_count} ta\n"
            f"• *PDF kitoblar*: {pdf_books} ta"
        )
        await message.answer(stats_text)
        return
        
    elif text == "📁 Janrlarni boshqarish":
        await message.answer("📁 *Janrlarni boshqarish bo'limi:*", reply_markup=keyboards.get_category_manage_keyboard())
        return
        
    elif text == "📚 Kitoblarni boshqarish":
        await message.answer("📚 *Kitoblarni boshqarish bo'limi:*", reply_markup=keyboards.get_book_manage_keyboard())
        return
        
    elif text == "💡 Tavsiyalar":
        pend_recs = [r for r in database.recommendations.values() if r.get("status", "pending") == "pending"]
        await message.answer(
            f"💡 *Tavsiyalar boshqaruvi*\n\nKutilayotgan tavsiyalar soni: {len(pend_recs)} ta",
            reply_markup=keyboards.get_admin_recommendations_keyboard()
        )
        return
        
    elif text == "📢 Xabar yuborish":
        await message.answer("Xabar turini tanlang:", reply_markup=keyboards.get_broadcast_types_keyboard())
        return
        
    elif text == "👥 Adminlar":
        await message.answer("👥 *Adminlarni boshqarish bo'limi:*", reply_markup=keyboards.get_admin_manage_keyboard())
        return
        
    elif text == "🔐 Majburiy obuna":
        enabled = database.settings.get("mandatory_subscription", False)
        await message.answer("🔐 *Majburiy obunani boshqarish:*", reply_markup=keyboards.get_subscription_manage_keyboard(enabled))
        return
        
    elif text == "📝 Footer matnini sozlash":
        current_footer = database.settings.get("custom_footer", "o'rnatilmagan")
        await state.set_state(AdminState.edit_footer)
        await message.answer(
            f"📝 *Footer matnini sozlash bo'limi*\n\n"
            f"Joriy footer: \n`{current_footer}`\n\n"
            "Yangi footer matnini yuboring (ixtiyoriy, masalan: @kanal_nomi yoki link):\n"
            "Footerni butunlay o'chirish uchun 'o'chirish' deb yozing.",
            reply_markup=keyboards.get_cancel_keyboard()
        )
        return
        
    elif text == "🤖 AI Sozlamalari":
        enabled = database.settings.get("ai_enabled", True)
        provider = database.settings.get("ai_provider", "GEMINI").upper()
        analytics = database.settings.get("ai_analytics", {})
        total_in = analytics.get("total_input_tokens", 0)
        total_out = analytics.get("total_output_tokens", 0)
        cost = analytics.get("total_cost", 0.0)
        
        dashboard_text = (
            "🤖 *AI Tizimi Sozlamalari:*\n\n"
            f"• *AI Holati (Kill-Switch)*: {'Yoqilgan (ON) 🟢' if enabled else 'O\'chirilgan (OFF) 🔴'}\n"
            f"• *Provayder*: *{provider}*\n\n"
            f"📊 *Tokenlar Sarfi Analytics:*\n"
            f"• Kiruvchi (Input) tokenlar: {total_in:,} ta\n"
            f"• Chiquvchi (Output) tokenlar: {total_out:,} ta\n"
            f"• Taxminiy hisoblangan sarf: *${cost:.6f}*"
        )
        await message.answer(dashboard_text, reply_markup=keyboards.get_ai_settings_keyboard(enabled, provider))
        return
        
    elif text == "⚙️ Menyuni Sozlash":
        menu_cfg = getattr(database, "menu_settings", {})
        rows = menu_cfg.get("rows", [])
        
        # Display current row layout
        rows_str = []
        for idx, r in enumerate(rows, 1):
            row_items = ", ".join(r)
            rows_str.append(f"Qator {idx}: `{row_items}`")
        layout_preview = "\n".join(rows_str)
        
        text_menu = (
            "⚙️ *Botning Asosiy Menyu Sozlamalari:*\n\n"
            "Mavjud qatorlar joylashuvi:\n"
            f"{layout_preview}\n\n"
            "Nima qilmoqchisiz?"
        )
        await message.answer(text_menu, reply_markup=keyboards.get_menu_settings_keyboard())
        return


# ----------------- FOOTER EDIT HANDLER -----------------
@router.message(AdminState.edit_footer)
async def process_edit_footer(message: Message, state: FSMContext):
    await state.clear()
    text = message.text.strip()
    
    if text.lower() == "o'chirish":
        new_footer = ""
    else:
        new_footer = text
        
    database.settings["custom_footer"] = new_footer
    
    log_text = f"#SETTINGS\nCUSTOM_FOOTER: {new_footer}"
    try:
        await message.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=log_text)
    except Exception:
        pass
        
    await database.save_index(message.bot)
    footer_disp = new_footer if new_footer else "o'chirilgan"
    await message.answer(
        f"✅ Footer matni muvaffaqiyatli yangilandi: \n`{footer_disp}`",
        reply_markup=keyboards.get_admin_menu()
    )

# ----------------- ADMIN REPLY HANDLER -----------------
@router.callback_query(F.data.startswith("admin_reply_user:"))
async def start_admin_reply(callback: CallbackQuery, state: FSMContext):
    target_user_id = int(callback.data.split(":")[1])
    await state.update_data(target_user_id=target_user_id)
    await state.set_state(AdminReplyForm.message)
    await callback.message.answer(
        f"✍️ ID `{target_user_id}` bo'lgan foydalanuvchiga yuboriladigan javob xabarini yozing:",
        reply_markup=keyboards.get_cancel_keyboard()
    )
    await callback.answer()

@router.message(AdminReplyForm.message)
async def process_admin_reply_message(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    
    target_user_id = data.get("target_user_id")
    if not target_user_id:
        await message.answer("Xatolik: foydalanuvchi ID topilmadi.", reply_markup=keyboards.get_admin_menu())
        return
        
    reply_text = message.text.strip()
    if not reply_text:
        await message.answer("Javob matni bo'sh bo'lishi mumkin emas.")
        return
        
    try:
        await message.bot.send_message(
            chat_id=target_user_id,
            text=f"✉️ *Adminlardan javob keldi:*\n\n{reply_text}"
        )
        await message.answer("✅ Javob xabari foydalanuvchiga muvaffaqiyatli yuborildi.", reply_markup=keyboards.get_admin_menu())
    except Exception as e:
        await message.answer(f"⚠️ Xabarni foydalanuvchiga yuborib bo'lmadi.\nXatolik: {e}", reply_markup=keyboards.get_admin_menu())

# ----------------- ADMINS MANAGEMENT -----------------
@router.callback_query(F.data == "admin_list_all")
async def list_admins(callback: CallbackQuery):
    admin_list = []
    for adm in database.admins:
        name = "Owner" if adm == OWNER_ID else f"Admin (ID: {adm})"
        admin_list.append(f"• {name}")
    text = "👥 *Tizim adminlari ro'yxati:*\n\n" + "\n".join(admin_list)
    await callback.message.answer(text)
    await callback.answer()

@router.callback_query(F.data == "admin_add_new")
async def request_add_admin(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if user_id != OWNER_ID:
        await callback.answer("Faqat asosiy Owner admin qo'sha oladi!", show_alert=True)
        return
        
    await state.set_state(AdminState.add_admin)
    await callback.message.answer("Yangi adminning Telegram ID raqamini kiriting:", reply_markup=keyboards.get_cancel_keyboard())
    await callback.answer()

@router.message(AdminState.add_admin)
async def process_add_admin(message: Message, state: FSMContext):
    await state.clear()
    try:
        new_adm_id = int(message.text.strip())
    except ValueError:
        await message.answer("Xato ID format! ID faqat raqamlardan iborat bo'lishi kerak.", reply_markup=keyboards.get_admin_menu())
        return
        
    database.admins.add(new_adm_id)
    
    admin_log = f"#ADMIN\nID: {new_adm_id}\nSTATUS: active"
    await message.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=admin_log)
    
    await database.save_index(message.bot)
    await message.answer(f"✅ Admin muvaffaqiyatli qo'shildi (ID: {new_adm_id}).", reply_markup=keyboards.get_admin_menu())

@router.callback_query(F.data == "admin_remove_existing")
async def request_remove_admin(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id != OWNER_ID:
        await callback.answer("Faqat asosiy Owner adminni o'chira oladi!", show_alert=True)
        return
        
    builder = keyboards.InlineKeyboardBuilder()
    for adm in database.admins:
        if adm != OWNER_ID:
            builder.row(keyboards.InlineKeyboardButton(text=f"❌ O'chirish: {adm}", callback_data=f"del_adm:{adm}"))
            
    if not builder.as_markup().inline_keyboard:
        await callback.message.answer("O'chirish uchun boshqa admin topilmadi.")
        await callback.answer()
        return
        
    await callback.message.answer("O'chirmoqchi bo'lgan adminni tanlang:", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("del_adm:"))
async def process_remove_admin(callback: CallbackQuery):
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return
        
    del_id = int(callback.data.split(":")[1])
    if del_id == OWNER_ID:
        await callback.answer("Asosiy egasini o'chirib bo'lmaydi!", show_alert=True)
        return
        
    if del_id in database.admins:
        database.admins.remove(del_id)
        
        admin_log = f"#ADMIN\nID: {del_id}\nSTATUS: removed"
        await callback.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=admin_log)
        
        await database.save_index(callback.bot)
        await callback.message.edit_text(f"✅ Admin o'chirildi (ID: {del_id}).")
    await callback.answer()

# ----------------- CATEGORY MANAGEMENT (WITH COLUMNS AND ORDER) -----------------
@router.callback_query(F.data == "admin_add_category")
async def start_add_category(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.add_category)
    await callback.message.answer("Yangi janr nomini kiriting:", reply_markup=keyboards.get_cancel_keyboard())
    await callback.answer()

@router.message(AdminState.add_category)
async def process_add_category(message: Message, state: FSMContext):
    await state.clear()
    name = message.text.strip()
    if not name:
        await message.answer("Nom bo'sh bo'lishi mumkin emas.", reply_markup=keyboards.get_admin_menu())
        return
        
    cat_id = str(uuid.uuid4())[:8]
    database.categories[cat_id] = {
        "id": cat_id,
        "name": name,
        "status": "active"
    }
    
    # Append to order list if exists
    order = database.settings.setdefault("categories_order", [])
    if cat_id not in order:
        order.append(cat_id)
        
    log_text = f"#CATEGORY\nID: {cat_id}\nNAME: {name}\nSTATUS: active"
    await message.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=log_text)
    
    await database.save_index(message.bot)
    await message.answer(f"✅ Yangi janr yaratildi: {name}", reply_markup=keyboards.get_admin_menu())

@router.callback_query(F.data == "admin_del_category")
async def list_del_category(callback: CallbackQuery):
    builder = keyboards.InlineKeyboardBuilder()
    for cat_id, cat_info in database.categories.items():
        if cat_info.get("status", "active") == "active":
            builder.row(keyboards.InlineKeyboardButton(text=cat_info["name"], callback_data=f"del_cat:{cat_id}"))
            
    if not builder.as_markup().inline_keyboard:
        await callback.message.answer("Janrlar mavjud emas.")
        await callback.answer()
        return
        
    await callback.message.answer("O'chirmoqchi bo'lgan janrni tanlang:", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("del_cat:"))
async def process_del_category(callback: CallbackQuery):
    cat_id = callback.data.split(":")[1]
    if cat_id in database.categories:
        database.categories[cat_id]["status"] = "removed"
        
        # Remove from order settings
        order = database.settings.get("categories_order", [])
        if cat_id in order:
            order.remove(cat_id)
            
        log_text = f"#CATEGORY\nID: {cat_id}\nNAME: {database.categories[cat_id]['name']}\nSTATUS: removed"
        await callback.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=log_text)
        
        await database.save_index(callback.bot)
        await callback.message.edit_text("✅ Janr o'chirildi (Mavjud kitoblar saqlanib qoladi).")
    await callback.answer()

# ----------------- CATEGORY LAYOUT CONFIGURATION -----------------
@router.callback_query(F.data == "admin_layout_category")
async def start_category_layout_config(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminCategoryLayoutState.select)
    current_cols = database.settings.get("categories_columns", 2)
    kb = keyboards.get_admin_layout_options_keyboard(current_cols)
    await callback.message.edit_text(
        f"📁 *Janrlar ustunlari va tartibini sozlash:*\n\n"
        f"Hozirgi ustunlar soni: *{current_cols} ustun*",
        reply_markup=kb
    )
    await callback.answer()

@router.callback_query(AdminCategoryLayoutState.select, F.data.startswith("set_cols:"))
async def process_set_columns(callback: CallbackQuery, state: FSMContext):
    cols = int(callback.data.split(":")[1])
    database.settings["categories_columns"] = cols
    await database.save_index(callback.bot)
    
    # Redraw
    kb = keyboards.get_admin_layout_options_keyboard(cols)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await callback.answer(f"Ustunlar soni {cols} qilib belgilandi.")

@router.callback_query(AdminCategoryLayoutState.select, F.data == "admin_reorder_cats")
async def start_category_reorder(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminCategoryLayoutState.order)
    
    # Fetch active categories
    active_cats = [c for c in database.categories.values() if c.get("status", "active") == "active"]
    order = database.settings.get("categories_order", [])
    
    # Align order list
    order_map = {cat_id: index for index, cat_id in enumerate(order)}
    active_cats.sort(key=lambda x: order_map.get(x["id"], 9999))
    
    # Store list of IDs in FSM
    reorder_list = [c["id"] for c in active_cats]
    await state.update_data(reorder_list=reorder_list)
    
    categories_list = [(c["id"], c["name"]) for c in active_cats]
    kb = keyboards.get_admin_reorder_keyboard(categories_list)
    
    await callback.message.edit_text(
        "🔢 *Janrlarni tartibini o'zgartiring:*\n\n"
        "Tepadagi va pastdagi o'qlar yordamida janrlar o'rnini almashtiring:",
        reply_markup=kb
    )
    await callback.answer()

@router.callback_query(AdminCategoryLayoutState.order, F.data.startswith("reorder_move:"))
async def process_category_reorder_move(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    cat_id = parts[1]
    direction = parts[2]
    
    fsm_data = await state.get_data()
    reorder_list = list(fsm_data.get("reorder_list", []))
    
    if cat_id not in reorder_list:
        await callback.answer()
        return
        
    idx = reorder_list.index(cat_id)
    if direction == "up" and idx > 0:
        reorder_list[idx], reorder_list[idx - 1] = reorder_list[idx - 1], reorder_list[idx]
    elif direction == "down" and idx < len(reorder_list) - 1:
        reorder_list[idx], reorder_list[idx + 1] = reorder_list[idx + 1], reorder_list[idx]
        
    await state.update_data(reorder_list=reorder_list)
    
    # Rebuild keyboard
    categories_list = []
    for cid in reorder_list:
        cat_info = database.categories.get(cid)
        if cat_info:
            categories_list.append((cid, cat_info["name"]))
            
    kb = keyboards.get_admin_reorder_keyboard(categories_list)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await callback.answer()

@router.callback_query(AdminCategoryLayoutState.order, F.data == "reorder_confirm")
async def process_category_reorder_confirm(callback: CallbackQuery, state: FSMContext):
    fsm_data = await state.get_data()
    reorder_list = fsm_data.get("reorder_list", [])
    await state.clear()
    
    database.settings["categories_order"] = reorder_list
    await database.save_index(callback.bot)
    
    await callback.message.edit_text(
        "✅ Janrlar tartibi muvaffaqiyatli saqlandi!",
        reply_markup=keyboards.get_category_manage_keyboard()
    )
    await callback.answer()

# ----------------- ADMIN BOOK CREATION FLOW (MULTI-AUDIOS AND GENRES) -----------------
@router.callback_query(F.data == "admin_add_book")
async def start_add_book(callback: CallbackQuery, state: FSMContext):
    active_cats = {k: v for k, v in database.categories.items() if v.get("status", "active") == "active"}
    if not active_cats:
        await callback.answer("Avval bitta janr yarating!", show_alert=True)
        return
        
    await state.set_state(AdminBookForm.title)
    await callback.message.answer("📖 Kitob nomini kiriting:", reply_markup=keyboards.get_cancel_keyboard())
    await callback.answer()

@router.message(AdminBookForm.title)
async def process_book_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(AdminBookForm.author)
    await message.answer("✍️ Kitob muallifini kiriting:", reply_markup=keyboards.get_cancel_keyboard())

@router.message(AdminBookForm.author)
async def process_book_author(message: Message, state: FSMContext):
    await state.update_data(author=message.text.strip())
    await state.set_state(AdminBookForm.description)
    await message.answer(
        "📝 Kitob tavsifini kiriting (ixtiyoriy):",
        reply_markup=keyboards.get_skip_cancel_keyboard()
    )

@router.message(AdminBookForm.description)
async def process_book_desc(message: Message, state: FSMContext):
    text = message.text.strip()
    if text == "⏭️ O'tkazib yuborish":
        await state.update_data(description="")
    else:
        await state.update_data(description=text)
        
    # Multi-category selector grid
    await state.update_data(selected_categories=[])
    await state.set_state(AdminBookForm.category)
    
    kb = keyboards.get_multi_category_selector(database.categories, [], "admin_book_cat")
    await message.answer("📁 Janrlarni tanlang (Bir nechta tanlashingiz mumkin) va 'Tasdiqlash' bosing:", reply_markup=kb)

@router.callback_query(AdminBookForm.category, F.data.startswith("admin_book_cat_toggle:"))
async def process_book_category_toggle(callback: CallbackQuery, state: FSMContext):
    cat_id = callback.data.split(":")[1]
    data = await state.get_data()
    selected = data.get("selected_categories", [])
    
    if cat_id in selected:
        selected.remove(cat_id)
    else:
        selected.append(cat_id)
        
    await state.update_data(selected_categories=selected)
    
    kb = keyboards.get_multi_category_selector(database.categories, selected, "admin_book_cat")
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await callback.answer()

@router.callback_query(AdminBookForm.category, F.data == "admin_book_cat_confirm")
async def process_book_category_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_categories", [])
    
    if not selected:
        await callback.answer("Kamida bitta janr tanlash majburiy!", show_alert=True)
        return
        
    await state.set_state(AdminBookForm.keywords)
    await callback.message.delete()
    await callback.message.answer(
        "🔍 Kitobni qidirishda yordam beradigan kalit so'zlarni (vergul bilan ajratib) kiriting (ixtiyoriy):\n",
        reply_markup=keyboards.get_skip_cancel_keyboard()
    )
    await callback.answer()

@router.message(AdminBookForm.keywords)
async def process_book_keywords(message: Message, state: FSMContext):
    text = message.text.strip()
    if text == "⏭️ O'tkazib yuborish":
        keywords = []
    else:
        keywords = [kw.strip() for kw in text.split(",") if kw.strip()]
        
    await state.update_data(keywords=keywords)
    await state.set_state(AdminBookForm.audio)
    await state.update_data(audio_files=[])
    
    builder = keyboards.InlineKeyboardBuilder()
    builder.row(
        keyboards.InlineKeyboardButton(text="✅ Yakunlash", callback_data="admin_book_audio_done"),
        keyboards.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")
    )
    await message.answer(
        "🎧 Kitobning audio fayllarini yuboring (MAJBURIY - bir yoki bir nechta audio yuboring):\n"
        "Fayllarni yuborib bo'lgach, '✅ Yakunlash' tugmasini bosing.",
        reply_markup=builder.as_markup()
    )

@router.message(AdminBookForm.audio)
async def process_book_audio_upload(message: Message, state: FSMContext):
    file_id = None
    file_type = None
    duration = 0
    
    if message.audio:
        file_id = message.audio.file_id
        file_type = "audio"
        duration = message.audio.duration or 0
    elif message.document and message.document.mime_type and message.document.mime_type.startswith("audio/"):
        file_id = message.document.file_id
        file_type = "document"
        
    if not file_id:
        await message.answer(
            "⚠️ Xatolik! Iltimos, audio fayl yuboring yoki bekor qilish uchun 'Bekor qilish' yozing."
        )
        return
        
    data = await state.get_data()
    audio_files = data.get("audio_files", [])
    audio_files.append({
        "file_id": file_id,
        "file_type": file_type,
        "duration": duration
    })
    await state.update_data(audio_files=audio_files)
    
    builder = keyboards.InlineKeyboardBuilder()
    builder.row(
        keyboards.InlineKeyboardButton(text="✅ Yakunlash", callback_data="admin_book_audio_done"),
        keyboards.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")
    )
    await message.answer(
        f"✅ {len(audio_files)}-audio qabul qilindi. Yana yuborishingiz yoki yakunlashingiz mumkin:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(AdminBookForm.audio, F.data == "admin_book_audio_done")
async def process_book_audio_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    audio_files = data.get("audio_files", [])
    
    if not audio_files:
        await callback.answer("Kamida bitta audio fayl yuborishingiz majburiy!", show_alert=True)
        return
        
    await state.set_state(AdminBookForm.cover)
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    builder = keyboards.InlineKeyboardBuilder()
    builder.row(
        keyboards.InlineKeyboardButton(text="⏭️ O'tkazib yuborish", callback_data="admin_book_cover_skip"),
        keyboards.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")
    )
    await callback.message.answer(
        "🖼️ Kitob muqovasi uchun rasm yuboring (ixtiyoriy):",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(AdminBookForm.cover, F.data == "admin_book_cover_skip")
async def process_book_cover_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(cover_file_id="")
    await state.set_state(AdminBookForm.pdf)
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    builder = keyboards.InlineKeyboardBuilder()
    builder.row(
        keyboards.InlineKeyboardButton(text="⏭️ O'tkazib yuborish", callback_data="admin_book_pdf_skip"),
        keyboards.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")
    )
    await callback.message.answer(
        "📄 Kitobning PDF faylini yuboring (ixtiyoriy):",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.message(AdminBookForm.cover)
async def process_book_cover(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer("Iltimos, rasm yuboring yoki o'tkazib yuboring.")
        return
        
    await state.update_data(cover_file_id=message.photo[-1].file_id)
    await state.set_state(AdminBookForm.pdf)
    
    builder = keyboards.InlineKeyboardBuilder()
    builder.row(
        keyboards.InlineKeyboardButton(text="⏭️ O'tkazib yuborish", callback_data="admin_book_pdf_skip"),
        keyboards.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")
    )
    await message.answer(
        "📄 Kitobning PDF faylini yuboring (ixtiyoriy):",
        reply_markup=builder.as_markup()
    )

@router.callback_query(AdminBookForm.pdf, F.data == "admin_book_pdf_skip")
async def process_book_pdf_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(pdf_file_id="")
    await show_admin_book_summary(callback.message, state)
    await callback.answer()

@router.message(AdminBookForm.pdf)
async def process_book_pdf(message: Message, state: FSMContext):
    if not message.document:
        await message.answer("Iltimos, hujjat yuboring yoki o'tkazib yuboring.")
        return
        
    await state.update_data(pdf_file_id=message.document.file_id)
    await show_admin_book_summary(message, state)

async def show_admin_book_summary(message: Message, state: FSMContext):
    data = await state.get_data()
    
    cat_names = []
    for c_id in data["selected_categories"]:
        cat_info = database.categories.get(c_id)
        if cat_info:
            cat_names.append(cat_info["name"])
    cat_str = ", ".join(cat_names) if cat_names else "Noma'lum"
    
    desc_val = data.get('description') or "yo'q"
    audio_files = data.get("audio_files", [])
    cover_status = "bor" if data.get('cover_file_id') else "yo'q"
    pdf_status = "bor" if data.get('pdf_file_id') else "yo'q"
    kws_val = ", ".join(data.get("keywords", [])) if data.get("keywords") else "yo'q"
    
    summary = (
        "📚 *Kitob tafsilotlari:*\n\n"
        f"• *Nomi*: {data['title']}\n"
        f"• *Muallif*: {data['author']}\n"
        f"• *Janrlar*: {cat_str}\n"
        f"• *Kalit so'zlar*: {kws_val}\n"
        f"• *Tavsif*: {desc_val}\n"
        f"• *Audio qismlar*: {len(audio_files)} ta\n"
        f"• *Muqova*: {cover_status}\n"
        f"• *PDF*: {pdf_status}\n\n"
        "Tizimga saqlashni tasdiqlaysizmi?"
    )
    
    await state.set_state(AdminBookForm.confirm)
    await message.answer(summary, reply_markup=keyboards.get_confirmation_keyboard())
    await message.answer("Amalni bajarish uchun inline tugmalardan foydalaning.", reply_markup=keyboards.get_cancel_keyboard())

@router.callback_query(AdminBookForm.confirm, F.data.startswith("confirm_"))
async def process_book_confirmation(callback: CallbackQuery, state: FSMContext):
    decision = callback.data.split("_")[1]
    
    if decision == "no":
        await state.clear()
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer("Kitob qo'shish bekor qilindi.", reply_markup=keyboards.get_admin_menu())
        await callback.answer()
        return
        
    data = await state.get_data()
    await state.clear()
    
    try:
        await callback.message.delete()
    except Exception:
        pass
    status_msg = await callback.message.answer("⌛ Fayllar saqlash kanaliga yuklanmoqda. Iltimos, kuting...")
    
    bot = callback.bot
    book_id = str(uuid.uuid4())[:8]
    
    # Upload/Forward each audio to the storage channel
    uploaded_audios = []
    for idx, f in enumerate(data["audio_files"], 1):
        try:
            if f["file_type"] == "document":
                sent_audio = await bot.send_document(chat_id=STORAGE_CHANNEL_ID, document=f["file_id"])
            else:
                sent_audio = await bot.send_audio(chat_id=STORAGE_CHANNEL_ID, audio=f["file_id"])
            
            uploaded_audios.append({
                "file_id": f["file_id"],
                "file_type": f["file_type"],
                "duration": f.get("duration", 0),
                "message_id": sent_audio.message_id
            })
        except Exception as e:
            logger.error(f"Error uploading audio part {idx} to channel: {e}")
            
    if data["cover_file_id"]:
        try:
            await bot.send_photo(chat_id=STORAGE_CHANNEL_ID, photo=data["cover_file_id"])
        except Exception as e:
            logger.error(f"Error uploading cover to channel: {e}")
            
    if data["pdf_file_id"]:
        try:
            await bot.send_document(chat_id=STORAGE_CHANNEL_ID, document=data["pdf_file_id"])
        except Exception as e:
            logger.error(f"Error uploading PDF to channel: {e}")
            
    book_entry = {
        "id": book_id,
        "title": data["title"],
        "author": data["author"],
        "description": data["description"].replace("\n", "\\n") if data["description"] else "",
        "categories": data["selected_categories"],
        "keywords": data.get("keywords", []),
        "ratings": {},
        "audio_files": uploaded_audios,
        "pdf_file_id": data["pdf_file_id"],
        "cover_file_id": data["cover_file_id"],
        "duration": sum(f.get("duration", 0) for f in uploaded_audios),
        "source": "admin",
        "status": "approved",
        "created_at": datetime.now().isoformat()
    }
    
    database.books[book_id] = book_entry
    
    pdf_val = data['pdf_file_id'] if data['pdf_file_id'] else "yoq"
    cover_val = data['cover_file_id'] if data['cover_file_id'] else "yoq"
    kws_str = ", ".join(data.get("keywords", [])) if data.get("keywords") else "yoq"
    
    log_text = (
        "#BOOK\n"
        f"ID: {book_id}\n"
        f"TITLE: {data['title']}\n"
        f"AUTHOR: {data['author']}\n"
        f"DESCRIPTION: {book_entry['description']}\n"
        f"CATEGORY: {data['selected_categories'][0] if data['selected_categories'] else 'yoq'}\n"
        f"KEYWORDS: {kws_str}\n"
        f"AUDIO_FILE_ID: {uploaded_audios[0]['file_id'] if uploaded_audios else 'yoq'}\n"
        f"AUDIO_MESSAGE_ID: {uploaded_audios[0]['message_id'] if uploaded_audios else 'yoq'}\n"
        f"PDF_FILE_ID: {pdf_val}\n"
        f"COVER_FILE_ID: {cover_val}\n"
        f"SOURCE: admin\n"
        f"STATUS: approved"
    )
    
    try:
        await bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=log_text)
    except Exception as e:
        logger.error(f"Error sending log text to channel: {e}")
        
    await database.save_index(bot)
    
    await status_msg.delete()
    await bot.send_message(
        chat_id=callback.from_user.id,
        text=f"✅ Kitob muvaffaqiyatli yaratildi: *{data['title']}*",
        reply_markup=keyboards.get_admin_menu()
    )
    await callback.answer()

# ----------------- EDIT BOOK (WITH MULTI-AUDIOS AND PDF EDITING) -----------------
@router.callback_query(F.data == "admin_edit_book")
@router.callback_query(F.data.startswith("admin_edit_page:"))
async def start_edit_book(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    page = int(parts[1]) if len(parts) > 1 else 1
    
    active_books = [b for b in database.books.values() if b.get("status", "approved") == "approved"]
    if not active_books:
        await callback.answer("Tizimda tahrirlash uchun kitoblar mavjud emas.", show_alert=True)
        return
        
    active_books.sort(key=lambda x: x.get("title", "").lower())
    
    PAGE_SIZE = 10
    total = len(active_books)
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    
    if page < 1: page = 1
    if page > total_pages: page = total_pages
    
    start_idx = (page - 1) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_books = active_books[start_idx:end_idx]
    
    builder = keyboards.InlineKeyboardBuilder()
    for b in page_books:
        builder.row(keyboards.InlineKeyboardButton(text=f"{b['title']} - {b['author']}", callback_data=f"edit_b_sel:{b['id']}"))
        
    nav_row = []
    if page > 1:
        nav_row.append(keyboards.InlineKeyboardButton(text="⏪ Oldingi", callback_data=f"admin_edit_page:{page - 1}"))
    nav_row.append(keyboards.InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="none"))
    if page < total_pages:
        nav_row.append(keyboards.InlineKeyboardButton(text="Keyingi ⏩", callback_data=f"admin_edit_page:{page + 1}"))
    builder.row(*nav_row)
    
    builder.row(keyboards.InlineKeyboardButton(text="🔙 Orqaga", callback_data="cancel_fsm"))
    
    text = "Tahrirlamoqchi bo'lgan kitobni tanlang:"
    await state.set_state(AdminEditBookState.select)
    
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except Exception:
        await callback.message.answer(text, reply_markup=builder.as_markup())
        
    await callback.answer()

@router.callback_query(AdminEditBookState.select, F.data.startswith("edit_b_sel:"))
async def select_book_to_edit(callback: CallbackQuery, state: FSMContext):
    book_id = callback.data.split(":")[1]
    await state.update_data(book_id=book_id)
    await state.set_state(AdminEditBookState.field)
    
    builder = keyboards.InlineKeyboardBuilder()
    builder.row(
        keyboards.InlineKeyboardButton(text="Nomi (Title)", callback_data="edit_f:title"),
        keyboards.InlineKeyboardButton(text="Muallifi (Author)", callback_data="edit_f:author")
    )
    builder.row(
        keyboards.InlineKeyboardButton(text="Tavsifi (Description)", callback_data="edit_f:description"),
        keyboards.InlineKeyboardButton(text="Kalit so'zlar", callback_data="edit_f:keywords")
    )
    builder.row(
        keyboards.InlineKeyboardButton(text="Muqova (Cover)", callback_data="edit_f:cover"),
        keyboards.InlineKeyboardButton(text="Janr (Genre)", callback_data="edit_f:category")
    )
    builder.row(
        keyboards.InlineKeyboardButton(text="Audioni tahrirlash", callback_data="edit_f:audio"),
        keyboards.InlineKeyboardButton(text="PDFni tahrirlash", callback_data="edit_f:pdf")
    )
    builder.row(keyboards.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm"))
    
    await callback.message.edit_text("Qaysi maydonni tahrirlamoqchisiz?", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(AdminEditBookState.field, F.data.startswith("edit_f:"))
async def select_field_to_edit(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    book_id = data.get("book_id")
    field = callback.data.split(":")[1]
    await state.update_data(field=field)
    
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    if field == "audio":
        await state.set_state(AdminEditBookState.audio)
        await state.update_data(audio_files=[])
        builder = keyboards.InlineKeyboardBuilder()
        builder.row(
            keyboards.InlineKeyboardButton(text="✅ Yakunlash", callback_data="admin_edit_audio_done"),
            keyboards.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")
        )
        await callback.message.answer(
            "Kitobning YANGI audio fayllarini yuboring (avvalgilari o'rniga o'rnatiladi):\n"
            "Mavjud barcha qismlarni yuborib bo'lgach, '✅ Yakunlash' bosing.",
            reply_markup=builder.as_markup()
        )
    elif field == "pdf":
        await state.set_state(AdminEditBookState.pdf)
        await callback.message.answer(
            "YANGI PDF faylini yuboring (ixtiyoriy):",
            reply_markup=keyboards.get_cancel_keyboard()
        )
    elif field == "cover":
        await state.set_state(AdminEditBookState.cover)
        await callback.message.answer(
            "Kitobning YANGI muqova rasmini (photo) yuboring:",
            reply_markup=keyboards.get_cancel_keyboard()
        )
    elif field == "category":
        await state.set_state(AdminEditBookState.category)
        book = database.books.get(book_id, {})
        current_cats = book.get("categories", [])
        await state.update_data(selected_categories=current_cats)
        kb = keyboards.get_multi_category_selector(database.categories, current_cats, "admin_edit_cat")
        await callback.message.answer("Kitobning yangi janrlarini tanlang va 'Tasdiqlash' bosing:", reply_markup=kb)
    else:
        await state.set_state(AdminEditBookState.value)
        if field == "keywords":
            await callback.message.answer(
                "Yangi kalit so'zlarni vergul bilan ajratib yuboring:",
                reply_markup=keyboards.get_cancel_keyboard()
            )
        else:
            await callback.message.answer(
                f"Yangi qiymatni yuboring (Maydon: {field}):",
                reply_markup=keyboards.get_cancel_keyboard()
            )
    await callback.answer()

@router.message(AdminEditBookState.audio)
async def process_edit_audio_upload(message: Message, state: FSMContext):
    file_id = None
    file_type = None
    duration = 0
    
    if message.audio:
        file_id = message.audio.file_id
        file_type = "audio"
        duration = message.audio.duration or 0
    elif message.document and message.document.mime_type and message.document.mime_type.startswith("audio/"):
        file_id = message.document.file_id
        file_type = "document"
        
    if not file_id:
        await message.answer("Iltimos, audio fayl yuboring yoki 'Yakunlash' tugmasini bosing.")
        return
        
    data = await state.get_data()
    audio_files = data.get("audio_files", [])
    audio_files.append({
        "file_id": file_id,
        "file_type": file_type,
        "duration": duration
    })
    await state.update_data(audio_files=audio_files)
    
    builder = keyboards.InlineKeyboardBuilder()
    builder.row(
        keyboards.InlineKeyboardButton(text="✅ Yakunlash", callback_data="admin_edit_audio_done"),
        keyboards.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")
    )
    await message.answer(
        f"✅ {len(audio_files)}-audio qabul qilindi. Yana yuborishingiz yoki yakunlashingiz mumkin:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(AdminEditBookState.audio, F.data == "admin_edit_audio_done")
async def process_edit_audio_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    audio_files = data.get("audio_files", [])
    
    if not audio_files:
        await callback.answer("Kamida bitta audio fayl yuboring!", show_alert=True)
        return
        
    book_id = data["book_id"]
    await state.clear()
    
    try:
        await callback.message.delete()
    except Exception:
        pass
    status_msg = await callback.message.answer("⌛ Audio fayllar saqlash kanaliga yuborilmoqda. Iltimos, kuting...")
    
    # Upload to storage channel
    uploaded_audios = []
    for idx, f in enumerate(audio_files, 1):
        try:
            if f["file_type"] == "document":
                sent_audio = await callback.bot.send_document(chat_id=STORAGE_CHANNEL_ID, document=f["file_id"])
            else:
                sent_audio = await callback.bot.send_audio(chat_id=STORAGE_CHANNEL_ID, audio=f["file_id"])
            uploaded_audios.append({
                "file_id": f["file_id"],
                "file_type": f["file_type"],
                "duration": f.get("duration", 0),
                "message_id": sent_audio.message_id
            })
        except Exception:
            pass
            
    if book_id in database.books:
        database.books[book_id]["audio_files"] = uploaded_audios
        database.books[book_id]["duration"] = sum(f.get("duration", 0) for f in uploaded_audios)
        
        # Log to storage channel
        b = database.books[book_id]
        log_text = f"#BOOK\nID: {book_id}\nTITLE: {b['title']}\nSTATUS: updated_audio"
        try:
            await callback.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=log_text)
        except Exception:
            pass
            
        await database.save_index(callback.bot)
        
    await status_msg.delete()
    await callback.message.answer("✅ Kitob audiolari muvaffaqiyatli tahrirlandi.", reply_markup=keyboards.get_admin_menu())
    await callback.answer()

@router.message(AdminEditBookState.pdf)
async def process_edit_pdf_upload(message: Message, state: FSMContext):
    if not message.document:
        await message.answer("Iltimos, hujjat formatida PDF yuboring.")
        return
        
    data = await state.get_data()
    book_id = data["book_id"]
    await state.clear()
    
    pdf_id = message.document.file_id
    
    # Upload to channel
    try:
        await message.bot.send_document(chat_id=STORAGE_CHANNEL_ID, document=pdf_id)
    except Exception:
        pass
        
    if book_id in database.books:
        database.books[book_id]["pdf_file_id"] = pdf_id
        
        b = database.books[book_id]
        log_text = f"#BOOK\nID: {book_id}\nTITLE: {b['title']}\nSTATUS: updated_pdf"
        try:
            await message.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=log_text)
        except Exception:
            pass
            
        await database.save_index(message.bot)
        
    await message.answer("✅ Kitob PDF varianti muvaffaqiyatli tahrirlandi.", reply_markup=keyboards.get_admin_menu())

@router.message(AdminEditBookState.value)
async def process_edited_value(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    
    book_id = data["book_id"]
    field = data["field"]
    val = message.text.strip()
    
    if book_id in database.books:
        if field == "description":
            database.books[book_id][field] = val.replace("\n", "\\n")
        elif field == "keywords":
            database.books[book_id][field] = [kw.strip() for kw in val.split(",") if kw.strip()]
        else:
            database.books[book_id][field] = val
            
        b = database.books[book_id]
        kws_str = ", ".join(b.get("keywords", [])) if b.get("keywords") else "yoq"
        
        log_text = (
            "#BOOK\n"
            f"ID: {book_id}\n"
            f"TITLE: {b['title']}\n"
            f"STATUS: updated_field"
        )
        try:
            await message.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=log_text)
        except Exception:
            pass
            
        await database.save_index(message.bot)
        await message.answer("✅ Kitob tahrirlandi.", reply_markup=keyboards.get_admin_menu())

# ----------------- DELETE BOOK -----------------
@router.callback_query(F.data == "admin_del_book")
async def list_delete_books(callback: CallbackQuery):
    active_books = [b for b in database.books.values() if b.get("status", "approved") == "approved"]
    if not active_books:
        await callback.answer("Bazada o'chirish uchun kitoblar mavjud emas.", show_alert=True)
        return
        
    builder = keyboards.InlineKeyboardBuilder()
    for b in active_books[:20]:
        builder.row(keyboards.InlineKeyboardButton(text=f"❌ {b['title']}", callback_data=f"del_b:{b['id']}"))
        
    await callback.message.answer("O'chirmoqchi bo'lgan kitobni tanlang:", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("del_b:"))
async def process_del_book(callback: CallbackQuery):
    book_id = callback.data.split(":")[1]
    if book_id in database.books:
        database.books[book_id]["status"] = "deleted"
        
        b = database.books[book_id]
        log_text = (
            "#BOOK\n"
            f"ID: {book_id}\n"
            f"TITLE: {b['title']}\n"
            f"STATUS: deleted"
        )
        try:
            await callback.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=log_text)
        except Exception:
            pass
            
        await database.save_index(callback.bot)
        await callback.message.edit_text("✅ Kitob o'chirildi.")
    await callback.answer()

# ----------------- GLOBAL SORTING SETTING -----------------
@router.callback_query(F.data == "admin_config_sorting")
async def start_config_sorting(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminSortingState.select)
    current = database.settings.get("books_sorting", "upload_time")
    kb = keyboards.get_admin_sorting_keyboard(current)
    await callback.message.edit_text(
        "⚙️ *Global kitoblarni tartiblash sozlamalari:*\n\n"
        "Foydalanuvchilar kitoblar ro'yxatini ko'rishganda kitoblar qaysi tartib bo'yicha chiqishini tanlang:",
        reply_markup=kb
    )
    await callback.answer()

@router.callback_query(AdminSortingState.select, F.data.startswith("set_sort:"))
async def process_set_sorting(callback: CallbackQuery, state: FSMContext):
    val = callback.data.split(":")[1]
    database.settings["books_sorting"] = val
    await database.save_index(callback.bot)
    
    # Redraw
    kb = keyboards.get_admin_sorting_keyboard(val)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await callback.answer("Global tartiblash sozlamasi yangilandi.", show_alert=True)

# ----------------- ADMIN RECOMMENDATION ACCEPT/REJECT -----------------
@router.callback_query(F.data == "admin_view_recs_pending")
async def view_pending_recommendations(callback: CallbackQuery):
    pend_recs = [r for r in database.recommendations.values() if r.get("status", "pending") == "pending"]
    if not pend_recs:
        await callback.answer("Hozircha kutilayotgan tavsiyalar yo'q.", show_alert=True)
        return
        
    for r in pend_recs[:5]:
        cat_names = []
        for c_id in r.get("categories", []):
            cat_info = database.categories.get(c_id)
            if cat_info:
                cat_names.append(cat_info["name"])
        cat_str = ", ".join(cat_names)
        
        desc_val = r.get('description') or "yo'q"
        admin_text = (
            "💡 *Kutilayotgan kitob tavsiyasi:*\n\n"
            f"• *Nomi*: {r['title']}\n"
            f"• *Muallif*: {r['author']}\n"
            f"• *Janrlar*: {cat_str}\n"
            f"• *Tavsif*: {desc_val}\n"
            f"• *Kimdan*: ID `{r['user_id']}`\n"
        )
        kb = keyboards.get_recommendation_decide_keyboard(r["id"])
        await callback.message.answer(admin_text, reply_markup=kb)
        
    await callback.answer()

@router.callback_query(F.data.startswith("rec_approve:"))
async def approve_recommendation(callback: CallbackQuery):
    rec_id = callback.data.split(":")[1]
    rec = database.recommendations.get(rec_id)
    if not rec or rec.get("status", "pending") != "pending":
        await callback.answer("Ushbu tavsiya allaqachon ko'rib chiqilgan yoki mavjud emas.", show_alert=True)
        return
        
    rec["status"] = "approved"
    
    log_rec = f"#RECOMMENDATION\nID: {rec_id}\nSTATUS: approved"
    try:
        await callback.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=log_rec)
    except Exception:
        pass
        
    book_id = str(uuid.uuid4())[:8]
    
    # Re-upload recommendation audio files to the storage channel
    audio_files = rec.get("audio_files", [])
    uploaded_audios = []
    
    for idx, f in enumerate(audio_files, 1):
        try:
            if f.get("file_type") == "document":
                sent_audio = await callback.bot.send_document(chat_id=STORAGE_CHANNEL_ID, document=f["file_id"])
            else:
                sent_audio = await callback.bot.send_audio(chat_id=STORAGE_CHANNEL_ID, audio=f["file_id"])
            
            uploaded_audios.append({
                "file_id": f["file_id"],
                "file_type": f.get("file_type", "audio"),
                "duration": f.get("duration", 0),
                "message_id": sent_audio.message_id
            })
        except Exception as e:
            logger.error(f"Error forwarding recommendation audio part {idx}: {e}")
            
    cover_file_id = rec.get("cover_file_id", "")
    if cover_file_id:
        try:
            await callback.bot.send_photo(chat_id=STORAGE_CHANNEL_ID, photo=cover_file_id)
        except Exception:
            pass
            
    pdf_file_id = rec.get("pdf_file_id", "")
    if pdf_file_id:
        try:
            await callback.bot.send_document(chat_id=STORAGE_CHANNEL_ID, document=pdf_file_id)
        except Exception:
            pass
            
    book_entry = {
        "id": book_id,
        "title": rec["title"],
        "author": rec["author"],
        "description": rec["description"].replace("\n", "\\n") if rec["description"] else "",
        "categories": rec.get("categories", []),
        "keywords": [],
        "ratings": {},
        "audio_files": uploaded_audios,
        "pdf_file_id": pdf_file_id,
        "cover_file_id": cover_file_id,
        "duration": sum(f.get("duration", 0) for f in uploaded_audios),
        "source": f"recommendation:{rec['user_id']}",
        "status": "approved",
        "created_at": datetime.now().isoformat()
    }
    
    database.books[book_id] = book_entry
    
    pdf_val = pdf_file_id if pdf_file_id else "yoq"
    cover_val = cover_file_id if cover_file_id else "yoq"
    log_text = (
        "#BOOK\n"
        f"ID: {book_id}\n"
        f"TITLE: {rec['title']}\n"
        f"AUTHOR: {rec['author']}\n"
        f"DESCRIPTION: {book_entry['description']}\n"
        f"CATEGORY: {rec['categories'][0] if rec['categories'] else 'yoq'}\n"
        f"KEYWORDS: yoq\n"
        f"AUDIO_FILE_ID: {uploaded_audios[0]['file_id'] if uploaded_audios else 'yoq'}\n"
        f"AUDIO_MESSAGE_ID: {uploaded_audios[0]['message_id'] if uploaded_audios else 'yoq'}\n"
        f"PDF_FILE_ID: {pdf_val}\n"
        f"COVER_FILE_ID: {cover_val}\n"
        f"SOURCE: recommendation\n"
        f"STATUS: approved"
    )
    try:
        await callback.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=log_text)
    except Exception:
        pass
        
    await database.save_index(callback.bot)
    
    user_id = rec["user_id"]
    try:
        await callback.bot.send_message(
            chat_id=user_id,
            text=f"🎉 Tabriklaymiz! Siz tavsiya qilgan *'{rec['title']}'* kitobi adminlar tomonidan ma'qullandi va botga qo'shildi! Rahmat!"
        )
    except Exception:
        pass
        
    await callback.message.edit_text(
        f"✅ *Tavsiya ma'qullandi!*\nKitob nomi: {rec['title']}\nTavsiya qiluvchi ID: `{user_id}`"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("rec_reject:"))
async def reject_recommendation(callback: CallbackQuery):
    rec_id = callback.data.split(":")[1]
    rec = database.recommendations.get(rec_id)
    if not rec or rec.get("status", "pending") != "pending":
        await callback.answer("Ushbu tavsiya allaqachon ko'rib chiqilgan.", show_alert=True)
        return
        
    rec["status"] = "rejected"
    
    log_rec = f"#RECOMMENDATION\nID: {rec_id}\nSTATUS: rejected"
    try:
        await callback.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=log_rec)
    except Exception:
        pass
        
    await database.save_index(callback.bot)
    
    user_id = rec["user_id"]
    try:
        await callback.bot.send_message(
            chat_id=user_id,
            text=f"Afsuski, siz tavsiya qilgan *'{rec['title']}'* kitobi adminlar tomonidan rad etildi."
        )
    except Exception:
        pass
        
    await callback.message.edit_text(
        f"❌ *Tavsiya rad etildi.*\nKitob nomi: {rec['title']}\nTavsiya qiluvchi ID: `{user_id}`"
    )
    await callback.answer()

# ----------------- BROADCASTING -----------------
class BroadcastForm(StatesGroup):
    text = State()
    photo = State()
    audio = State()

@router.callback_query(F.data == "bc_text")
async def start_bc_text(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BroadcastForm.text)
    await callback.message.answer("📝 Tarqatiladigan xabar matnini yuboring:", reply_markup=keyboards.get_cancel_keyboard())
    await callback.answer()

@router.message(BroadcastForm.text)
async def process_bc_text(message: Message, state: FSMContext):
    await state.clear()
    text = message.text
    
    status_msg = await message.answer("📢 Tarqatilmoqda, kuting...")
    success = 0
    fail = 0
    
    for user_id in database.users.keys():
        try:
            await message.bot.send_message(chat_id=user_id, text=text)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1
            
    await status_msg.delete()
    await message.answer(
        f"📢 *Xabar tarqatish yakunlandi:*\n\n"
        f"✅ Muvaffaqiyatli: {success} ta\n"
        f"❌ Muammo yuz berdi: {fail} ta",
        reply_markup=keyboards.get_admin_menu()
    )

@router.callback_query(F.data == "bc_photo")
async def start_bc_photo(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BroadcastForm.photo)
    await callback.message.answer("🖼️ Tarqatiladigan rasmni yuboring va unga izoh yozing:", reply_markup=keyboards.get_cancel_keyboard())
    await callback.answer()

@router.message(BroadcastForm.photo)
async def process_bc_photo(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer("Iltimos, rasm yuboring.")
        return
        
    await state.clear()
    photo_id = message.photo[-1].file_id
    caption = message.caption or ""
    
    status_msg = await message.answer("📢 Rasm tarqatilmoqda, kuting...")
    success = 0
    fail = 0
    
    for user_id in database.users.keys():
        try:
            await message.bot.send_photo(chat_id=user_id, photo=photo_id, caption=caption)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1
            
    await status_msg.delete()
    await message.answer(
        f"📢 *Rasm tarqatish yakunlandi:*\n\n"
        f"✅ Muvaffaqiyatli: {success} ta\n"
        f"❌ Muammo yuz berdi: {fail} ta",
        reply_markup=keyboards.get_admin_menu()
    )

@router.callback_query(F.data == "bc_audio")
async def start_bc_audio(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BroadcastForm.audio)
    await callback.message.answer("🎧 Tarqatiladigan audio faylni yuboring va unga izoh (matn) yozing:", reply_markup=keyboards.get_cancel_keyboard())
    await callback.answer()

@router.message(BroadcastForm.audio)
async def process_bc_audio(message: Message, state: FSMContext):
    if not message.audio:
        await message.answer("Iltimos, audio fayl yuboring.")
        return
        
    await state.clear()
    audio_id = message.audio.file_id
    caption = message.caption or ""
    
    status_msg = await message.answer("📢 Audio tarqatilmoqda, kuting...")
    success = 0
    fail = 0
    
    for user_id in database.users.keys():
        try:
            await message.bot.send_audio(chat_id=user_id, audio=audio_id, caption=caption)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail += 1
            
    await status_msg.delete()
    await message.answer(
        f"📢 *Audio tarqatish yakunlandi:*\n\n"
        f"✅ Muvaffaqiyatli: {success} ta\n"
        f"❌ Muammo yuz berdi: {fail} ta",
        reply_markup=keyboards.get_admin_menu()
    )

# ----------------- MANDATORY SUBSCRIPTION SETTINGS -----------------
@router.callback_query(F.data == "admin_toggle_sub")
async def toggle_subscription(callback: CallbackQuery):
    enabled = not database.settings.get("mandatory_subscription", False)
    database.settings["mandatory_subscription"] = enabled
    
    log_text = f"#SETTINGS\nMANDATORY_SUBSCRIPTION: {'ON' if enabled else 'OFF'}"
    try:
        await callback.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=log_text)
    except Exception:
        pass
        
    await database.save_index(callback.bot)
    await callback.message.edit_reply_markup(reply_markup=keyboards.get_subscription_manage_keyboard(enabled))
    await callback.answer("Majburiy obuna holati o'zgartirildi.")

@router.callback_query(F.data == "admin_list_sub_channels")
async def list_required_channels(callback: CallbackQuery):
    if not database.required_channels:
        await callback.message.answer("Hozircha a'zo bo'lish majburiy bo'lgan kanallar yo'q.")
        await callback.answer()
        return
        
    text_list = []
    for ch_id, ch_info in database.required_channels.items():
        text_list.append(f"• *{ch_info['title']}* (ID: {ch_id})\n  Link: {ch_info['url']}")
        
    text = "📢 *Majburiy kanallar ro'yxati:*\n\n" + "\n\n".join(text_list)
    await callback.message.answer(text)
    await callback.answer()

@router.callback_query(F.data == "admin_add_sub_channel")
async def start_add_sub_channel(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.add_required_channel_id)
    await callback.message.answer(
        "Kanal ID raqamini kiriting (masalan, `-100123456789`):\n"
        "Eslatma: bot bu kanalda admin bo'lishi shart!",
        reply_markup=keyboards.get_cancel_keyboard()
    )
    await callback.answer()

@router.message(AdminState.add_required_channel_id)
async def process_add_sub_channel_id(message: Message, state: FSMContext):
    try:
        ch_id = int(message.text.strip())
    except ValueError:
        await message.answer("Xato format! Kanal ID raqam bo'lishi kerak.", reply_markup=keyboards.get_admin_menu())
        await state.clear()
        return
        
    try:
        member = await message.bot.get_chat_member(chat_id=ch_id, user_id=message.bot.id)
        if member.status not in ["administrator", "creator"]:
            await message.answer("⚠️ Diqqat! Bot bu kanalda administrator emas! Avval botni kanalda admin qiling va qayta urinib ko'ring.", reply_markup=keyboards.get_admin_menu())
            await state.clear()
            return
    except Exception as e:
        await message.answer(f"⚠️ Kanalni tekshirib bo'lmadi. Bot kanalda admin qilinganligiga ishonch hosil qiling.\nXatolik: {e}", reply_markup=keyboards.get_admin_menu())
        await state.clear()
        return
        
    await state.update_data(id=ch_id)
    await state.set_state(AdminState.add_required_channel_title)
    await message.answer("Kanal nomini (Title) kiriting (masalan: `Mening Kanalim`):", reply_markup=keyboards.get_cancel_keyboard())

@router.message(AdminState.add_required_channel_title)
async def process_add_sub_channel_title(message: Message, state: FSMContext):
    title = message.text.strip()
    await state.update_data(title=title)
    await state.set_state(AdminState.add_required_channel_url)
    await message.answer("Kanalga taklif havolasini kiriting (Invite Link, masalan: `https://t.me/...`):", reply_markup=keyboards.get_cancel_keyboard())

@router.message(AdminState.add_required_channel_url)
async def process_add_sub_channel_url(message: Message, state: FSMContext):
    url = message.text.strip()
    data = await state.get_data()
    await state.clear()
    
    ch_id = data["id"]
    title = data["title"]
    
    database.required_channels[ch_id] = {
        "id": ch_id,
        "title": title,
        "url": url,
        "status": "active"
    }
    
    log_text = (
        "#REQUIRED_CHANNEL\n"
        f"ID: {ch_id}\n"
        f"TITLE: {title}\n"
        f"URL: {url}\n"
        f"STATUS: active"
    )
    try:
        await message.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=log_text)
    except Exception:
        pass
        
    await database.save_index(message.bot)
    
    await message.answer(
        f"✅ Kanal majburiy obuna ro'yxatiga qo'shildi:\n*{title}* (ID: {ch_id})",
        reply_markup=keyboards.get_admin_menu()
    )

@router.callback_query(F.data == "admin_del_sub_channel")
async def list_del_sub_channel(callback: CallbackQuery):
    if not database.required_channels:
        await callback.answer("O'chirish uchun kanallar mavjud emas.", show_alert=True)
        return
        
    builder = keyboards.InlineKeyboardBuilder()
    for ch_id, ch_info in database.required_channels.items():
        builder.row(keyboards.InlineKeyboardButton(text=f"❌ {ch_info['title']}", callback_data=f"del_ch:{ch_id}"))
        
    await callback.message.answer("O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("del_ch:"))
async def process_del_sub_channel(callback: CallbackQuery):
    ch_id = int(callback.data.split(":")[1])
    if ch_id in database.required_channels:
        del_info = database.required_channels.pop(ch_id)
        
        log_text = (
            "#REQUIRED_CHANNEL\n"
            f"ID: {ch_id}\n"
            f"TITLE: {del_info['title']}\n"
            f"STATUS: removed"
        )
        try:
            await callback.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=log_text)
        except Exception:
            pass
            
        await database.save_index(callback.bot)
        await callback.message.edit_text("✅ Kanal majburiy ro'yxatdan o'chirildi.")
    await callback.answer()


# ----------------- EXPANDED EDITING HANDLERS -----------------
@router.message(AdminEditBookState.cover)
async def process_edit_cover(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer("Iltimos, rasm formatida muqova yuboring.")
        return
        
    data = await state.get_data()
    book_id = data["book_id"]
    await state.clear()
    
    cover_id = message.photo[-1].file_id
    
    try:
        await message.bot.send_photo(chat_id=STORAGE_CHANNEL_ID, photo=cover_id)
    except Exception:
        pass
        
    if book_id in database.books:
        database.books[book_id]["cover_file_id"] = cover_id
        
        b = database.books[book_id]
        log_text = f"#BOOK\nID: {book_id}\nTITLE: {b['title']}\nSTATUS: updated_cover"
        try:
            await message.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=log_text)
        except Exception:
            pass
            
        await database.save_index(message.bot)
        
    await message.answer("✅ Kitob muqova rasmi muvaffaqiyatli tahrirlandi.", reply_markup=keyboards.get_admin_menu())

@router.callback_query(AdminEditBookState.category, F.data.startswith("admin_edit_cat_toggle:"))
async def process_edit_category_toggle(callback: CallbackQuery, state: FSMContext):
    cat_id = callback.data.split(":")[1]
    data = await state.get_data()
    selected = data.get("selected_categories", [])
    
    if cat_id in selected:
        selected.remove(cat_id)
    else:
        selected.append(cat_id)
        
    await state.update_data(selected_categories=selected)
    
    kb = keyboards.get_multi_category_selector(database.categories, selected, "admin_edit_cat")
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await callback.answer()

@router.callback_query(AdminEditBookState.category, F.data == "admin_edit_cat_confirm")
async def process_edit_category_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_categories", [])
    book_id = data["book_id"]
    await state.clear()
    
    if not selected:
        await callback.answer("Kamida bitta janr tanlash majburiy!", show_alert=True)
        return
        
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    if book_id in database.books:
        database.books[book_id]["categories"] = selected
        
        b = database.books[book_id]
        log_text = f"#BOOK\nID: {book_id}\nTITLE: {b['title']}\nSTATUS: updated_categories"
        try:
            await callback.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=log_text)
        except Exception:
            pass
            
        await database.save_index(callback.bot)
        
    await callback.message.answer("✅ Kitob janrlari muvaffaqiyatli tahrirlandi.", reply_markup=keyboards.get_admin_menu())
    await callback.answer()


# ----------------- AI SWITCHBOARD & FEATURE TOGGLE -----------------
@router.callback_query(F.data == "admin_toggle_ai")
async def process_toggle_ai(callback: CallbackQuery):
    enabled = not database.settings.get("ai_enabled", True)
    database.settings["ai_enabled"] = enabled
    await database.save_index(callback.bot)
    
    provider = database.settings.get("ai_provider", "GEMINI").upper()
    analytics = database.settings.get("ai_analytics", {})
    total_in = analytics.get("total_input_tokens", 0)
    total_out = analytics.get("total_output_tokens", 0)
    cost = analytics.get("total_cost", 0.0)
    
    dashboard_text = (
        "🤖 *AI Tizimi Sozlamalari:*\n\n"
        f"• *AI Holati (Kill-Switch)*: {'Yoqilgan (ON) 🟢' if enabled else 'O\'chirilgan (OFF) 🔴'}\n"
        f"• *Provayder*: *{provider}*\n\n"
        f"📊 *Tokenlar Sarfi Analytics:*\n"
        f"• Kiruvchi (Input) tokenlar: {total_in:,} ta\n"
        f"• Chiquvchi (Output) tokenlar: {total_out:,} ta\n"
        f"• Taxminiy hisoblangan sarf: *${cost:.6f}*"
    )
    
    await callback.message.edit_text(dashboard_text, reply_markup=keyboards.get_ai_settings_keyboard(enabled, provider))
    await callback.answer("AI holati o'zgartirildi.")

@router.callback_query(F.data == "admin_toggle_ai_provider")
async def process_toggle_ai_provider(callback: CallbackQuery):
    current = database.settings.get("ai_provider", "GEMINI").upper()
    if current == "GEMINI":
        new_provider = "DEEPSEEK"
    elif current == "DEEPSEEK":
        new_provider = "GROQ"
    else:
        new_provider = "GEMINI"
    database.settings["ai_provider"] = new_provider
    await database.save_index(callback.bot)
    
    enabled = database.settings.get("ai_enabled", True)
    analytics = database.settings.get("ai_analytics", {})
    total_in = analytics.get("total_input_tokens", 0)
    total_out = analytics.get("total_output_tokens", 0)
    cost = analytics.get("total_cost", 0.0)
    
    dashboard_text = (
        "🤖 *AI Tizimi Sozlamalari:*\n\n"
        f"• *AI Holati (Kill-Switch)*: {'Yoqilgan (ON) 🟢' if enabled else 'O\'chirilgan (OFF) 🔴'}\n"
        f"• *Provayder*: *{new_provider}*\n\n"
        f"📊 *Tokenlar Sarfi Analytics:*\n"
        f"• Kiruvchi (Input) tokenlar: {total_in:,} ta\n"
        f"• Chiquvchi (Output) tokenlar: {total_out:,} ta\n"
        f"• Taxminiy hisoblangan sarf: *${cost:.6f}*"
    )
    
    await callback.message.edit_text(dashboard_text, reply_markup=keyboards.get_ai_settings_keyboard(enabled, new_provider))
    await callback.answer(f"AI provayderi {new_provider} ga o'zgartirildi.")

@router.callback_query(F.data == "admin_clear_ai_stats")
async def process_clear_ai_stats(callback: CallbackQuery):
    database.settings["ai_analytics"] = {
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cost": 0.0
    }
    await database.save_index(callback.bot)
    
    enabled = database.settings.get("ai_enabled", True)
    provider = database.settings.get("ai_provider", "GEMINI").upper()
    
    dashboard_text = (
        "🤖 *AI Tizimi Sozlamalari:*\n\n"
        f"• *AI Holati (Kill-Switch)*: {'Yoqilgan (ON) 🟢' if enabled else 'O\'chirilgan (OFF) 🔴'}\n"
        f"• *Provayder*: *{provider}*\n\n"
        f"📊 *Tokenlar Sarfi Analytics:*\n"
        f"• Kiruvchi (Input) tokenlar: 0 ta\n"
        f"• Chiquvchi (Output) tokenlar: 0 ta\n"
        f"• Taxminiy hisoblangan sarf: *$0.000000*"
    )
    
    await callback.message.edit_text(dashboard_text, reply_markup=keyboards.get_ai_settings_keyboard(enabled, provider))
    await callback.answer("Statistika tozalandi.")


# ----------------- DYNAMIC MENU SETTINGS HANDLERS -----------------
@router.callback_query(F.data == "menu_edit_labels")
async def menu_edit_labels_list(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminMenuSettingsState.edit_label_select)
    menu_cfg = getattr(database, "menu_settings", {})
    labels = menu_cfg.get("labels", {})
    
    builder = keyboards.InlineKeyboardBuilder()
    for btn_key, label in labels.items():
        builder.row(keyboards.InlineKeyboardButton(text=f"{btn_key} -> {label}", callback_data=f"menu_lbl_sel:{btn_key}"))
    builder.row(keyboards.InlineKeyboardButton(text="🔙 Orqaga", callback_data="cancel_fsm"))
    
    await callback.message.edit_text("Nomini o'zgartirmoqchi bo'lgan tugmani tanlang:", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(AdminMenuSettingsState.edit_label_select, F.data.startswith("menu_lbl_sel:"))
async def menu_edit_label_select(callback: CallbackQuery, state: FSMContext):
    btn_key = callback.data.split(":")[1]
    await state.update_data(btn_key=btn_key)
    await state.set_state(AdminMenuSettingsState.edit_label_value)
    
    await callback.message.answer(
        f"Tugma kaliti: `{btn_key}`\n"
        "Ushbu tugma uchun yangi yozuvni (label) yuboring:",
        reply_markup=keyboards.get_cancel_keyboard()
    )
    await callback.answer()

@router.message(AdminMenuSettingsState.edit_label_value)
async def process_menu_label_value(message: Message, state: FSMContext):
    new_label = message.text.strip()
    if not new_label:
        await message.answer("Tugma nomi bo'sh bo'lishi mumkin emas.")
        return
        
    data = await state.get_data()
    btn_key = data["btn_key"]
    await state.clear()
    
    menu_cfg = getattr(database, "menu_settings", {})
    labels = menu_cfg.setdefault("labels", {})
    labels[btn_key] = new_label
    
    await database.save_index(message.bot)
    await message.answer(
        f"✅ Tugma nomi muvaffaqiyatli yangilandi:\n`{btn_key}` -> `{new_label}`",
        reply_markup=keyboards.get_admin_menu()
    )

@router.callback_query(F.data == "menu_edit_rows")
async def menu_edit_rows_list(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminMenuSettingsState.edit_row)
    menu_cfg = getattr(database, "menu_settings", {})
    rows = menu_cfg.get("rows", [])
    
    builder = keyboards.InlineKeyboardBuilder()
    for idx, r in enumerate(rows):
        row_items = ", ".join(r)
        builder.row(keyboards.InlineKeyboardButton(text=f"Qator {idx+1}: {row_items}", callback_data=f"menu_row_sel:{idx}"))
    builder.row(keyboards.InlineKeyboardButton(text="🔙 Orqaga", callback_data="cancel_fsm"))
    
    await callback.message.edit_text("Tahrirlamoqchi bo'lgan qatorni tanlang:", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(AdminMenuSettingsState.edit_row, F.data.startswith("menu_row_sel:"))
async def menu_edit_row_select(callback: CallbackQuery, state: FSMContext):
    row_idx = int(callback.data.split(":")[1])
    await state.update_data(row_idx=row_idx)
    
    menu_cfg = getattr(database, "menu_settings", {})
    rows = menu_cfg.get("rows", [])
    current_row = rows[row_idx]
    
    valid_keys = [
        "📚 Kitoblar", "📚 Kutubxonam", "🕒 Tarix", 
        "🧠 AI Tavsiya", "💬 AI Companion", 
        "💡 Kitob Tavsiya Qilish", "🔍 Qidiruv", 
        "👤 Profil", "ℹ️ Yordam"
    ]
    
    valid_keys_str = "\n".join([f"• `{k}`" for k in valid_keys])
    
    await callback.message.answer(
        f"Siz {row_idx+1}-qatorni tahrirlashni tanladingiz.\n"
        f"Joriy tugmalar: `{', '.join(current_row)}`\n\n"
        "Yangi tugmalar ro'yxatini vergul bilan ajratib yuboring.\n"
        "Faqat quyidagi kalit so'zlardan foydalanishingiz mumkin:\n"
        f"{valid_keys_str}\n\n"
        "Masalan: `📚 Kutubxonam, 🕒 Tarix`",
        reply_markup=keyboards.get_cancel_keyboard()
    )
    await callback.answer()

@router.message(AdminMenuSettingsState.edit_row)
async def process_menu_row_value(message: Message, state: FSMContext):
    text = message.text.strip()
    data = await state.get_data()
    row_idx = data["row_idx"]
    
    valid_keys = [
        "📚 Kitoblar", "📚 Kutubxonam", "🕒 Tarix", 
        "🧠 AI Tavsiya", "💬 AI Companion", 
        "💡 Kitob Tavsiya Qilish", "🔍 Qidiruv", 
        "👤 Profil", "ℹ️ Yordam"
    ]
    
    # Parse items
    items = [item.strip() for item in text.split(",") if item.strip()]
    
    # Validate items
    invalid = [item for item in items if item not in valid_keys]
    if invalid:
        await message.answer(
            f"❌ Noto'g'ri kalit so'zlar kiritildi: `{', '.join(invalid)}`.\n"
            "Iltimos, faqat ruxsat berilgan tugmalarni kiriting."
        )
        return
        
    await state.clear()
    
    menu_cfg = getattr(database, "menu_settings", {})
    rows = menu_cfg.setdefault("rows", [])
    
    if len(items) == 0:
        # Delete row if empty
        rows.pop(row_idx)
        action_msg = "o'chirildi"
    else:
        rows[row_idx] = items
        action_msg = "yangilandi"
        
    await database.save_index(message.bot)
    await message.answer(f"✅ {row_idx+1}-qator muvaffaqiyatli {action_msg}!", reply_markup=keyboards.get_admin_menu())
