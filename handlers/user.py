import uuid
import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import OWNER_ID, STORAGE_CHANNEL_ID
import database
from states import UserState, UserRecForm
import keyboards

logger = logging.getLogger(__name__)
router = Router()

# Global cancel handler for User FSM
@router.message(F.text == "❌ Bekor qilish")
@router.message(Command("cancel"))
async def cancel_user_fsm(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    await message.answer(
        "Amaliyot bekor qilindi.",
        reply_markup=keyboards.get_main_menu(database.is_admin(user_id))
    )

# ----------------- PROFIL -----------------
@router.message(F.text == "👤 Profil")
async def view_profile(message: Message):
    user_id = message.from_user.id
    user_data = database.users.get(user_id)
    if not user_data:
        await message.answer("Siz haqingizda ma'lumot topilmadi. Qayta boshlash uchun /start bosing.")
        return
        
    favs_count = len(user_data.get("favorites", []))
    history_count = len(user_data.get("history", []))
    joined_date = user_data.get("joined_at", "Noma'lum")
    if joined_date != "Noma'lum":
        try:
            dt = datetime.fromisoformat(joined_date)
            joined_date = dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass
            
    full_name = user_data.get("full_name") or "Noma'lum"
    username = user_data.get("username") or "yo'q"
    profile_text = (
        "👤 **Sizning profilingiz:**\n\n"
        f"• **Ism**: {full_name}\n"
        f"• **Telegram ID**: `{user_id}`\n"
        f"• **Username**: @{username}\n"
        f"• **Sevimlilar**: {favs_count} ta kitob\n"
        f"• **Tarix (tinglangan)**: {history_count} ta kitob\n"
        f"• **Ro'yxatdan o'tilgan**: {joined_date}\n"
    )
    await message.answer(profile_text)

# ----------------- SEVIMLILAR -----------------
@router.message(F.text == "⭐ Sevimlilar")
async def view_favorites(message: Message):
    user_id = message.from_user.id
    user_data = database.users.get(user_id, {})
    fav_ids = user_data.get("favorites", [])
    
    # Filter only active approved books
    fav_books = []
    for bid in fav_ids:
        b = database.books.get(bid)
        if b and b.get("status", "approved") == "approved":
            fav_books.append(b)
            
    if not fav_books:
        await message.answer("Sevimli kitoblaringiz ro'yxati hozircha bo'sh. Kitoblar tafsilotidan 'Sevimli qo'shish' tugmasini bosing.")
        return
        
    builder = keyboards.InlineKeyboardBuilder()
    for b in fav_books:
        builder.row(keyboards.InlineKeyboardButton(text=f"⭐ {b['title']} - {b['author']}", callback_data=f"view_book:{b['id']}"))
    await message.answer("⭐ **Sevimli kitoblaringiz:**", reply_markup=builder.as_markup())

# ----------------- TARIX -----------------
@router.message(F.text == "🕒 Tarix")
async def view_history(message: Message):
    user_id = message.from_user.id
    user_data = database.users.get(user_id, {})
    hist_ids = user_data.get("history", [])
    
    hist_books = []
    for bid in hist_ids:
        b = database.books.get(bid)
        if b and b.get("status", "approved") == "approved":
            hist_books.append(b)
            
    if not hist_books:
        await message.answer("Siz hali biron bir kitob tinglamadingiz. Kitob tinglaganingizdan so'ng bu yerda paydo bo'ladi.")
        return
        
    builder = keyboards.InlineKeyboardBuilder()
    for b in hist_books:
        builder.row(keyboards.InlineKeyboardButton(text=f"🕒 {b['title']} - {b['author']}", callback_data=f"view_book:{b['id']}"))
    await message.answer("🕒 **Oxirgi tinglagan kitoblaringiz:**", reply_markup=builder.as_markup())

# ----------------- JANRLAR / CATEGORIES -----------------
@router.message(F.text == "📚 Janrlar")
async def view_categories_menu(message: Message):
    active_cats = {k: v for k, v in database.categories.items() if v.get("status", "active") == "active"}
    if not active_cats:
        await message.answer("Hozircha hech qanday janr mavjud emas.")
        return
        
    kb = keyboards.get_categories_inline(active_cats, "user_view_cat")
    await message.answer("📚 **Janrlardan birini tanlang:**", reply_markup=kb)

@router.callback_query(F.data.startswith("user_view_cat:"))
async def view_category_books(callback: CallbackQuery):
    cat_id = callback.data.split(":")[1]
    cat_info = database.categories.get(cat_id)
    if not cat_info:
        await callback.answer("Janr topilmadi.", show_alert=True)
        return
        
    # Get books in this category
    cat_books = [b for b in database.books.values() if b.get("category") == cat_id and b.get("status", "approved") == "approved"]
    
    if not cat_books:
        await callback.message.answer(f"📁 **{cat_info['name']}** janrida hozircha kitoblar mavjud emas.")
        await callback.answer()
        return
        
    # Show page 1
    await show_books_page(callback, cat_id, cat_books, 1)

async def show_books_page(callback: CallbackQuery, cat_id: str, books_list: list, page: int):
    PAGE_SIZE = 5
    total = len(books_list)
    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    
    if page < 1: page = 1
    if page > pages: page = pages
    
    start_idx = (page - 1) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_books = books_list[start_idx:end_idx]
    
    cat_name = database.categories.get(cat_id, {}).get("name", "Janr")
    text = f"📁 **Janr: {cat_name}**\n\nQuyidagi kitoblardan birini tanlang:"
    
    builder = keyboards.InlineKeyboardBuilder()
    for b in page_books:
        builder.row(keyboards.InlineKeyboardButton(text=f"📖 {b['title']} - {b['author']}", callback_data=f"view_book:{b['id']}"))
        
    # Add pagination controls
    pag_buttons = []
    if page > 1:
        pag_buttons.append(keyboards.InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"cat_page:{cat_id}:{page - 1}"))
    pag_buttons.append(keyboards.InlineKeyboardButton(text=f"{page}/{pages}", callback_data="none"))
    if page < pages:
        pag_buttons.append(keyboards.InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"cat_page:{cat_id}:{page + 1}"))
    
    builder.row(*pag_buttons)
    builder.row(keyboards.InlineKeyboardButton(text="🔙 Janrlarga qaytish", callback_data="back_to_cats"))
    
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except Exception:
        # Fallback if content did not change or message edit is not possible
        await callback.message.answer(text, reply_markup=builder.as_markup())
        
    await callback.answer()

