import uuid
import logging
import random
import urllib.parse
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext

from config import OWNER_ID, STORAGE_CHANNEL_ID
import database
from states import UserState, UserRecForm, UserProfileForm, UserContactForm, UserAIRecommendationState, UserAIChatState
import keyboards
import ai_service

logger = logging.getLogger(__name__)
router = Router()

def sort_books(books_list):
    sorting = database.settings.get("books_sorting", "upload_time")
    if sorting == "random":
        shuffled = list(books_list)
        random.shuffle(shuffled)
        return shuffled
    elif sorting == "rating":
        def get_avg_rating(b):
            ratings = b.get("ratings", {})
            if not ratings:
                return 0.0
            return sum(ratings.values()) / len(ratings)
        return sorted(books_list, key=get_avg_rating, reverse=True)
    elif sorting == "title":
        return sorted(books_list, key=lambda x: x.get("title", "").lower())
    elif sorting == "author":
        return sorted(books_list, key=lambda x: x.get("author", "").lower())
    else: # upload_time
        return sorted(books_list, key=lambda x: x.get("created_at", ""), reverse=True)

def format_duration(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours} soat, {minutes} daqiqa"
    return f"{minutes} daqiqa"

# Global cancel handlers
@router.message(StateFilter("*"), F.text == "❌ Bekor qilish")
@router.message(StateFilter("*"), Command("cancel"))
async def cancel_user_fsm(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    await message.answer(
        "Amaliyot bekor qilindi.",
        reply_markup=keyboards.get_main_menu(database.is_admin(user_id))
    )

@router.callback_query(StateFilter("*"), F.data == "cancel_fsm")
async def cancel_fsm_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        "Amaliyot bekor qilindi.",
        reply_markup=keyboards.get_main_menu(database.is_admin(user_id))
    )
    await callback.answer()

# ----------------- COMMAND SHORTCUTS -----------------
@router.message(Command("books"))
async def books_cmd_shortcut(message: Message):
    await view_categories_menu(message)

@router.message(Command("search"))
async def search_cmd_shortcut(message: Message, state: FSMContext):
    await start_search(message, state)

@router.message(Command("contact"))
async def contact_cmd_shortcut(message: Message, state: FSMContext):
    await state.set_state(UserContactForm.message)
    await message.answer(
        "✍️ Adminlarga yubormoqchi bo'lgan xabaringiz yoki taklifingizni yozib yuboring:",
        reply_markup=keyboards.get_cancel_keyboard()
    )

@router.message(Command("rate"))
async def rate_cmd_shortcut(message: Message):
    await message.answer(
        "⭐ Kitobni baholash uchun kitobning audiosini tinglab bo'lgach, tagidagi 'Baholash' tugmasidan foydalaning."
    )

@router.message(Command("share"))
async def share_cmd_shortcut(message: Message):
    bot_info = await message.bot.get_me()
    share_link = f"https://t.me/{bot_info.username}"
    share_text = (
        "📚 *Uzbek Audio Book Botini do'stlaringizga ulashing!*\n\n"
        "Eng sara o'zbek tilidagi audiokitoblar va PDF nashrlar jamlangan bot:\n"
        f"{share_link}"
    )
    await message.answer(share_text)

# ----------------- KUTUBXONAM -----------------
@router.message(database.is_menu_button("📚 Kutubxonam"))
async def view_library_menu(message: Message):
    user_id = message.from_user.id
    user_data = database.users.get(user_id, {})
    
    favs_count = len(user_data.get("favorites", []))
    stats = user_data.get("listening_stats", {"total_seconds": 0, "completed_books": []})
    completed_count = len(stats.get("completed_books", []))
    total_hours_str = format_duration(stats.get("total_seconds", 0))
    
    lib_text = (
        "📚 *Sizning Shaxsiy Kutubxonangiz:*\n\n"
        f"• *Kutubxonadagi kitoblar*: {favs_count} ta\n"
        f"• *Eshitib tugatilgan kitoblar*: {completed_count} ta\n"
        f"• *Jami eshitilgan vaqt*: {total_hours_str}\n\n"
        "Quyidagi bo'limlardan birini tanlang:"
    )
    await message.answer(lib_text, reply_markup=keyboards.get_library_keyboard())

