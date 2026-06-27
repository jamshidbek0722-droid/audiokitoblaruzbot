from aiogram import Router, F, BaseMiddleware
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, TelegramObject
import database
from keyboards import get_main_menu, get_subscription_keyboard
import logging

logger = logging.getLogger(__name__)
router = Router()

class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)
            
        user_id = user.id
        
        # Exempt admins and owners
        if database.is_admin(user_id):
            return await handler(event, data)
            
        is_sub_enabled = database.settings.get("mandatory_subscription", False)
        if is_sub_enabled and database.required_channels:
            # Allow /start and check_sub callback
            if isinstance(event, Message) and event.text:
                if event.text.startswith("/start"):
                    return await handler(event, data)
            if isinstance(event, CallbackQuery) and event.data == "check_sub":
                return await handler(event, data)
                
            bot = data.get("bot")
            unsubscribed = []
            for ch_id, ch_info in database.required_channels.items():
                try:
                    member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
                    if member.status not in ["member", "administrator", "creator"]:
                        unsubscribed.append(ch_info)
                except Exception as e:
                    logger.warning(f"Error checking sub in middleware for chat {ch_id}: {e}")
                    unsubscribed.append(ch_info)
                    
            if unsubscribed:
                kb = get_subscription_keyboard(unsubscribed)
                text = "⚠️ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'lishingiz majburiy:"
                if isinstance(event, Message):
                    await event.answer(text, reply_markup=kb)
                elif isinstance(event, CallbackQuery):
                    await event.message.answer(text, reply_markup=kb)
                    await event.answer()
                return
                
        return await handler(event, data)

@router.message(CommandStart())
async def start_cmd(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name
    
    # Register the user
    await database.register_user(user_id, username, full_name, message.bot)
    
    is_user_admin = database.is_admin(user_id)
    is_sub_enabled = database.settings.get("mandatory_subscription", False)
    
    if is_sub_enabled and database.required_channels and not is_user_admin:
        unsubscribed = []
        for ch_id, ch_info in database.required_channels.items():
            try:
                member = await message.bot.get_chat_member(chat_id=ch_id, user_id=user_id)
                if member.status not in ["member", "administrator", "creator"]:
                    unsubscribed.append(ch_info)
            except Exception as e:
                logger.warning(f"Error checking sub for chat {ch_id}: {e}")
                unsubscribed.append(ch_info)
        
        if unsubscribed:
            kb = get_subscription_keyboard(unsubscribed)
            await message.answer(
                "⚠️ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'lishingiz majburiy:",
                reply_markup=kb
            )
            return

    await message.answer(
        f"Assalomu alaykum, {full_name or 'Foydalanuvchi'}! 📚 Uzbek Audio Book botiga xush kelibsiz!\n"
        "Bu yerda siz turli janrdagi audiokitoblarni tinglashingiz va yuklab olishingiz mumkin.\n\n"
        "Menyudan foydalaning:",
        reply_markup=get_main_menu(is_user_admin)
    )

@router.message(Command("help"))
@router.message(database.is_menu_button("ℹ️ Yordam"))
async def help_cmd(message: Message):
    help_text = (
        "📚 *Botdan foydalanish bo'yicha yordam:*\n\n"
        "• *📚 Kitoblar*: Audiokitoblarni janrlar bo'yicha ko'rish.\n"
        "• *🔍 Qidiruv*: Kitoblarni nomi, muallifi yoki kalit so'zlari bo'yicha qidirish.\n"
        "• *📚 Kutubxonam*: Shaxsiy kutubxonangiz, tinglangan soatlar statistikasi va tarix.\n"
        "• *👤 Profil*: Sizning ma'lumotlaringiz (profil to'ldirish).\n"
        "• *💡 Kitob Tavsiya Qilish*: Botda bo'lmagan kitoblarni tavsiya qilish.\n\n"
        "Muammolar yuzasidan adminlarga murojaat qiling (Profil yoki Yordam bo'limi orqali)."
    )
    await message.answer(help_text)

@router.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    bot = callback.bot
    
    unsubscribed = []
    for ch_id, ch_info in database.required_channels.items():
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status not in ["member", "administrator", "creator"]:
                unsubscribed.append(ch_info)
        except Exception as e:
            logger.warning(f"Error checking sub in callback for chat {ch_id}: {e}")
            unsubscribed.append(ch_info)
            
    if unsubscribed:
        await callback.answer("Siz hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)
    else:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            "✅ Rahmat! Kanallarga a'zoligingiz tasdiqlandi.",
            reply_markup=get_main_menu(database.is_admin(user_id))
        )
        await callback.answer()