@router.callback_query(F.data.startswith("cat_page:"))
async def handle_category_page(callback: CallbackQuery):
    parts = callback.data.split(":")
    cat_id = parts[1]
    page = int(parts[2])
    cat_books = [b for b in database.books.values() if b.get("category") == cat_id and b.get("status", "approved") == "approved"]
    await show_books_page(callback, cat_id, cat_books, page)

@router.callback_query(F.data == "back_to_cats")
async def back_to_categories_callback(callback: CallbackQuery):
    active_cats = {k: v for k, v in database.categories.items() if v.get("status", "active") == "active"}
    kb = keyboards.get_categories_inline(active_cats, "user_view_cat")
    await callback.message.edit_text("📚 **Janrlardan birini tanlang:**", reply_markup=kb)
    await callback.answer()

# ----------------- QIDIRUV / SEARCH -----------------
@router.message(F.text == "🔍 Qidiruv")
async def start_search(message: Message, state: FSMContext):
    await state.set_state(UserState.search)
    await message.answer("🔍 Qidirmoqchi bo'lgan kitobingiz nomi yoki muallifini kiriting:", reply_markup=keyboards.get_cancel_keyboard())

@router.message(UserState.search)
async def process_search_query(message: Message, state: FSMContext):
    query = message.text.strip()
    if not query:
        await message.answer("Iltimos, qidiruv so'zini kiriting.")
        return
        
    # Search logic
    found_books = []
    for b in database.books.values():
        if b.get("status", "approved") == "approved":
            title = b.get("title", "").lower()
            author = b.get("author", "").lower()
            if query.lower() in title or query.lower() in author:
                found_books.append(b)
                
    await state.clear()
    
    if not found_books:
        user_id = message.from_user.id
        await message.answer(
            f"Afsuski, '{query}' so'rovi bo'yicha hech qanday kitob topilmadi. Boshqa so'z bilan urinib ko'ring.",
            reply_markup=keyboards.get_main_menu(database.is_admin(user_id))
        )
        return
        
    # Show search results
    builder = keyboards.InlineKeyboardBuilder()
    for b in found_books[:10]: # Limit search results list in chat
        builder.row(keyboards.InlineKeyboardButton(text=f"📖 {b['title']} - {b['author']}", callback_data=f"view_book:{b['id']}"))
    
    user_id = message.from_user.id
    await message.answer(
        f"🔍 **'{query}' bo'yicha topilgan kitoblar:**",
        reply_markup=builder.as_markup()
    )
    # Restore main menu keyboard
    await message.answer("Qidiruv tugallandi.", reply_markup=keyboards.get_main_menu(database.is_admin(user_id)))