@router.callback_query(F.data == "lib_my_books")
async def view_lib_books(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = database.users.get(user_id, {})
    fav_ids = user_data.get("favorites", [])
    
    fav_books = []
    for bid in fav_ids:
        b = database.books.get(bid)
        if b and b.get("status", "approved") == "approved":
            fav_books.append(b)
            
    if not fav_books:
        await callback.answer("Kutubxonangiz hozircha bo'sh.", show_alert=True)
        return
        
    builder = keyboards.InlineKeyboardBuilder()
    for b in fav_books:
        builder.row(keyboards.InlineKeyboardButton(text=f"📖 {b['title']}", callback_data=f"view_book:{b['id']}:lib_fav"))
    builder.row(keyboards.InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_lib"))
    
    await callback.message.edit_text("📚 *Kutubxonangizdagi kitoblar:*", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data == "lib_history")
async def view_lib_history(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = database.users.get(user_id, {})
    hist_ids = user_data.get("history", [])
    
    hist_books = []
    for bid in hist_ids:
        b = database.books.get(bid)
        if b and b.get("status", "approved") == "approved":
            hist_books.append(b)
            
    if not hist_books:
        await callback.answer("Tarix hozircha bo'sh.", show_alert=True)
        return
        
    builder = keyboards.InlineKeyboardBuilder()
    for b in hist_books:
        builder.row(keyboards.InlineKeyboardButton(text=f"🕒 {b['title']}", callback_data=f"view_book:{b['id']}:lib_hist"))
    builder.row(keyboards.InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_lib"))
    
    await callback.message.edit_text("🕒 *Oxirgi eshitilgan kitoblar:*", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data == "lib_stats")
async def view_lib_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = database.users.get(user_id, {})
    stats = user_data.get("listening_stats", {"total_seconds": 0, "completed_books": []})
    
    total_hours_str = format_duration(stats.get("total_seconds", 0))
    completed_count = len(stats.get("completed_books", []))
    
    profile = user_data.get("profile")
    profile_status = "To'ldirilgan ✅" if profile else "To'ldirilmagan ❌"
    
    stats_text = (
        "📊 *Sizning eshitish statistikangiz:*\n\n"
        f"• *Jami eshitilgan vaqt*: {total_hours_str}\n"
        f"• *Tugatilgan kitoblar soni*: {completed_count} ta\n"
        f"• *Profil holati*: {profile_status}\n\n"
        "Profil to'ldirish uchun shaxsiy profil bo'limiga o'ting."
    )
    builder = keyboards.InlineKeyboardBuilder()
    builder.row(keyboards.InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_lib"))
    
    await callback.message.edit_text(stats_text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data == "back_to_lib")
async def back_to_library_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data = database.users.get(user_id, {})
    
    favs_count = len(user_data.get("favorites", []))
    stats = user_data.get("listening_stats", {"total_seconds": 0, "completed_books": []})
    completed_count = len(stats.get("completed_books", []))
    total_hours_str = format_duration(stats.get("total_seconds", 0))
    
    lib_text = (
        "📚 *Sizning Shaxsiy Kutubxonangiz:*\n\n"
        f"• *Kutubxonadagi kitoblar*: {favs_count} ta\n"
        f"• *Eshitib tugatilgan kitoblar*: {completed_count} ta\n"
        f"• *Jami eshitilgan vaqt*: {total_hours_str}\n\n"
        "Quyidagi bo'limlardan birini tanlang:"
    )
    await callback.message.edit_text(lib_text, reply_markup=keyboards.get_library_keyboard())
    await callback.answer()

@router.message(F.text == "🕒 Tarix")
async def view_history_cmd(message: Message):
    user_id = message.from_user.id
    user_data = database.users.get(user_id, {})
    hist_ids = user_data.get("history", [])
    
    hist_books = []
    for bid in hist_ids:
        b = database.books.get(bid)
        if b and b.get("status", "approved") == "approved":
            hist_books.append(b)
            
    if not hist_books:
        await message.answer("Siz hali biron bir kitob tinglamadingiz.")
        return
        
    builder = keyboards.InlineKeyboardBuilder()
    for b in hist_books:
        builder.row(keyboards.InlineKeyboardButton(text=f"🕒 {b['title']} - {b['author']}", callback_data=f"view_book:{b['id']}:lib_hist"))
    await message.answer("🕒 *Oxirgi eshitilgan kitoblar:*", reply_markup=builder.as_markup())

# ----------------- PROFIL -----------------
@router.message(database.is_menu_button("👤 Profil"))
async def view_profile(message: Message):
    user_id = message.from_user.id
    user_data = database.users.get(user_id)
    if not user_data:
        await message.answer("Siz haqingizda ma'lumot topilmadi. Qayta boshlash uchun /start bosing.")
        return
        
    favs_count = len(user_data.get("favorites", []))
    stats = user_data.get("listening_stats", {"total_seconds": 0, "completed_books": []})
    completed_count = len(stats.get("completed_books", []))
    total_hours_str = format_duration(stats.get("total_seconds", 0))
    joined_date = user_data.get("joined_at", "Noma'lum")
    if joined_date != "Noma'lum":
        try:
            dt = datetime.fromisoformat(joined_date)
            joined_date = dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass
            
    full_name = user_data.get("full_name") or "Noma'lum"
    username = user_data.get("username") or "yo'q"
    
    profile = user_data.get("profile")
    profile_details = ""
    if profile:
        profile_details = (
            f"\n*Qo'shimcha ma'lumotlar:*\n"
            f"• *Jins*: {profile.get('gender', 'Noma\'lum')}\n"
            f"• *Yosh*: {profile.get('age', 'Noma\'lum')}\n"
            f"• *Viloyat*: {profile.get('region', 'Noma\'lum')}\n"
            f"• *Qiziqishlar*: {profile.get('interests', 'Noma\'lum') or 'kiritilmagan'}\n"
        )
    else:
        profile_details = "\n⚠️ *Profilingiz to'liq emas!* Bot statistikasini yaxshilash va sizga mos kitoblar tavsiya etilishi uchun profilingizni to'ldiring.\n"
        
    profile_text = (
        "👤 *Sizning profilingiz:*\n\n"
        f"• *Ism*: {full_name}\n"
        f"• *Telegram ID*: `{user_id}`\n"
        f"• *Username*: @{username}\n"
        f"• *Kutubxonadagi kitoblar*: {favs_count} ta\n"
        f"• *Jami eshitilgan vaqt*: {total_hours_str}\n"
        f"• *Ro'yxatdan o'tilgan*: {joined_date}\n"
        f"{profile_details}"
    )
    
    kb = keyboards.get_profile_options_keyboard()
    await message.answer(profile_text, reply_markup=kb)

# ----------------- PROFILE WIZARD FLOW -----------------
@router.callback_query(F.data == "complete_profile")
async def start_profile_wizard(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserProfileForm.gender)
    await callback.message.answer(
        "🙋‍♂️ Jinsingizni tanlang:",
        reply_markup=keyboards.get_gender_keyboard()
    )
    await callback.answer()

@router.callback_query(UserProfileForm.gender, F.data.startswith("profile_gender:"))
async def process_profile_gender(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.split(":")[1]
    await state.update_data(gender=gender)
    await state.set_state(UserProfileForm.age)
    
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    await callback.message.answer(
        "Yosh kiritish:\nIltimos, yoshingizni raqamda kiriting (masalan: 23):",
        reply_markup=keyboards.get_cancel_keyboard()
    )
    await callback.answer()

@router.message(UserProfileForm.age)
async def process_profile_age(message: Message, state: FSMContext):
    try:
        age = int(message.text.strip())
        if age < 5 or age > 100:
            raise ValueError()
    except ValueError:
        await message.answer("Iltimos, yoshingizni to'g'ri raqamda kiriting (5 dan 100 gacha):")
        return
        
    await state.update_data(age=age)
    await state.set_state(UserProfileForm.region)
    
    await message.answer(
        "Yashash hududingizni (viloyat) tanlang:",
        reply_markup=keyboards.get_regions_keyboard()
    )

@router.callback_query(UserProfileForm.region, F.data.startswith("profile_region:"))
async def process_profile_region(callback: CallbackQuery, state: FSMContext):
    region = callback.data.split(":")[1]
    await state.update_data(region=region)
    await state.set_state(UserProfileForm.interests)
    
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    await callback.message.answer(
        "Qiziqadigan janrlaringiz yoki kitoblaringiz haqida yozing (ixtiyoriy, masalan: Badiiy, Tarixiy):\n"
        "Yoki 'O'tkazib yuborish' tugmasini bosing.",
        reply_markup=keyboards.get_skip_cancel_keyboard()
    )
    await callback.answer()

@router.message(UserProfileForm.interests)
async def process_profile_interests(message: Message, state: FSMContext):
    text = message.text.strip()
    interests = ""
    if text != "⏭️ O'tkazib yuborish":
        interests = text
        
    data = await state.get_data()
    await state.clear()
    
    user_id = message.from_user.id
    
    if user_id in database.users:
        database.users[user_id]["profile"] = {
            "gender": data["gender"],
            "age": data["age"],
            "region": data["region"],
            "interests": interests
        }
        await database.save_index(message.bot)
        
    await message.answer(
        "🎉 Profilingiz muvaffaqiyatli to'ldirildi/yangilandi!",
        reply_markup=keyboards.get_main_menu(database.is_admin(user_id))
    )

# ----------------- KITOBLLAR / CATEGORIES -----------------
@router.message(database.is_menu_button("📚 Kitoblar"))
async def view_categories_menu(message: Message):
    active_cats = {k: v for k, v in database.categories.items() if v.get("status", "active") == "active"}
    if not active_cats:
        await message.answer("Hozircha hech qanday janr mavjud emas.")
        return
        
    cols = database.settings.get("categories_columns", 2)
    order = database.settings.get("categories_order", [])
    kb = keyboards.get_categories_layout_keyboard(database.categories, "user_view_cat", columns=cols, order=order)
    await message.answer("📚 *Janrlardan birini tanlang:*", reply_markup=kb)

@router.callback_query(F.data.startswith("user_view_cat:"))
async def view_category_books(callback: CallbackQuery):
    cat_id = callback.data.split(":")[1]
    cat_info = database.categories.get(cat_id)
    if not cat_info:
        await callback.answer("Janr topilmadi.", show_alert=True)
        return
        
    cat_books = [b for b in database.books.values() if cat_id in b.get("categories", []) and b.get("status", "approved") == "approved"]
    
    if not cat_books:
        await callback.message.answer(f"📁 *{cat_info['name']}* janrida hozircha kitoblar mavjud emas.")
        await callback.answer()
        return
        
    # Apply global sorting configuration
    cat_books = sort_books(cat_books)
    await show_books_page(callback, cat_id, cat_books, 1)

async def show_books_page(callback: CallbackQuery, cat_id: str, books_list: list, page: int):
    PAGE_SIZE = 10  # Upgraded page size from 5 to 10
    total = len(books_list)
    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    
    if page < 1: page = 1
    if page > pages: page = pages
    
    start_idx = (page - 1) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_books = books_list[start_idx:end_idx]
    
    cat_name = database.categories.get(cat_id, {}).get("name", "Janr")
    text = f"📁 *Janr: {cat_name}*\n\nQuyidagi kitoblardan birini tanlang:"
    
    builder = keyboards.InlineKeyboardBuilder()
    for b in page_books:
        builder.row(keyboards.InlineKeyboardButton(text=f"📖 {b['title']} - {b['author']}", callback_data=f"view_book:{b['id']}:cat_{cat_id}_{page}"))
        
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
        await callback.message.answer(text, reply_markup=builder.as_markup())
        
    await callback.answer()

@router.callback_query(F.data.startswith("cat_page:"))
async def handle_category_page(callback: CallbackQuery):
    parts = callback.data.split(":")
    cat_id = parts[1]
    page = int(parts[2])
    cat_books = [b for b in database.books.values() if cat_id in b.get("categories", []) and b.get("status", "approved") == "approved"]
    cat_books = sort_books(cat_books)
    await show_books_page(callback, cat_id, cat_books, page)

@router.callback_query(F.data == "back_to_cats")
async def back_to_categories_callback(callback: CallbackQuery):
    active_cats = {k: v for k, v in database.categories.items() if v.get("status", "active") == "active"}
    cols = database.settings.get("categories_columns", 2)
    order = database.settings.get("categories_order", [])
    kb = keyboards.get_categories_layout_keyboard(active_cats, "user_view_cat", columns=cols, order=order)
    await callback.message.edit_text("📚 *Janrlardan birini tanlang:*", reply_markup=kb)
    await callback.answer()

# ----------------- QIDIRUV / SEARCH -----------------
@router.message(database.is_menu_button("🔍 Qidiruv"))
async def start_search(message: Message, state: FSMContext):
    await state.set_state(UserState.search)
    # Include an inline cancel button to FSM search
    builder = keyboards.InlineKeyboardBuilder()
    builder.row(keyboards.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm"))
    await message.answer("🔍 Qidirmoqchi bo'lgan kitobingiz nomi, muallifi yoki kalit so'zini kiriting:", reply_markup=builder.as_markup())

@router.message(UserState.search)
async def process_search_query(message: Message, state: FSMContext):
    query = message.text.strip()
    if not query:
        await message.answer("Iltimos, qidiruv so'zini kiriting.")
        return
        
    found_books = []
    for b in database.books.values():
        if b.get("status", "approved") == "approved":
            title = b.get("title", "").lower()
            author = b.get("author", "").lower()
            kws = [kw.lower() for kw in b.get("keywords", [])]
            
            match = False
            if query.lower() in title or query.lower() in author:
                match = True
            else:
                for kw in kws:
                    if query.lower() in kw:
                        match = True
                        break
            if match:
                found_books.append(b)
                
    await state.clear()
    
    if not found_books:
        user_id = message.from_user.id
        await message.answer(
            f"Afsuski, '{query}' so'rovi bo'yicha hech qanday kitob topilmadi. Boshqa so'z bilan urinib ko'ring.",
            reply_markup=keyboards.get_main_menu(database.is_admin(user_id))
        )
        return
        
    builder = keyboards.InlineKeyboardBuilder()
    for b in found_books[:10]:
        builder.row(keyboards.InlineKeyboardButton(text=f"📖 {b['title']} - {b['author']}", callback_data=f"view_book:{b['id']}:search"))
    
    user_id = message.from_user.id
    await message.answer(
        f"🔍 *'{query}' bo'yicha topilgan kitoblar:*",
        reply_markup=builder.as_markup()
    )
    await message.answer("Qidiruv tugallandi.", reply_markup=keyboards.get_main_menu(database.is_admin(user_id)))

# ----------------- VIEW BOOK DETAILS -----------------
@router.callback_query(F.data.startswith("view_book:"))
async def view_book_details(callback: CallbackQuery):
    parts = callback.data.split(":")
    book_id = parts[1]
    src = parts[2] if len(parts) > 2 else ""
    book = database.books.get(book_id)
    if not book or book.get("status", "approved") != "approved":
        await callback.answer("Kitob topilmadi yoki o'chirilgan.", show_alert=True)
        return
        
    user_id = callback.from_user.id
    user_data = database.users.get(user_id, {})
    is_fav = book_id in user_data.get("favorites", [])
    has_pdf = bool(book.get("pdf_file_id"))
    
    cat_names = []
    for c_id in book.get("categories", []):
        cat_info = database.categories.get(c_id)
        if cat_info:
            cat_names.append(cat_info["name"])
    cat_str = ", ".join(cat_names) if cat_names else "Noma'lum"
    
    desc = book.get("description", "").replace("\\n", "\n")
    if not desc:
        desc = "Tavsif mavjud emas."
        
    ratings = book.get("ratings", {})
    avg_rating = "0.0"
    ratings_count = len(ratings)
    if ratings_count > 0:
        avg_rating = f"{sum(ratings.values()) / ratings_count:.1f}"
        
    rating_str = f"⭐ *Reyting*: {avg_rating}/5 ({ratings_count} ta ovoz)"
    
    # Calculate duration
    dur_str = format_duration(book.get("duration", 0))
    dur_info = f"\n🕒 *Davomiyligi*: {dur_str}" if book.get("duration", 0) > 0 else ""
    
    details_text = (
        f"📖 *{book['title']}*\n"
        f"✍️ *Muallif*: {book['author']}\n"
        f"📁 *Janr*: {cat_str}\n"
        f"{rating_str}{dur_info}\n\n"
        f"📝 *Tavsif*:\n{desc}"
    )
    
    kb = keyboards.get_book_details_keyboard(book_id, is_fav, has_pdf, src=src)
    
    if book.get("cover_file_id"):
        try:
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

# ----------------- MULTI-AUDIO TINGLASH & YUKLAB OLISH -----------------
@router.callback_query(F.data.startswith("play_book:"))
async def play_book_audio(callback: CallbackQuery):
    book_id = callback.data.split(":")[1]
    book = database.books.get(book_id)
    if not book:
        await callback.answer("Kitob topilmadi.", show_alert=True)
        return
        
    user_id = callback.from_user.id
    
    # Update History without immediately saving index
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
    user_data["history"] = history_list[:10]
    
    await callback.answer("Audiodetallar yuklanmoqda...")
    
    audios = book.get("audio_files", [])
    if not audios:
        # Fallback if audio_files is missing but audio_file_id is there
        old_id = book.get("audio_file_id")
        if old_id:
            audios = [{"file_id": old_id, "file_type": book.get("audio_file_type", "audio"), "duration": book.get("duration", 0)}]
            book["audio_files"] = audios
            
    if not audios:
        await callback.message.answer("⚠️ Ushbu kitobning audio fayli topilmadi.")
        return
        
    footer = database.settings.get("custom_footer", "")
    bot_info = await callback.bot.get_me()
    
    total_audios = len(audios)
    
    # Send all audios sequentially
    for idx, audio in enumerate(audios, 1):
        caption = f"🎧 *{book['title']}* - {idx}-qism\n✍️ *Muallif*: {book['author']}"
        if footer:
            caption += f"\n\n{footer}"
            
        file_id = audio["file_id"]
        file_type = audio.get("file_type", "audio")
        
        # Attach play keyboard ONLY to the last audio file
        kb = keyboards.get_audio_play_keyboard(book_id, bot_info.username) if idx == total_audios else None
        
        try:
            if file_type == "document":
                await callback.message.answer_document(document=file_id, caption=caption, reply_markup=kb)
            else:
                await callback.message.answer_audio(audio=file_id, caption=caption, reply_markup=kb)
        except Exception as e:
            logger.error(f"Error sending audio: {e}")
            try:
                # Try fallback format
                if file_type == "document":
                    await callback.message.answer_audio(audio=file_id, caption=caption, reply_markup=kb)
                else:
                    await callback.message.answer_document(document=file_id, caption=caption, reply_markup=kb)
            except Exception:
                await callback.message.answer(f"⚠️ {idx}-qism audio faylini yuborib bo'lmadi.")

@router.callback_query(F.data.startswith("download_audio:"))
async def download_book_audio(callback: CallbackQuery):
    book_id = callback.data.split(":")[1]
    book = database.books.get(book_id)
    if not book:
        await callback.answer("Kitob topilmadi.", show_alert=True)
        return
        
    await callback.answer("Audio yuklab olish uchun yuborilmoqda...")
    audios = book.get("audio_files", [])
    if not audios:
        old_id = book.get("audio_file_id")
        if old_id:
            audios = [{"file_id": old_id, "file_type": book.get("audio_file_type", "audio")}]
            
    if not audios:
        await callback.message.answer("⚠️ Audio fayl topilmadi.")
        return
        
    footer = database.settings.get("custom_footer", "")
    for idx, audio in enumerate(audios, 1):
        caption = f"📥 *Yuklab olindi*: {book['title']} - {idx}-qism"
        if footer:
            caption += f"\n\n{footer}"
        file_id = audio["file_id"]
        try:
            # Force download by sending as document
            await callback.message.answer_document(document=file_id, caption=caption)
        except Exception:
            try:
                await callback.message.answer_audio(audio=file_id, caption=caption)
            except Exception:
                await callback.message.answer(f"⚠️ {idx}-qism faylini yuborib bo'lmadi.")

@router.callback_query(F.data.startswith("download_pdf:"))
async def download_book_pdf(callback: CallbackQuery):
    book_id = callback.data.split(":")[1]
    book = database.books.get(book_id)
    if not book or not book.get("pdf_file_id"):
        await callback.answer("Ushbu kitobning PDF fayli mavjud emas.", show_alert=True)
        return
        
    await callback.answer("PDF yuklab olinmoqda...")
    
    footer = database.settings.get("custom_footer", "")
    caption = f"📄 *PDF*: {book['title']} - {book['author']}"
    if footer:
        caption += f"\n\n{footer}"
        
    try:
        await callback.message.answer_document(document=book["pdf_file_id"], caption=caption)
    except Exception:
        await callback.message.answer("⚠️ PDF faylini yuborishda xatolik yuz berdi.")

# ----------------- FAVORITES (KUTUBXONAM) TOGGLE -----------------
@router.callback_query(F.data.startswith("toggle_fav:"))
async def toggle_favorite(callback: CallbackQuery):
    parts = callback.data.split(":")
    book_id = parts[1]
    src = parts[2] if len(parts) > 2 else ""
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
        await callback.answer("Kitob kutubxonangizdan o'chirildi.", show_alert=False)
    else:
        favs.append(book_id)
        await callback.answer("Kitob kutubxonangizga qo'shildi.", show_alert=False)
        
    user_data["favorites"] = favs
    await database.save_index(callback.bot)
    
    has_pdf = bool(database.books.get(book_id, {}).get("pdf_file_id"))
    is_now_fav = book_id in favs
    kb = keyboards.get_book_details_keyboard(book_id, is_now_fav, has_pdf, src=src)
    
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass

# ----------------- LISTENING VERIFICATION & RATINGS -----------------
@router.callback_query(F.data.startswith("finish_book:"))
async def finish_book_listening(callback: CallbackQuery):
    book_id = callback.data.split(":")[1]
    book = database.books.get(book_id)
    if not book:
        await callback.answer("Kitob topilmadi.", show_alert=True)
        return
        
    user_id = callback.from_user.id
    user_data = database.users.setdefault(user_id, {
        "id": user_id,
        "favorites": [],
        "history": [],
        "listening_stats": {"total_seconds": 0, "completed_books": []},
        "joined_at": datetime.now().isoformat()
    })
    
    stats = user_data.setdefault("listening_stats", {"total_seconds": 0, "completed_books": []})
    completed_books = stats.setdefault("completed_books", [])
    
    if book_id not in completed_books:
        completed_books.append(book_id)
        duration = book.get("duration", 0)
        stats["total_seconds"] += duration
        await database.save_index(callback.bot)
        
        dur_str = format_duration(duration)
        await callback.message.answer(
            f"🎉 *Ajoyib!* Siz *'{book['title']}'* kitobini eshitib tugatdingiz!\n"
            f"Eshitilgan vaqt: *{dur_str}* kutubxonangiz statistikasiga qo'shildi.\n\n"
            f"Iltimos, kitobni xolis baholang:",
            reply_markup=keyboards.get_book_rating_keyboard(book_id)
        )
    else:
        await callback.message.answer(
            f"Siz ushbu kitobni avval ham tinglab tugatgansiz. Baholamoqchi bo'lsangiz bosing:",
            reply_markup=keyboards.get_book_rating_keyboard(book_id)
        )
    await callback.answer()

@router.callback_query(F.data.startswith("show_rating:"))
async def show_rating_keyboard(callback: CallbackQuery):
    book_id = callback.data.split(":")[1]
    user_id = callback.from_user.id
    
    # Restrict rating to users who completed listening (except admins/owner)
    stats = database.users.get(user_id, {}).get("listening_stats", {})
    completed_books = stats.get("completed_books", [])
    
    if book_id not in completed_books and not database.is_admin(user_id):
        await callback.answer(
            "⚠️ Boshqalarga xolis baho berish uchun avval ushbu kitobni eshitib tugatishingiz kerak!\n"
            "Kitobni to'liq eshitgach, '✅ Eshitib tugatdim' tugmasini bosing.",
            show_alert=True
        )
        return
        
    await callback.message.answer(
        "⭐ Kitob uchun o'z bahoingizni tanlang:",
        reply_markup=keyboards.get_book_rating_keyboard(book_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("rate_b:"))
async def process_book_rating(callback: CallbackQuery):
    parts = callback.data.split(":")
    book_id = parts[1]
    score = int(parts[2])
    user_id = callback.from_user.id
    
    # Double check restriction
    stats = database.users.get(user_id, {}).get("listening_stats", {})
    completed_books = stats.get("completed_books", [])
    
    if book_id not in completed_books and not database.is_admin(user_id):
        await callback.answer(
            "⚠️ Boshqalarga xolis baho berish uchun avval ushbu kitobni eshitib tugatishingiz kerak!",
            show_alert=True
        )
        return
        
    book = database.books.get(book_id)
    if not book:
        await callback.answer("Kitob topilmadi.", show_alert=True)
        return
        
    ratings = book.setdefault("ratings", {})
    ratings[str(user_id)] = score
    await database.save_index(callback.bot)
    
    await callback.answer(f"Siz ushbu kitobga {score} ball berdingiz! Rahmat.", show_alert=True)
    try:
        await callback.message.delete()
    except Exception:
        pass

@router.callback_query(F.data == "close_rating")
async def close_rating(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()

# ----------------- USER CONTACT ADMIN -----------------
@router.callback_query(F.data == "user_contact_admin")
async def start_contact_admin(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserContactForm.message)
    builder = keyboards.InlineKeyboardBuilder()
    builder.row(keyboards.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm"))
    await callback.message.answer(
        "✍️ Adminlarga yubormoqchi bo'lgan xabaringiz yoki taklifingizni yozib yuboring:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.message(UserContactForm.message)
async def process_contact_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text.strip()
    
    if not text:
        await message.answer("Xabar matni bo'sh bo'lishi mumkin emas.")
        return
        
    await state.clear()
    
    admin_msg = (
        "📩 *Adminga murojaat keldi:*\n\n"
        f"• *Foydalanuvchi*: {message.from_user.full_name}\n"
        f"• *Telegram ID*: `{user_id}`\n"
        f"• *Username*: @{message.from_user.username or 'yoq'}\n\n"
        f"💬 *Xabar*:\n{text}"
    )
    
    kb = keyboards.get_admin_reply_keyboard(user_id)
    
    for admin_id in database.admins:
        try:
            await message.bot.send_message(chat_id=admin_id, text=admin_msg, reply_markup=kb)
        except Exception as e:
            logger.warning(f"Could not forward contact message to admin {admin_id}: {e}")
            
    if OWNER_ID not in database.admins:
        try:
            await message.bot.send_message(chat_id=OWNER_ID, text=admin_msg, reply_markup=kb)
        except Exception as e:
            logger.warning(f"Could not forward contact message to owner: {e}")
            
    await message.answer(
        "✅ Xabaringiz adminlarga yuborildi. Tez orada javob qaytarishadi.",
        reply_markup=keyboards.get_main_menu(database.is_admin(user_id))
    )

# ----------------- BOOK RECOMMENDATION SYSTEM (WITH MULTI-GENRES & AUDIOS) -----------------
@router.message(database.is_menu_button("💡 Kitob Tavsiya Qilish"))
async def start_recommendation(message: Message, state: FSMContext):
    await state.set_state(UserRecForm.title)
    builder = keyboards.InlineKeyboardBuilder()
    builder.row(keyboards.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm"))
    await message.answer(
        "💡 *Kitob tavsiya qilish bo'limi:*\n\nKitob nomini kiriting:",
        reply_markup=builder.as_markup()
    )

@router.message(UserRecForm.title)
async def process_rec_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(UserRecForm.author)
    builder = keyboards.InlineKeyboardBuilder()
    builder.row(keyboards.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm"))
    await message.answer("Muallif ismini kiriting:", reply_markup=builder.as_markup())

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
        
    active_cats = {k: v for k, v in database.categories.items() if v.get("status", "active") == "active"}
    if not active_cats:
        await state.clear()
        user_id = message.from_user.id
        await message.answer(
            "Tizimda janrlar mavjud emas. Hozircha tavsiya yuborib bo'lmaydi.",
            reply_markup=keyboards.get_main_menu(database.is_admin(user_id))
        )
        return
        
    await state.update_data(selected_categories=[])
    await state.set_state(UserRecForm.category)
    
    # Multi-category selector grid
    kb = keyboards.get_multi_category_selector(database.categories, [], "user_rec_cat")
    await message.answer("Kitob qaysi janrlarga tegishli? Kerakli janrlarni tanlab, 'Tasdiqlash' tugmasini bosing:", reply_markup=kb)

@router.callback_query(UserRecForm.category, F.data.startswith("user_rec_cat_toggle:"))
async def process_rec_category_toggle(callback: CallbackQuery, state: FSMContext):
    cat_id = callback.data.split(":")[1]
    data = await state.get_data()
    selected = data.get("selected_categories", [])
    
    if cat_id in selected:
        selected.remove(cat_id)
    else:
        selected.append(cat_id)
        
    await state.update_data(selected_categories=selected)
    
    kb = keyboards.get_multi_category_selector(database.categories, selected, "user_rec_cat")
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await callback.answer()

@router.callback_query(UserRecForm.category, F.data == "user_rec_cat_confirm")
async def process_rec_category_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_categories", [])
    
    if not selected:
        await callback.answer("Kamida bitta janrni tanlash majburiy!", show_alert=True)
        return
        
    await state.set_state(UserRecForm.audio)
    await state.update_data(audio_files=[])
    
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    builder = keyboards.InlineKeyboardBuilder()
    builder.row(
        keyboards.InlineKeyboardButton(text="⏭️ Audio yo'q / Yakunlash", callback_data="user_rec_audio_done"),
        keyboards.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")
    )
    await callback.message.answer(
        "Kitobning audio fayllarini yuboring (ixtiyoriy, birma-bir bir nechta audio yuborishingiz mumkin):\n"
        "Fayllarni yuborib bo'lgach, 'Yakunlash' tugmasini bosing.",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.message(UserRecForm.audio)
async def process_rec_audio_upload(message: Message, state: FSMContext):
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
        await message.answer("Iltimos, audio fayl yuboring yoki quyidagi 'Yakunlash' tugmasini bosing.")
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
        keyboards.InlineKeyboardButton(text="✅ Yakunlash", callback_data="user_rec_audio_done"),
        keyboards.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")
    )
    await message.answer(
        f"✅ {len(audio_files)}-audio qabul qilindi. Yana yuborishingiz yoki yakunlashingiz mumkin:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(UserRecForm.audio, F.data == "user_rec_audio_done")
async def process_rec_audio_done(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserRecForm.cover)
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    builder = keyboards.InlineKeyboardBuilder()
    builder.row(
        keyboards.InlineKeyboardButton(text="⏭️ O'tkazib yuborish", callback_data="user_rec_cover_skip"),
        keyboards.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")
    )
    await callback.message.answer(
        "Kitob muqovasini yuboring (rasm, ixtiyoriy):",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(UserRecForm.cover, F.data == "user_rec_cover_skip")
async def process_rec_cover_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(cover_file_id="")
    await state.set_state(UserRecForm.pdf)
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    builder = keyboards.InlineKeyboardBuilder()
    builder.row(
        keyboards.InlineKeyboardButton(text="⏭️ O'tkazib yuborish", callback_data="user_rec_pdf_skip"),
        keyboards.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")
    )
    await callback.message.answer(
        "Kitobning PDF variantini yuboring (hujjat, ixtiyoriy):",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.message(UserRecForm.cover)
async def process_rec_cover_upload(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer("Iltimos, rasm yuboring yoki o'tkazib yuboring.")
        return
        
    await state.update_data(cover_file_id=message.photo[-1].file_id)
    await state.set_state(UserRecForm.pdf)
    
    builder = keyboards.InlineKeyboardBuilder()
    builder.row(
        keyboards.InlineKeyboardButton(text="⏭️ O'tkazib yuborish", callback_data="user_rec_pdf_skip"),
        keyboards.InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_fsm")
    )
    await message.answer(
        "Kitobning PDF variantini yuboring (hujjat, ixtiyoriy):",
        reply_markup=builder.as_markup()
    )

@router.callback_query(UserRecForm.pdf, F.data == "user_rec_pdf_skip")
async def process_rec_pdf_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(pdf_file_id="")
    await show_rec_summary(callback.message, state)
    await callback.answer()

@router.message(UserRecForm.pdf)
async def process_rec_pdf_upload(message: Message, state: FSMContext):
    if not message.document:
        await message.answer("Iltimos, hujjat formatida PDF yuboring yoki o'tkazib yuboring.")
        return
        
    await state.update_data(pdf_file_id=message.document.file_id)
    await show_rec_summary(message, state)

async def show_rec_summary(message: Message, state: FSMContext):
    data = await state.get_data()
    
    cat_names = []
    for c_id in data["selected_categories"]:
        cat_info = database.categories.get(c_id)
        if cat_info:
            cat_names.append(cat_info["name"])
    cat_str = ", ".join(cat_names) if cat_names else "Noma'lum"
    
    desc_val = data.get("description") or "yo'q"
    audio_files = data.get("audio_files", [])
    audio_status = f"{len(audio_files)} ta audio" if audio_files else "yo'q"
    cover_status = "bor" if data.get("cover_file_id") else "yo'q"
    pdf_status = "bor" if data.get("pdf_file_id") else "yo'q"
    
    summary = (
        "📖 *Kitob tavsiyasi tayyor:*\n\n"
        f"• *Nomi*: {data['title']}\n"
        f"• *Muallif*: {data['author']}\n"
        f"• *Janrlar*: {cat_str}\n"
        f"• *Tavsif*: {desc_val}\n"
        f"• *Audio*: {audio_status}\n"
        f"• *Muqova*: {cover_status}\n"
        f"• *PDF*: {pdf_status}\n\n"
        "Tavsiyani tasdiqlaysizmi?"
    )
    
    await state.set_state(UserRecForm.confirm)
    await message.answer(summary, reply_markup=keyboards.get_confirmation_keyboard())
    # Keep reply cancelled layout
    await message.answer("Tugmalardan foydalaning.", reply_markup=keyboards.get_cancel_keyboard())

@router.callback_query(UserRecForm.confirm, F.data.startswith("confirm_"))
async def process_rec_confirmation(callback: CallbackQuery, state: FSMContext):
    decision = callback.data.split("_")[1]
    user_id = callback.from_user.id
    
    if decision == "no":
        await state.clear()
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            "Tavsiya bekor qilindi.",
            reply_markup=keyboards.get_main_menu(database.is_admin(user_id))
        )
        await callback.answer()
        return
        
    data = await state.get_data()
    await state.clear()
    
    rec_id = str(uuid.uuid4())[:8]
    audio_files = data.get("audio_files", [])
    
    rec_data = {
        "id": rec_id,
        "user_id": user_id,
        "title": data["title"],
        "author": data["author"],
        "description": data["description"],
        "categories": data["selected_categories"],
        "audio_files": audio_files,
        "cover_file_id": data["cover_file_id"],
        "pdf_file_id": data["pdf_file_id"],
        "duration": sum(f.get("duration", 0) for f in audio_files),
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    
    database.recommendations[rec_id] = rec_data
    await database.save_index(callback.bot)
    
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    await callback.message.answer(
        "✅ Rahmat! Sizning tavsiyangiz adminlarga ko'rib chiqish uchun yuborildi.",
        reply_markup=keyboards.get_main_menu(database.is_admin(user_id))
    )
    await callback.answer()
    
    # Notify admins with direct audio/pdf references so they can play/see them!
    cat_names = []
    for c_id in data["selected_categories"]:
        cat_info = database.categories.get(c_id)
        if cat_info:
            cat_names.append(cat_info["name"])
    cat_str = ", ".join(cat_names)
    
    desc_val = data.get("description") or "yo'q"
    user_name_val = callback.from_user.username or "username_yoq"
    
    admin_text = (
        "💡 *Yangi kitob tavsiyasi keldi:*\n\n"
        f"• *Nomi*: {data['title']}\n"
        f"• *Muallif*: {data['author']}\n"
        f"• *Janrlar*: {cat_str}\n"
        f"• *Tavsif*: {desc_val}\n"
        f"• *Fayllar*: {len(audio_files)} ta audio, PDF: {'bor' if data['pdf_file_id'] else 'yoq'}\n"
        f"• *Kimdan*: ID `{user_id}` (@{user_name_val})\n\n"
        "Tavsiyani ma'qullaysizmi?"
    )
    
    kb = keyboards.get_recommendation_decide_keyboard(rec_id)
    
    # Forward the audio and PDF files to admins first so they can actually review them!
    async def send_previews(admin_id):
        # 1. Send text details card
        await callback.bot.send_message(chat_id=admin_id, text=admin_text, reply_markup=kb)
        # 2. Send cover if present
        if data.get("cover_file_id"):
            try:
                await callback.bot.send_photo(chat_id=admin_id, photo=data["cover_file_id"], caption=f"🖼️ *Tavsiya muqovasi*: {data['title']}")
            except Exception:
                pass
        # 3. Send PDF if present
        if data.get("pdf_file_id"):
            try:
                await callback.bot.send_document(chat_id=admin_id, document=data["pdf_file_id"], caption=f"📄 *Tavsiya PDF*: {data['title']}")
            except Exception:
                pass
        # 4. Send Audios
        for idx, f in enumerate(audio_files, 1):
            try:
                caption = f"🎧 *Tavsiya Audio* ({idx}/{len(audio_files)}): {data['title']}"
                if f.get("file_type") == "document":
                    await callback.bot.send_document(chat_id=admin_id, document=f["file_id"], caption=caption)
                else:
                    await callback.bot.send_audio(chat_id=admin_id, audio=f["file_id"], caption=caption)
            except Exception:
                pass
                
    for admin_id in database.admins:
        try:
            await send_previews(admin_id)
        except Exception as e:
            logger.warning(f"Could not notify admin {admin_id}: {e}")
            
    if OWNER_ID not in database.admins:
        try:
            await send_previews(OWNER_ID)
        except Exception as e:
            logger.warning(f"Could not notify owner: {e}")


# ----------------- BACK TO BOOKS FREEZE FIX -----------------
@router.callback_query(F.data.startswith("back_to_books:"))
async def handle_back_to_books(callback: CallbackQuery):
    parts = callback.data.split(":")
    book_id = parts[1]
    src = parts[2] if len(parts) > 2 else ""
    
    # Depending on the source, route back
    if src.startswith("cat_"):
        src_parts = src.split("_")
        cat_id = src_parts[1]
        page = int(src_parts[2]) if len(src_parts) > 2 else 1
        
        cat_books = [b for b in database.books.values() if cat_id in b.get("categories", []) and b.get("status", "approved") == "approved"]
        cat_books = sort_books(cat_books)
        
        # Show category page
        await show_books_page(callback, cat_id, cat_books, page)
    elif src == "lib_fav":
        try:
            await callback.message.delete()
        except Exception:
            pass
        await view_lib_books(callback)
    elif src == "lib_hist":
        try:
            await callback.message.delete()
        except Exception:
            pass
        await view_lib_history(callback)
    elif src == "search":
        try:
            await callback.message.delete()
        except Exception:
            pass
        user_id = callback.from_user.id
        await callback.message.answer("Qidiruv natijalariga qaytish uchun qayta qidiring yoki menyudan foydalaning.", 
                                      reply_markup=keyboards.get_main_menu(database.is_admin(user_id)))
        await callback.answer()
    elif src.startswith("ai_rec"):
        try:
            await callback.message.delete()
        except Exception:
            pass
        user_id = callback.from_user.id
        await callback.message.answer(
            "AI Tavsiyalariga qaytish uchun menyudan '🧠 AI Tavsiya' tugmasini tanlang.",
            reply_markup=keyboards.get_main_menu(database.is_admin(user_id))
        )
        await callback.answer()
    else:
        # Fallback to categories list
        try:
            await callback.message.delete()
        except Exception:
            pass
        active_cats = {k: v for k, v in database.categories.items() if v.get("status", "active") == "active"}
        cols = database.settings.get("categories_columns", 2)
        order = database.settings.get("categories_order", [])
        kb = keyboards.get_categories_layout_keyboard(active_cats, "user_view_cat", columns=cols, order=order)
        await callback.message.answer("📚 *Janrlardan birini tanlang:*", reply_markup=kb)
        await callback.answer()


# ----------------- AI PSYCHOLOGICAL RECOMMENDATION ENGINE -----------------
MOOD_OPTIONS = [
    "😊 Xursand / Ko'tarinki",
    "😔 Charchagan / G'amgin",
    "🤔 Fikrlashga moyil / Jiddiy",
    "🧘 Xotirjam / Orombaxsh"
]

INTEREST_OPTIONS = [
    "💡 Shaxsiy rivojlanish / Muvaffaqiyat",
    "🎭 Siyosat / Tarix / Hayotiy",
    "🔮 Sirlar / Detektiv / Sarguzasht",
    "❤️ Sevgi / Muhabbat"
]

EXPECTATION_OPTIONS = [
    "🚀 Yangi motivatsiya va kuch",
    "🧠 Kuchli falsafiy fikrlar",
    "🌌 Hayoliy dunyoga sayohat",
    "😴 Shunchaki dam olish"
]

@router.message(database.is_menu_button("🧠 AI Tavsiya"))
async def start_ai_recommendation(message: Message, state: FSMContext):
    # Check if AI is enabled
    if not database.settings.get("ai_enabled", True):
        await message.answer("⚠️ Kechirasiz, AI funksiyalari hozirda vaqtincha o'chirilgan.")
        return
        
    await state.set_state(UserAIRecommendationState.mood)
    kb = keyboards.get_quiz_keyboard(MOOD_OPTIONS, "quiz_mood")
    await message.answer(
        "🧠 *AI Psixologik Tavsiya Tizimi*\n\n"
        "Sizning hozirgi ruhiy holatingizga mos kitoblarni tanlab berishim uchun quyidagi savollarga javob bering.\n\n"
        "1. *Hozirgi kayfiyatingiz qanday?*",
        reply_markup=kb
    )

@router.callback_query(UserAIRecommendationState.mood, F.data.startswith("quiz_mood:"))
async def process_quiz_mood(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.split(":")[1])
    mood = MOOD_OPTIONS[idx]
    await state.update_data(mood=mood)
    
    await state.set_state(UserAIRecommendationState.interest)
    kb = keyboards.get_quiz_keyboard(INTEREST_OPTIONS, "quiz_interest")
    await callback.message.edit_text(
        "🧠 *AI Psixologik Tavsiya Tizimi*\n\n"
        f"Kayfiyat: {mood}\n\n"
        "2. *Sizni hozirda qaysi mavzu ko'proq qiziqtiradi?*",
        reply_markup=kb
    )
    await callback.answer()

@router.callback_query(UserAIRecommendationState.interest, F.data.startswith("quiz_interest:"))
async def process_quiz_interest(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.split(":")[1])
    interest = INTEREST_OPTIONS[idx]
    data = await state.get_data()
    mood = data["mood"]
    await state.update_data(interest=interest)
    
    await state.set_state(UserAIRecommendationState.expectation)
    kb = keyboards.get_quiz_keyboard(EXPECTATION_OPTIONS, "quiz_expect")
    await callback.message.edit_text(
        "🧠 *AI Psixologik Tavsiya Tizimi*\n\n"
        f"Kayfiyat: {mood}\n"
        f"Qiziqish: {interest}\n\n"
        "3. *Kitobdan nima kutmoqdasiz?*",
        reply_markup=kb
    )
    await callback.answer()

@router.callback_query(UserAIRecommendationState.expectation, F.data.startswith("quiz_expect:"))
async def process_quiz_expectation(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.split(":")[1])
    expect = EXPECTATION_OPTIONS[idx]
    data = await state.get_data()
    mood = data["mood"]
    interest = data["interest"]
    
    await callback.message.edit_text("⌛ AI siz uchun eng mos kitoblarni tahlil qilmoqda. Iltimos, kuting...")
    await callback.answer()
    
    # Fetch all active books to build system context
    active_books = [b for b in database.books.values() if b.get("status", "approved") == "approved"]
    if not active_books:
        await callback.message.answer(
            "Tizimda tavsiya qilish uchun kitoblar yetarli emas.",
            reply_markup=keyboards.get_main_menu(database.is_admin(callback.from_user.id))
        )
        await state.clear()
        return
        
    books_context_list = []
    for b in active_books[:30]:  # Limit context size to fit token limits
        books_context_list.append(f"ID: {b['id']} | Title: {b['title']} | Author: {b['author']} | Description: {b.get('description', '')[:100]}")
    books_context = "\n".join(books_context_list)
    
    system_instruction = (
        "Siz kitob tavsiya qiluvchi AI tizimsiz. Sizga berilgan kitoblar ro'yxatidan foydalanuvchining psixologik javoblariga mos keladigan eng yaxshi 3 ta kitobni tanlashingiz va tavsiya sababini ko'rsatishingiz lozim.\n"
        "Faqat va faqat quyidagi formatda javob bering, har bir kitob uchun alohida qatorlarda:\n"
        "[ID: <kitob_id>] - <kitob_nomi> - <muallif>\n"
        "Tavsiya sababi: <sabab>\n\n"
        "Eslatma: kitob ID raqamlari berilgan ro'yxatdagidek 100% aniq bo'lsin!"
    )
    
    prompt = (
        f"Mavjud kitoblar:\n{books_context}\n\n"
        f"Foydalanuvchi javoblari:\n"
        f"1. Kayfiyat: {mood}\n"
        f"2. Qiziqish mavzusi: {interest}\n"
        f"3. Kutish: {expect}\n\n"
        "Eng mos keladigan 3 ta kitobni tavsiya qiling."
    )
    
    ai_response = await ai_service.generate_response(prompt, system_instruction)
    
    # Parse the recommended book IDs from AI response
    recommended_ids = []
    lines = ai_response.split("\n")
    for line in lines:
        if "[ID:" in line:
            try:
                parts = line.split("]")[0].split("[ID:")
                if len(parts) > 1:
                    bid = parts[1].strip()
                    if bid in database.books:
                        recommended_ids.append(bid)
            except Exception:
                pass
                
    # Remove duplicate recommendations
    recommended_ids = list(dict.fromkeys(recommended_ids))
    
    await state.clear()
    
    # Prepare text summary
    response_clean = ai_response.replace("[ID:", "").replace("]", "")
    
    summary_text = (
        "🧠 *AI Psixologik Tavsiyalari:*\n\n"
        f"{response_clean}\n\n"
        "Tavsiya etilgan kitoblarni quyidagi tugmalar orqali batafsil ko'rishingiz mumkin:"
    )
    
    builder = keyboards.InlineKeyboardBuilder()
    for bid in recommended_ids:
        b_info = database.books[bid]
        builder.row(keyboards.InlineKeyboardButton(text=f"📖 {b_info['title']}", callback_data=f"view_book:{bid}:ai_rec"))
        
    if recommended_ids:
        ids_str = ",".join(recommended_ids)
        if len(ids_str) < 50:  # Check callback payload limits
            builder.row(keyboards.InlineKeyboardButton(text="📥 Hammasini Kutubxonamga Qo'shish", callback_data=f"ai_add_all:{ids_str}"))
            
    builder.row(keyboards.InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_cats"))
    
    # Delete the waiting message
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    await callback.message.answer(summary_text, reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("ai_add_all:"))
async def process_ai_add_all(callback: CallbackQuery):
    parts = callback.data.split(":")
    ids_str = parts[1]
    book_ids = [bid.strip() for bid in ids_str.split(",") if bid.strip()]
    
    user_id = callback.from_user.id
    user_data = database.users.setdefault(user_id, {
        "id": user_id,
        "favorites": [],
        "history": [],
        "joined_at": datetime.now().isoformat()
    })
    
    favs = user_data.setdefault("favorites", [])
    added_count = 0
    for bid in book_ids:
        if bid in database.books and bid not in favs:
            favs.append(bid)
            added_count += 1
            
    user_data["favorites"] = favs
    await database.save_index(callback.bot)
    
    await callback.answer(f"✅ {added_count} ta yangi kitob kutubxonangizga qo'shildi!", show_alert=True)


# ----------------- AI BOOK COMPANION (RAG FREE CHAT) -----------------
@router.message(database.is_menu_button("💬 AI Companion"))
async def start_ai_companion(message: Message, state: FSMContext):
    if not database.settings.get("ai_enabled", True):
        await message.answer("⚠️ Kechirasiz, AI funksiyalari hozirda vaqtincha o'chirilgan.")
        return
        
    await state.set_state(UserAIChatState.chat)
    
    kb = keyboards.ReplyKeyboardBuilder()
    kb.row(keyboards.KeyboardButton(text="❌ Chiqish"))
    
    await message.answer(
        "💬 *AI Companion (Kitob Hamrohi) suhbat rejimiga xush kelibsiz!*\n\n"
        "Men botdagi mavjud kitoblar haqida batafsil ma'lumotga egaman. "
        "Mendan istalgan kitob, muallif yoki janr haqida so'rashingiz mumkin.\n\n"
        "Suhbatdan chiqish uchun quyidagi *'❌ Chiqish'* tugmasini bosing.",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )

@router.message(UserAIChatState.chat)
async def process_ai_companion_chat(message: Message, state: FSMContext):
    text = message.text.strip() if message.text else ""
    if not text:
        await message.answer("Iltimos, faqat matnli xabarlar yuboring.")
        return
        
    if text == "❌ Chiqish":
        await state.clear()
        user_id = message.from_user.id
        await message.answer(
            "Suhbat yakunlandi. Asosiy menyuga qaytdingiz.",
            reply_markup=keyboards.get_main_menu(database.is_admin(user_id))
        )
        return
        
    status_msg = await message.answer("💬 *AI o'ylamoqda...*")
    
    # Fetch all active books to build RAG context
    active_books = [b for b in database.books.values() if b.get("status", "approved") == "approved"]
    
    books_context_list = []
    for b in active_books[:40]:  # Limit context size to fit token limits
        cat_names = []
        for c_id in b.get("categories", []):
            cat_info = database.categories.get(c_id)
            if cat_info:
                cat_names.append(cat_info["name"])
        cat_str = ", ".join(cat_names)
        
        books_context_list.append(
            f"- Sarlavha: {b['title']}\n"
            f"  Muallif: {b['author']}\n"
            f"  Janrlar: {cat_str}\n"
            f"  Tavsif: {b.get('description', '')[:150]}"
        )
    books_context = "\n\n".join(books_context_list)
    
    system_instruction = (
        "Siz \"Uzbek Audio Book Bot\" tizimining kitob hamrohi (AI Companion) hisoblanasiz.\n"
        "Foydalanuvchi bilan o'zbek tilida, do'stona va kitobxonlarga xos ohangda muloqot qiling.\n\n"
        "Botdagi mavjud kitoblar ro'yxati:\n"
        f"{books_context}\n\n"
        "Qoidalar:\n"
        "1. Foydalanuvchiga faqat yuqoridagi kitoblar ro'yxatida bor bo'lgan kitoblarni tavsiya qiling va ular haqida gapiring.\n"
        "2. Agar foydalanuvchi ro'yxatda yo'q kitobni so'rasa, u kitob botda yo'qligini, lekin u kitobni menyudagi '💡 Kitob Tavsiya Qilish' tugmasi orqali botga qo'shishni so'rashi mumkinligini muloyimlik bilan tushuntiring.\n"
        "3. Har doim qisqa va qiziqarli javoblar bering."
    )
    
    ai_response = await ai_service.generate_response(text, system_instruction)
    
    await status_msg.delete()
    await message.answer(ai_response)
