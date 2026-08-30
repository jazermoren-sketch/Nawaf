# Nawaf Discord Bot

بوت Discord مكتوب بـ Python و discord.py 2.x، مع SQLite.

## المميزات
- إرسال رسالة من البوت إلى روم يحدده المشرف: `/send`
- نظام Tickets مع إغلاق وتقييم من 1 إلى 5 وملاحظة
- نظام XP وLevels: `/level`
- نظام تقديم عبر Modal مع قبول/رفض
- نظام إعلانات: `/announce`
- أذكار تلقائية قابلة للتفعيل والتخصيص: `/dhikr-settings`
- عملة خاصة بالسيرفر: `/balance` و`/pay` و`/currency-settings`

## التشغيل
1. ثبّت Python 3.11+.
2. نفّذ `pip install -r requirements.txt`.
3. أنشئ ملف `.env` وضع فيه:
   `DISCORD_TOKEN=توكن_البوت`
4. شغّل `python main.py`.

فعّل في Discord Developer Portal الـMessage Content Intent وServer Members Intent لأن بعض الأنظمة تحتاجها.