# ----------------- VIEW BOOK DETAILS -----------------
@router.callback_query(F.data.startswith("view_book:"))
async def view_book_details(callback: CallbackQuery):
    book_id = callback.data.split(":")[1]
    book = database.books.get(book_id)
    if not book or book.get("status", "approved") != "approved":
        await callback.answer("Kitob topilmadi yoki o'chirilgan.", show_alert=True)
        return
        
    user_id = callback.from_user.id
    user_data = database.users.get(user_id, {})
    is_fav = book_id in user_data.get("favorites", [])
    has_pdf = bool(book.get("pdf_file_id"))
    
    cat_name = database.categories.get(book["category"], {}).get("name", "Noma'lum")
    desc = book.get("description", "").replace("\\n", "\n")
    if not desc:
        desc = "Tavsif mavjud emas."
        
    details_text = (
        f"📖 **{book['title']}**\n"
        f"✍️ **Muallif**: {book['author']}\n"
        f"📁 **Janr**: {cat_name}\n\n"
        f"📝 **Tavsif**:\n{desc}"
    )
    
    kb = keyboards.get_book_details_keyboard(book_id, is_fav, has_pdf)
    
    # Try sending with cover photo
    if book.get("cover_file_id"):
        try:
            # Delete details message if it was text to keep chat clean
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_photo(photo=book["cover_file_id"], caption=details_text, reply_markup=kb)
    else:
        try:
            await callback.message.edit_text(details_text, reply_markup=kb)
        except Exception:
            await callback.message.answer(details_text, reply_markup=kb)
            
    await callback.answer()

@router.callback_query(F.data == "back_to_books")
async def back_to_books_handler(callback: CallbackQuery):
    # Just redirect them back to Janrlar (Categories) selection
    active_cats = {k: v for k, v in database.categories.items() if v.get("status", "active") == "active"}
    kb = keyboards.get_categories_inline(active_cats, "user_view_cat")
    
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    await callback.message.answer("📚 **Janrlardan birini tanlang:**", reply_markup=kb)
    await callback.answer()

