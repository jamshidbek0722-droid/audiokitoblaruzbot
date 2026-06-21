import uuid
import logging
import json
import io
import asyncio
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import OWNER_ID, STORAGE_CHANNEL_ID
import database
import keyboards
from states import AdminState, AdminBookForm

logger = logging.getLogger(__name__)
router = Router()

# Global cancel handler for Admin FSM
@router.message(F.text == "❌ Bekor qilish")
@router.message(Command("cancel"))
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
    "🔄 Bazani yangilash",
    "📥 Bazani eksport qilish"
]

def is_admin_filter(message: Message) -> bool:
    return database.is_admin(message.from_user.id)

# Middleware check inside admin router: Ensure only admins can trigger these
@router.message(is_admin_filter, F.text.in_(ADMIN_MENU_BUTTONS))
async def admin_check_message(message: Message, state: FSMContext):
        
    # Check if message is a menu button
    text = message.text
    if text == "⚙️ Admin Panel":
        await message.answer("⚙️ **Admin Paneliga xush kelibsiz.**", reply_markup=keyboards.get_admin_menu(), parse_mode="Markdown")
        return
        
    elif text == "🏠 Asosiy menyu":
        await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=keyboards.get_main_menu(True))
        return
        
    elif text == "📊 Statistika":
        # Calculate stats
        users_count = len(database.users)
        cats_count = len([c for c in database.categories.values() if c.get("status", "active") == "active"])
        
        active_books = [b for b in database.books.values() if b.get("status", "approved") == "approved"]
        books_count = len(active_books)
        audio_books = len([b for b in active_books if b.get("audio_file_id")])
        pdf_books = len([b for b in active_books if b.get("pdf_file_id")])
        
        stats_text = (
            "📊 **Bot Statistikasi:**\n\n"
            f"• **Foydalanuvchilar soni**: {users_count} ta\n"
            f"• **Faol janrlar soni**: {cats_count} ta\n"
            f"• **Faol kitoblar soni**: {books_count} ta\n"
            f"• **Audio kitoblar**: {audio_books} ta\n"
            f"• **PDF kitoblar**: {pdf_books} ta\n"
        )
        await message.answer(stats_text)
        return
        
    elif text == "📁 Janrlarni boshqarish":
        await message.answer("📁 **Janrlarni boshqarish bo'limi:**", reply_markup=keyboards.get_category_manage_keyboard())
        return
        
    elif text == "📚 Kitoblarni boshqarish":
        await message.answer("📚 **Kitoblarni boshqarish bo'limi:**", reply_markup=keyboards.get_book_manage_keyboard())
        return
        
    elif text == "💡 Tavsiyalar":
        # Show pending recommendations count
        pend_recs = [r for r in database.recommendations.values() if r.get("status", "pending") == "pending"]
        await message.answer(
            f"💡 **Tavsiyalar boshqaruvi**\n\nKutilayotgan tavsiyalar soni: {len(pend_recs)} ta",
            reply_markup=keyboards.get_admin_recommendations_keyboard()
        )
        return
        
    elif text == "📢 Xabar yuborish":
        await message.answer("Xabar turini tanlang:", reply_markup=keyboards.get_broadcast_types_keyboard())
        return
        
    elif text == "👥 Adminlar":
        await message.answer("👥 **Adminlarni boshqarish bo'limi:**", reply_markup=keyboards.get_admin_manage_keyboard())
        return
        
    elif text == "🔐 Majburiy obuna":
        enabled = database.settings.get("mandatory_subscription", False)
        await message.answer("🔐 **Majburiy obunani boshqarish:**", reply_markup=keyboards.get_subscription_manage_keyboard(enabled))
        return
        
    elif text == "🔄 Bazani yangilash":
        # Rebuild/reload database index from storage channel
        await message.answer("🔄 Baza indeksi yangilanmoqda...")
        await database.load_index(message.bot)
        await message.answer("✅ Baza indeksi muvaffaqiyatli yuklandi.")
        return
        
    elif text == "📥 Bazani eksport qilish":
        # Send json index file to admin
        data = {
            "admins": list(database.admins),
            "categories": database.categories,
            "books": database.books,
            "users": {str(k): v for k, v in database.users.items()},
            "recommendations": database.recommendations,
            "settings": database.settings,
            "required_channels": {str(k): v for k, v in database.required_channels.items()}
        }
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        input_file = BufferedInputFile(bytes(json_str, "utf-8"), filename="database_backup.json")
        await message.answer_document(document=input_file, caption="📥 Bot ma'lumotlar bazasi zaxira nusxasi (JSON).")
        return

