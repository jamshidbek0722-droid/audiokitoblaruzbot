# Uzbek Telegram Audio Book Bot

Ushbu bot Telegram kanali orqali ishlaydigan in-memory ma'lumotlar bazasiga ega bo'lgan Uzbek tilidagi audiokitoblar botidir. Bot SQLite, MySQL yoki mahalliy JSON fayllardan foydalanmaydi. Barcha ma'lumotlar faqat bitta Telegram saqlash kanalida (`#INDEX` xabari) saqlanadi.

## Xususiyatlari
- **In-Memory Database**: Bot ishga tushganda saqlash kanalining mahkamlangan (pinned) xabaridan butun ma'lumotlar bazasini yuklaydi va tezkor ishlaydi.
- **Admin Panel**:
  - Janrlarni qo'shish va o'chirish.
  - Kitob qo'shish (Audio fayl MAJBURIY, muqova va PDF ixtiyoriy).
  - Kitob tahrirlash (Nomi, muallifi, tavsifi) va o'chirish.
  - Foydalanuvchi tavsiyalarini bir-klikda tasdiqlash yoki rad etish.
  - Foydalanuvchilarga xabar tarqatish (Matn, rasm, audio).
  - Majburiy obuna kanallarini boshqarish (qo'shish, o'chirish, yoqish/o'chirish).
  - Ma'lumotlar bazasini yangilash va JSON zaxira nusxasini yuklab olish.
- **Foydalanuvchi Paneli**:
  - Janrlar bo'yicha kitoblarni sahifalab (pagination) ko'rish.
  - Muallif yoki nomi bo'yicha kitoblarni qidirish.
  - Profil ma'lumotlari, sevimlilar (favorites) va oxirgi tinglangan kitoblar tarixi (history).
  - Kitob tinglash (Tinglash va Yuklab olish tugmalari).
  - PDF kitob yuklash (agar mavjud bo'lsa).
  - Adminlar uchun kitob tavsiya qilish tizimi.

## Talablar
- Python 3.11+
- `aiogram` 3.x kutubxonasi
- Telegram Storage Channel (Bot ushbu kanalda xabar yozish, mahkamlash va o'chirish huquqlariga ega admin bo'lishi shart)

## O'rnatish va Ishga tushirish

1. Zaxira fayllarini o'rnating:
   ```bash
   pip install -r requirements.txt
   ```

2. Sozlamalarni tekshiring yoki o'zgartiring (`config.py`):
   - `BOT_TOKEN`: Telegram bot tokeni.
   - `OWNER_ID`: Tizim asosiy egasining Telegram ID raqami.
   - `STORAGE_CHANNEL_ID`: Kitoblar va baza saqlanadigan kanal ID-si (ID `-100` bilan boshlanishi kerak).

3. Botni saqlash kanaliga qo'shing va unga **Administrator** huquqlarini bering:
   - Xabarlarni yuborish (Post messages)
   - Xabarlarni tahrirlash (Edit messages)
   - Xabarlarni o'chirish (Delete messages)
   - Xabarlarni mahkamlash (Pin messages)

4. Botni ishga tushiring:
   ```bash
   python main.py
   ```