# ----------------- TINGLASH & YUKLAB OLISH -----------------
@router.callback_query(F.data.startswith("play_book:"))
async def play_book_audio(callback: CallbackQuery):
    book_id = callback.data.split(":")[1]
    book = database.books.get(book_id)
    if not book:
        await callback.answer("Kitob topilmadi.", show_alert=True)
        return
        
    user_id = callback.from_user.id
    
    # Update History
    user_data = database.users.setdefault(user_id, {
        "id": user_id,
        "favorites": [],
        "history": [],
        "joined_at": datetime.now().isoformat()
    })
    
    history_list = user_data.setdefault("history", [])
    if book_id in history_list:
        history_list.remove(book_id)
    history_list.insert(0, book_id)
    user_data["history"] = history_list[:10] # Keep last 10 unique
    
    await database.save_index(callback.bot)
    
    await callback.answer("Audio yuborilmoqda...")
    
    caption = f"🎧 **Eshitilmoqda**: {book['title']}\n✍️ **Muallif**: {book['author']}"
    file_id = book.get("audio_file_id")
    file_type = book.get("audio_file_type", "audio")
    
    try:
        if file_type == "document":
            await callback.message.answer_document(document=file_id, caption=caption)
        else:
            await callback.message.answer_audio(audio=file_id, caption=caption)
    except Exception as e:
        logger.error(f"Error sending audio to user: {e}")
        # Try fallback as document/audio
        try:
            if file_type == "document":
                await callback.message.answer_audio(audio=file_id, caption=caption)
            else:
                await callback.message.answer_document(document=file_id, caption=caption)
        except Exception as fallback_err:
            await callback.message.answer("⚠️ Audio faylni yuborishda xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.")

@router.callback_query(F.data.startswith("download_audio:"))
async def download_book_audio(callback: CallbackQuery):
    book_id = callback.data.split(":")[1]
    book = database.books.get(book_id)
    if not book:
        await callback.answer("Kitob topilmadi.", show_alert=True)
        return
        
    await callback.answer("Audio yuklab olish uchun yuborilmoqda...")
    file_id = book.get("audio_file_id")
    
    caption = f"📥 **Yuklab olindi**: {book['title']} - {book['author']}"
    try:
        # Send as document to force download
        await callback.message.answer_document(document=file_id, caption=caption)
    except Exception:
        # Try as audio
        try:
            await callback.message.answer_audio(audio=file_id, caption=caption)
        except Exception:
            await callback.message.answer("⚠️ Faylni yuborishda xatolik yuz berdi.")

@router.callback_query(F.data.startswith("download_pdf:"))
async def download_book_pdf(callback: CallbackQuery):
    book_id = callback.data.split(":")[1]
    book = database.books.get(book_id)
    if not book or not book.get("pdf_file_id"):
        await callback.answer("Ushbu kitobning PDF fayli mavjud emas.", show_alert=True)
        return
        
    await callback.answer("PDF yuklab olinmoqda...")
    caption = f"📄 **PDF**: {book['title']} - {book['author']}"
    try:
        await callback.message.answer_document(document=book["pdf_file_id"], caption=caption)
    except Exception:
        await callback.message.answer("⚠️ PDF faylini yuborishda xatolik yuz berdi.")

# ----------------- FAVORITES TOGGLE -----------------
@router.callback_query(F.data.startswith("toggle_fav:"))
async def toggle_favorite(callback: CallbackQuery):
    book_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    user_data = database.users.setdefault(user_id, {
        "id": user_id,
        "favorites": [],
        "history": [],
        "joined_at": datetime.now().isoformat()
    })
    
    favs = user_data.setdefault("favorites", [])
    if book_id in favs:
        favs.remove(book_id)
        await callback.answer("Kitob sevimlilardan o'chirildi.", show_alert=False)
    else:
        favs.append(book_id)
        await callback.answer("Kitob sevimlilarga qo'shildi.", show_alert=False)
        
    user_data["favorites"] = favs
    await database.save_index(callback.bot)
    
    # Refresh keyboard
    has_pdf = bool(database.books.get(book_id, {}).get("pdf_file_id"))
    is_now_fav = book_id in favs
    kb = keyboards.get_book_details_keyboard(book_id, is_now_fav, has_pdf)
    
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass

# ----------------- BOOK RECOMMENDATION SYSTEM -----------------
@router.message(F.text == "💡 Kitob Tavsiya Qilish")
async def start_recommendation(message: Message, state: FSMContext):
    await state.set_state(UserRecForm.title)
    await message.answer(
        "💡 **Kitob tavsiya qilish bo'limi:**\n\nKitob nomini kiriting:",
        reply_markup=keyboards.get_cancel_keyboard()
    )

@router.message(UserRecForm.title)
async def process_rec_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(UserRecForm.author)
    await message.answer("Muallif ismini kiriting:", reply_markup=keyboards.get_cancel_keyboard())