# ----------------- ADMINS MANAGEMENT -----------------
@router.callback_query(F.data == "admin_list_all")
async def list_admins(callback: CallbackQuery):
    admin_list = []
    for adm in database.admins:
        name = "Owner" if adm == OWNER_ID else f"Admin (ID: {adm})"
        admin_list.append(f"• {name}")
    text = "👥 **Tizim adminlari ro'yxati:**\n\n" + "\n".join(admin_list)
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
    
    # Save to storage channel
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
        
        # Save to storage channel
        admin_log = f"#ADMIN\nID: {del_id}\nSTATUS: removed"
        await callback.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=admin_log)
        
        await database.save_index(callback.bot)
        await callback.message.edit_text(f"✅ Admin o'chirildi (ID: {del_id}).")
    await callback.answer()

# ----------------- CATEGORY MANAGEMENT -----------------
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
    
    # Save structured block to channel
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
        
        # Save structured block to channel
        log_text = f"#CATEGORY\nID: {cat_id}\nNAME: {database.categories[cat_id]['name']}\nSTATUS: removed"
        await callback.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=log_text)
        
        await database.save_index(callback.bot)
        await callback.message.edit_text("✅ Janr o'chirildi (Mavjud kitoblar saqlanib qoladi).")
    await callback.answer()

# ----------------- ADMIN BOOK CREATION FLOW (REQUIRED AUDIO) -----------------
@router.callback_query(F.data == "admin_add_book")
async def start_add_book(callback: CallbackQuery, state: FSMContext):
    # Verify categories exist first
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
        
    active_cats = {k: v for k, v in database.categories.items() if v.get("status", "active") == "active"}
    kb = keyboards.get_categories_inline(active_cats, "admin_book_cat")
    
    await state.set_state(AdminBookForm.category)
    await message.answer("📁 Janrni tanlang:", reply_markup=kb)
    await message.answer("Tugmalardan foydalaning. Bekor qilish uchun '❌ Bekor qilish' deb yozing.")

@router.callback_query(AdminBookForm.category, F.data.startswith("admin_book_cat:"))
async def process_book_category(callback: CallbackQuery, state: FSMContext):
    cat_id = callback.data.split(":")[1]
    await state.update_data(category=cat_id)
    await state.set_state(AdminBookForm.audio)
    
    await callback.message.delete()
    await callback.message.answer(
        "🎧 Kitobning audio faylini yuboring (MAJBURIY - audio yoki hujjat formatida):",
        reply_markup=keyboards.get_cancel_keyboard() # Do NOT offer Skip button here
    )
    await callback.answer()

@router.message(AdminBookForm.audio)
async def process_book_audio(message: Message, state: FSMContext):
    # Verify we actually received an audio or document
    file_id = None
    file_type = None
    
    if message.audio:
        file_id = message.audio.file_id
        file_type = "audio"
    elif message.document:
        # Document can be used for files
        file_id = message.document.file_id
        file_type = "document"
        
    if not file_id:
        # Crucial validation! Block if missing
        await message.answer(
            "⚠️ Xatolik! Kitob yaratish uchun audio fayl yuborish majburiydir!\n"
            "Iltimos, audio yoki hujjat yuboring. Bekor qilish uchun '❌ Bekor qilish' tugmasini bosing."
        )
        return
        
    await state.update_data(audio_file_id=file_id, audio_file_type=file_type)
    await state.set_state(AdminBookForm.cover)
    await message.answer(
        "🖼️ Kitob muqovasi uchun rasm yuboring (ixtiyoriy):",
        reply_markup=keyboards.get_skip_cancel_keyboard()
    )

@router.message(AdminBookForm.cover)
async def process_book_cover(message: Message, state: FSMContext):
    if message.text == "⏭️ O'tkazib yuborish":
        await state.update_data(cover_file_id="")
    elif message.photo:
        await state.update_data(cover_file_id=message.photo[-1].file_id)
    else:
        await message.answer("Iltimos, rasm yuboring yoki 'O'tkazib yuborish' tugmasini bosing.")
        return
        
    await state.set_state(AdminBookForm.pdf)
    await message.answer(
        "📄 Kitobning PDF faylini yuboring (ixtiyoriy):",
        reply_markup=keyboards.get_skip_cancel_keyboard()
    )

@router.message(AdminBookForm.pdf)
async def process_book_pdf(message: Message, state: FSMContext):
    if message.text == "⏭️ O'tkazib yuborish":
        await state.update_data(pdf_file_id="")
    elif message.document:
        await state.update_data(pdf_file_id=message.document.file_id)
    else:
        await message.answer("Iltimos, hujjat yuboring yoki 'O'tkazib yuborish' tugmasini bosing.")
        return
        
    # Preview confirmation
    data = await state.get_data()
    cat_name = database.categories.get(data["category"], {}).get("name", "Noma'lum")
    
    desc_val = data.get('description') or "yo'q"
    cover_status = "bor" if data.get('cover_file_id') else "yo'q"
    pdf_status = "bor" if data.get('pdf_file_id') else "yo'q"
    summary = (
        "📚 **Kitob tafsilotlari:**\n\n"
        f"• **Nomi**: {data['title']}\n"
        f"• **Muallif**: {data['author']}\n"
        f"• **Janr**: {cat_name}\n"
        f"• **Tavsif**: {desc_val}\n"
        f"• **Audio**: bor (yuborilgan)\n"
        f"• **Muqova**: {cover_status}\n"
        f"• **PDF**: {pdf_status}\n\n"
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
        await callback.message.delete()
        await callback.message.answer("Kitob qo'shish bekor qilindi.", reply_markup=keyboards.get_admin_menu())
        await callback.answer()
        return
        
    # Yes - save
    data = await state.get_data()
    await state.clear()
    
    await callback.message.delete()
    status_msg = await callback.message.answer("⌛ Fayllar saqlash kanaliga yuklanmoqda. Iltimos, kuting...")
    
    bot = callback.bot
    book_id = str(uuid.uuid4())[:8]
    
    # 1. Forward/Upload audio file to channel
    audio_msg_id = None
    try:
        if data["audio_file_type"] == "document":
            sent_audio = await bot.send_document(chat_id=STORAGE_CHANNEL_ID, document=data["audio_file_id"])
        else:
            sent_audio = await bot.send_audio(chat_id=STORAGE_CHANNEL_ID, audio=data["audio_file_id"])
        audio_msg_id = sent_audio.message_id
    except Exception as e:
        logger.error(f"Error uploading audio to channel: {e}")
        
    # 2. Upload cover if present
    if data["cover_file_id"]:
        try:
            await bot.send_photo(chat_id=STORAGE_CHANNEL_ID, photo=data["cover_file_id"])
        except Exception as e:
            logger.error(f"Error uploading cover to channel: {e}")
            
    # 3. Upload PDF if present
    if data["pdf_file_id"]:
        try:
            await bot.send_document(chat_id=STORAGE_CHANNEL_ID, document=data["pdf_file_id"])
        except Exception as e:
            logger.error(f"Error uploading PDF to channel: {e}")
            
    # Save metadata
    book_entry = {
        "id": book_id,
        "title": data["title"],
        "author": data["author"],
        "description": data["description"].replace("\n", "\\n") if data["description"] else "",
        "category": data["category"],
        "audio_file_id": data["audio_file_id"],
        "audio_file_type": data["audio_file_type"],
        "audio_message_id": audio_msg_id,
        "pdf_file_id": data["pdf_file_id"],
        "cover_file_id": data["cover_file_id"],
        "source": "admin",
        "status": "approved",
        "created_at": datetime.now().isoformat()
    }
    
    database.books[book_id] = book_entry
    
    # Post structured message to channel history
    audio_msg_val = audio_msg_id if audio_msg_id else "noma'lum"
    pdf_val = data['pdf_file_id'] if data['pdf_file_id'] else "yoq"
    cover_val = data['cover_file_id'] if data['cover_file_id'] else "yoq"
    log_text = (
        "#BOOK\n"
        f"ID: {book_id}\n"
        f"TITLE: {data['title']}\n"
        f"AUTHOR: {data['author']}\n"
        f"DESCRIPTION: {book_entry['description']}\n"
        f"CATEGORY: {data['category']}\n"
        f"AUDIO_FILE_ID: {data['audio_file_id']}\n"
        f"AUDIO_MESSAGE_ID: {audio_msg_val}\n"
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
        text=f"✅ Kitob muvaffaqiyatli yaratildi: **{data['title']}**",
        reply_markup=keyboards.get_admin_menu()
    )
    await callback.answer()

# ----------------- EDIT BOOK -----------------
# Simply request title changes or delete and add.
# We will implement a quick book edit of title/author.
class AdminEditBookState(StatesGroup):
    select = State()
    field = State()
    value = State()

@router.callback_query(F.data == "admin_edit_book")
async def start_edit_book(callback: CallbackQuery, state: FSMContext):
    active_books = [b for b in database.books.values() if b.get("status", "approved") == "approved"]
    if not active_books:
        await callback.answer("Tizimda tahrirlash uchun kitoblar mavjud emas.", show_alert=True)
        return
        
    builder = keyboards.InlineKeyboardBuilder()
    for b in active_books[:20]: # Limit edit choices list
        builder.row(keyboards.InlineKeyboardButton(text=f"{b['title']} - {b['author']}", callback_data=f"edit_b_sel:{b['id']}"))
        
    await state.set_state(AdminEditBookState.select)
    await callback.message.answer("Tahrirlamoqchi bo'lgan kitobni tanlang:", reply_markup=builder.as_markup())
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
    builder.row(keyboards.InlineKeyboardButton(text="Tavsifi (Description)", callback_data="edit_f:description"))
    
    await callback.message.edit_text("Qaysi maydonni tahrirlamoqchisiz?", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(AdminEditBookState.field, F.data.startswith("edit_f:"))
async def select_field_to_edit(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split(":")[1]
    await state.update_data(field=field)
    await state.set_state(AdminEditBookState.value)
    
    await callback.message.delete()
    await callback.message.answer(
        f"Yangi qiymatni yuboring (Maydon: {field}):",
        reply_markup=keyboards.get_cancel_keyboard()
    )
    await callback.answer()

@router.message(AdminEditBookState.value)
async def process_edited_value(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    
    book_id = data["book_id"]
    field = data["field"]
    val = message.text.strip()
    
    if book_id in database.books:
        # Edit in-memory
        if field == "description":
            database.books[book_id][field] = val.replace("\n", "\\n")
        else:
            database.books[book_id][field] = val
            
        b = database.books[book_id]
        
        # Log to channel
        log_text = (
            "#BOOK\n"
            f"ID: {book_id}\n"
            f"TITLE: {b['title']}\n"
            f"AUTHOR: {b['author']}\n"
            f"DESCRIPTION: {b['description']}\n"
            f"CATEGORY: {b['category']}\n"
            f"AUDIO_FILE_ID: {b['audio_file_id']}\n"
            f"AUDIO_MESSAGE_ID: {b['audio_message_id']}\n"
            f"PDF_FILE_ID: {b['pdf_file_id'] or 'yoq'}\n"
            f"COVER_FILE_ID: {b['cover_file_id'] or 'yoq'}\n"
            f"SOURCE: {b.get('source', 'admin')}\n"
            f"STATUS: approved"
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
    for b in active_books[:20]: # Show list
        builder.row(keyboards.InlineKeyboardButton(text=f"❌ {b['title']}", callback_data=f"del_b:{b['id']}"))
        
    await callback.message.answer("O'chirmoqchi bo'lgan kitobni tanlang:", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data.startswith("del_b:"))
async def process_del_book(callback: CallbackQuery):
    book_id = callback.data.split(":")[1]
    if book_id in database.books:
        database.books[book_id]["status"] = "deleted"
        
        # Log to channel
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

# ----------------- ADMIN RECOMMENDATION ACCEPT/REJECT -----------------
@router.callback_query(F.data == "admin_view_recs_pending")
async def view_pending_recommendations(callback: CallbackQuery):
    pend_recs = [r for r in database.recommendations.values() if r.get("status", "pending") == "pending"]
    if not pend_recs:
        await callback.answer("Hozircha kutilayotgan tavsiyalar yo'q.", show_alert=True)
        return
        
    for r in pend_recs[:5]: # Show first 5 pending
        cat_name = database.categories.get(r["category"], {}).get("name", "Noma'lum")
        desc_val = r.get('description') or "yo'q"
        admin_text = (
            "💡 **Kutilayotgan kitob tavsiyasi:**\n\n"
            f"• **Nomi**: {r['title']}\n"
            f"• **Muallif**: {r['author']}\n"
            f"• **Janr**: {cat_name}\n"
            f"• **Tavsif**: {desc_val}\n"
            f"• **Kimdan**: ID `{r['user_id']}`\n"
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
    
    # Save recommendation status update to channel history
    log_rec = f"#RECOMMENDATION\nID: {rec_id}\nSTATUS: approved"
    try:
        await callback.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=log_rec)
    except Exception:
        pass
        
    # Convert recommendation into a visible Book
    book_id = str(uuid.uuid4())[:8]
    
    # Check if recommendation has audio
    # If audio is present in the recommendation, we use it.
    audio_file_id = rec.get("audio_file_id", "")
    audio_file_type = rec.get("audio_file_type", "audio")
    
    audio_msg_id = None
    if audio_file_id:
        try:
            # Upload it to storage channel
            if audio_file_type == "document":
                sent_audio = await callback.bot.send_document(chat_id=STORAGE_CHANNEL_ID, document=audio_file_id)
            else:
                sent_audio = await callback.bot.send_audio(chat_id=STORAGE_CHANNEL_ID, audio=audio_file_id)
            audio_msg_id = sent_audio.message_id
        except Exception as e:
            logger.error(f"Error uploading recommendation audio: {e}")
            
    # Cover photo upload to channel
    cover_file_id = rec.get("cover_file_id", "")
    if cover_file_id:
        try:
            await callback.bot.send_photo(chat_id=STORAGE_CHANNEL_ID, photo=cover_file_id)
        except Exception:
            pass
            
    # PDF upload to channel
    pdf_file_id = rec.get("pdf_file_id", "")
    if pdf_file_id:
        try:
            await callback.bot.send_document(chat_id=STORAGE_CHANNEL_ID, document=pdf_file_id)
        except Exception:
            pass
            
    # Create Book entry
    book_entry = {
        "id": book_id,
        "title": rec["title"],
        "author": rec["author"],
        "description": rec["description"].replace("\n", "\\n") if rec["description"] else "",
        "category": rec["category"],
        "audio_file_id": audio_file_id,
        "audio_file_type": audio_file_type,
        "audio_message_id": audio_msg_id,
        "pdf_file_id": pdf_file_id,
        "cover_file_id": cover_file_id,
        "source": f"recommendation:{rec['user_id']}",
        "status": "approved",
        "created_at": datetime.now().isoformat()
    }
    
    # Save book to database
    database.books[book_id] = book_entry
    
    # Post structured message to channel history
    audio_msg_val = audio_msg_id if audio_msg_id else "noma'lum"
    pdf_val = pdf_file_id if pdf_file_id else "yoq"
    cover_val = cover_file_id if cover_file_id else "yoq"
    log_text = (
        "#BOOK\n"
        f"ID: {book_id}\n"
        f"TITLE: {rec['title']}\n"
        f"AUTHOR: {rec['author']}\n"
        f"DESCRIPTION: {book_entry['description']}\n"
        f"CATEGORY: {rec['category']}\n"
        f"AUDIO_FILE_ID: {audio_file_id}\n"
        f"AUDIO_MESSAGE_ID: {audio_msg_val}\n"
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
    
    # Notify user who suggested it
    user_id = rec["user_id"]
    try:
        await callback.bot.send_message(
            chat_id=user_id,
            text=f"🎉 Tabriklaymiz! Siz tavsiya qilgan **'{rec['title']}'** kitobi adminlar tomonidan ma'qullandi va botga qo'shildi! Rahmat!"
        )
    except Exception:
        pass
        
    # Edit admin message
    await callback.message.edit_text(
        f"✅ **Tavsiya ma'qullandi!**\nKitob nomi: {rec['title']}\nTavsiya qiluvchi ID: `{user_id}`"
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
    
    # Save recommendation status update to channel
    log_rec = f"#RECOMMENDATION\nID: {rec_id}\nSTATUS: rejected"
    try:
        await callback.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=log_rec)
    except Exception:
        pass
        
    await database.save_index(callback.bot)
    
    # Notify user
    user_id = rec["user_id"]
    try:
        await callback.bot.send_message(
            chat_id=user_id,
            text=f"Afsuski, siz tavsiya qilgan **'{rec['title']}'** kitobi adminlar tomonidan rad etildi."
        )
    except Exception:
        pass
        
    await callback.message.edit_text(
        f"❌ **Tavsiya rad etildi.**\nKitob nomi: {rec['title']}\nTavsiya qiluvchi ID: `{user_id}`"
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
            await asyncio.sleep(0.05) # Prevent flood wait
        except Exception:
            fail += 1
            
    await status_msg.delete()
    await message.answer(
        f"📢 **Xabar tarqatish yakunlandi:**\n\n"
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
        f"📢 **Rasm tarqatish yakunlandi:**\n\n"
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
        f"📢 **Audio tarqatish yakunlandi:**\n\n"
        f"✅ Muvaffaqiyatli: {success} ta\n"
        f"❌ Muammo yuz berdi: {fail} ta",
        reply_markup=keyboards.get_admin_menu()
    )

# ----------------- MANDATORY SUBSCRIPTION SETTINGS -----------------
@router.callback_query(F.data == "admin_toggle_sub")
async def toggle_subscription(callback: CallbackQuery):
    enabled = not database.settings.get("mandatory_subscription", False)
    database.settings["mandatory_subscription"] = enabled
    
    # Log to channel history
    log_text = f"#SETTINGS\nMANDATORY_SUBSCRIPTION: {'ON' if enabled else 'OFF'}"
    try:
        await callback.bot.send_message(chat_id=STORAGE_CHANNEL_ID, text=log_text)
    except Exception:
        pass
        
    await database.save_index(callback.bot)
    
    # Edit markup
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
        text_list.append(f"• **{ch_info['title']}** (ID: {ch_id})\n  Link: {ch_info['url']}")
        
    text = "📢 **Majburiy kanallar ro'yxati:**\n\n" + "\n\n".join(text_list)
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
        
    # Verify bot is admin in this channel
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
    
    # Log to storage channel
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
        f"✅ Kanal majburiy obuna ro'yxatiga qo'shildi:\n**{title}** (ID: {ch_id})",
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
        
        # Log to storage channel
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