@router.message(UserRecForm.author)
async def process_rec_author(message: Message, state: FSMContext):
    await state.update_data(author=message.text.strip())
    await state.set_state(UserRecForm.description)
    await message.answer(
        "Kitob tavsifini kiriting (ixtiyoriy):",
        reply_markup=keyboards.get_skip_cancel_keyboard()
    )

@router.message(UserRecForm.description)
async def process_rec_description(message: Message, state: FSMContext):
    text = message.text.strip()
    if text == "⏭️ O'tkazib yuborish":
        await state.update_data(description="")
    else:
        await state.update_data(description=text)
        
    # Get active categories to choose from
    active_cats = {k: v for k, v in database.categories.items() if v.get("status", "active") == "active"}
    if not active_cats:
        await state.clear()
        user_id = message.from_user.id
        await message.answer(
            "Tizimda janrlar mavjud emas. Hozircha tavsiya yuborib bo'lmaydi.",
            reply_markup=keyboards.get_main_menu(database.is_admin(user_id))
        )
        return
        
    await state.set_state(UserRecForm.category)
    kb = keyboards.get_categories_inline(active_cats, "rec_cat")
    # Send a temporary keyboard to cancel FSM
    await message.answer("Kitob qaysi janrga tegishli? Quyidagilardan tanlang:", reply_markup=kb)
    # Also remind user they can click "Cancel" text message or type "/cancel"
    await message.answer("Tavsiyani bekor qilish uchun '❌ Bekor qilish' deb yozishingiz mumkin.")

@router.callback_query(F.data.startswith("rec_cat:"))
async def process_rec_category(callback: CallbackQuery, state: FSMContext):
    cat_id = callback.data.split(":")[1]
    await state.update_data(category=cat_id)
    await state.set_state(UserRecForm.audio)
    
    await callback.message.delete()
    await callback.message.answer(
        "Kitobning audio faylini yuboring (ixtiyoriy, audio yoki hujjat formatida):",
        reply_markup=keyboards.get_skip_cancel_keyboard()
    )
    await callback.answer()

@router.message(UserRecForm.audio)
async def process_rec_audio(message: Message, state: FSMContext):
    if message.text == "⏭️ O'tkazib yuborish":
        await state.update_data(audio_file_id="", audio_file_type="")
    elif message.audio:
        await state.update_data(audio_file_id=message.audio.file_id, audio_file_type="audio")
    elif message.document:
        await state.update_data(audio_file_id=message.document.file_id, audio_file_type="document")
    else:
        await message.answer("Iltimos, audio fayl yuboring yoki 'O'tkazib yuborish' tugmasini bosing.")
        return
        
    await state.set_state(UserRecForm.cover)
    await message.answer(
        "Kitob muqovasini yuboring (rasm, ixtiyoriy):",
        reply_markup=keyboards.get_skip_cancel_keyboard()
    )

@router.message(UserRecForm.cover)
async def process_rec_cover(message: Message, state: FSMContext):
    if message.text == "⏭️ O'tkazib yuborish":
        await state.update_data(cover_file_id="")
    elif message.photo:
        # Telegram sends multiple dimensions, choose the largest one
        await state.update_data(cover_file_id=message.photo[-1].file_id)
    else:
        await message.answer("Iltimos, rasm yuboring yoki 'O'tkazib yuborish' tugmasini bosing.")
        return
        
    await state.set_state(UserRecForm.pdf)
    await message.answer(
        "Kitobning PDF variantini yuboring (hujjat, ixtiyoriy):",
        reply_markup=keyboards.get_skip_cancel_keyboard()
    )

@router.message(UserRecForm.pdf)
async def process_rec_pdf(message: Message, state: FSMContext):
    if message.text == "⏭️ O'tkazib yuborish":
        await state.update_data(pdf_file_id="")
    elif message.document:
        await state.update_data(pdf_file_id=message.document.file_id)
    else:
        await message.answer("Iltimos, hujjat yuboring yoki 'O'tkazib yuborish' tugmasini bosing.")
        return
        
    # Confirmation stage
    data = await state.get_data()
    cat_name = database.categories.get(data["category"], {}).get("name", "Noma'lum")
    
    desc_val = data.get('description') or "yo'q"
    audio_status = "bor" if data.get('audio_file_id') else "yo'q"
    cover_status = "bor" if data.get('cover_file_id') else "yo'q"
    pdf_status = "bor" if data.get('pdf_file_id') else "yo'q"
    
    summary = (
        "📖 **Kitob tavsiyasi tayyor:**\n\n"
        f"• **Nomi**: {data['title']}\n"
        f"• **Muallif**: {data['author']}\n"
        f"• **Janr**: {cat_name}\n"
        f"• **Tavsif**: {desc_val}\n"
        f"• **Audio**: {audio_status}\n"
        f"• **Muqova**: {cover_status}\n"
        f"• **PDF**: {pdf_status}\n\n"
        "Tavsiyani tasdiqlaysizmi?"
    )
    
    await state.set_state(UserRecForm.confirm)
    await message.answer(summary, reply_markup=keyboards.get_confirmation_keyboard())
    # Restore cancel/save keyboard just in case they text
    await message.answer("Tugmalardan foydalaning.", reply_markup=keyboards.get_cancel_keyboard())

@router.callback_query(UserRecForm.confirm, F.data.startswith("confirm_"))
async def process_rec_confirmation(callback: CallbackQuery, state: FSMContext):
    decision = callback.data.split("_")[1]
    user_id = callback.from_user.id
    
    if decision == "no":
        await state.clear()
        await callback.message.delete()
        await callback.message.answer(
            "Tavsiya bekor qilindi.",
            reply_markup=keyboards.get_main_menu(database.is_admin(user_id))
        )
        await callback.answer()
        return
        
    # Yes
    data = await state.get_data()
    await state.clear()
    
    rec_id = str(uuid.uuid4())[:8]
    
    # Save recommendation
    rec_data = {
        "id": rec_id,
        "user_id": user_id,
        "title": data["title"],
        "author": data["author"],
        "description": data["description"],
        "category": data["category"],
        "audio_file_id": data["audio_file_id"],
        "audio_file_type": data.get("audio_file_type", ""),
        "cover_file_id": data["cover_file_id"],
        "pdf_file_id": data["pdf_file_id"],
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    
    database.recommendations[rec_id] = rec_data
    await database.save_index(callback.bot)
    
    await callback.message.delete()
    await callback.message.answer(
        "✅ Rahmat! Sizning tavsiyangiz adminlarga ko'rib chiqish uchun yuborildi.",
        reply_markup=keyboards.get_main_menu(database.is_admin(user_id))
    )
    await callback.answer()
    
    # Notify admins
    cat_name = database.categories.get(data["category"], {}).get("name", "Noma'lum")
    desc_val = data.get('description') or "yo'q"
    user_name_val = callback.from_user.username or "username_yoq"
    admin_text = (
        "💡 **Yangi kitob tavsiyasi keldi:**\n\n"
        f"• **Nomi**: {data['title']}\n"
        f"• **Muallif**: {data['author']}\n"
        f"• **Janr**: {cat_name}\n"
        f"• **Tavsif**: {desc_val}\n"
        f"• **Kimdan**: ID `{user_id}` (@{user_name_val})\n\n"
        "Ma'qullaysizmi?"
    )
    
    # Send to Owner and admins
    kb = keyboards.get_recommendation_decide_keyboard(rec_id)
    for admin_id in database.admins:
        try:
            await callback.bot.send_message(chat_id=admin_id, text=admin_text, reply_markup=kb)
        except Exception as e:
            logger.warning(f"Could not notify admin {admin_id}: {e}")
            
    if OWNER_ID not in database.admins:
        try:
            await callback.bot.send_message(chat_id=OWNER_ID, text=admin_text, reply_markup=kb)
        except Exception as e:
            logger.warning(f"Could not notify owner: {e}")
