# The starting curriculum: topics, and the variants written so far. It is copied into the database once,
# on first start. After that the administrator edits the database, so this file is only the first version.
# The text follows docs/curriculum.md (version 0.1).

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

# Age band codes used in the curriculum, and the age_band value each code maps to in the student records.
BAND_CODES = {"K": "4-6", "J": "7-10", "T": "11-14", "S": "15-18", "A": "adult"}
BAND_LABELS = {"K": "۴ تا ۶ سال", "J": "۷ تا ۱۰ سال", "T": "۱۱ تا ۱۴ سال", "S": "۱۵ تا ۱۸ سال", "A": "بزرگسال"}

# (id, title, goal, first level, last level, age band codes)
TOPICS = [
    ("INTRO", "معرفی خود", "خودش را معرفی کند و چند جمله درباره‌ی خودش بگوید", "A1", "C2", "KJTSA"),
    ("GREET", "احوال‌پرسی و گفتگوی کوتاه", "سلام کند و گفتگوی کوتاه روزانه را شروع و تمام کند", "A1", "B2", "KJTSA"),
    ("FAMILY", "خانواده", "اعضای خانواده را معرفی و درباره‌شان توضیح دهد", "A1", "B2", "KJT"),
    ("PETS", "حیوان‌ها", "حیوان خود یا موردعلاقه‌اش را توصیف کند", "A1", "B1", "KJ"),
    ("COLORS_OBJECTS", "رنگ و اشیا", "اشیا و رنگ‌ها را نام ببرد و توصیف کند", "A1", "A1", "KJ"),
    ("FEELINGS", "احساسات", "احساس خود را بگوید و دلیلش را توضیح دهد", "A1", "B2", "KJTSA"),
    ("FAVORITES", "علاقه‌ها", "غذا، رنگ، فعالیت و چیز موردعلاقه‌اش را بگوید", "A1", "C2", "KJTSA"),
    ("LIKES_DISLIKES", "دوست داشتن و نداشتن", "نظر خود درباره‌ی چیزها را با دلیل بگوید", "A1", "B1", "KJT"),
    ("DAILY_ROUTINE", "روال روزانه", "روز خود را از صبح تا شب تعریف کند", "A1", "B2", "JTSA"),
    ("TIME_DATE", "ساعت و تاریخ", "ساعت، روز و تاریخ را بگوید و زمان قرار را هماهنگ کند", "A1", "B1", "JTSA"),
    ("FOOD_DRINK", "غذا و نوشیدنی", "غذا و نوشیدنی موردعلاقه را بگوید و سفارش دهد", "A1", "B1", "KJTSA"),
    ("SHOPPING", "خرید", "در فروشگاه بپرسد، انتخاب کند و قیمت را بفهمد", "A1", "B2", "JTSA"),
    ("RESTAURANT", "رستوران", "سفارش دهد، غذا را توصیف کند و صورت‌حساب بپرسد", "A1", "C2", "JTSA"),
    ("NUMBERS_MONEY", "عدد و پول", "عدد، قیمت و مقدار را بگوید و بفهمد", "A1", "A2", "KJT"),
    ("HOBBIES_SPORTS", "سرگرمی و ورزش", "سرگرمی و ورزش خود را توصیف کند", "A1", "B2", "JTSA"),
    ("ABILITIES", "توانایی‌ها", "بگوید چه کاری بلد است و چه کاری بلد نیست", "A1", "A2", "KJT"),
    ("HOME_ROOMS", "خانه و اتاق", "اتاق‌ها و وسایل خانه را توصیف کند", "A1", "A1", "KJ"),
    ("CITY_DIRECTIONS", "شهر و مسیر", "مسیر را بپرسد و توضیح دهد", "A1", "B1", "JTSA"),
    ("WEATHER_SEASONS", "آب‌وهوا و فصل‌ها", "آب‌وهوا را توصیف کند و لباس مناسب را بگوید", "A1", "B1", "KJTSA"),
    ("PAST_EVENTS", "رویدادهای گذشته", "دیروز و تجربه‌های گذشته را تعریف کند", "A2", "B2", "JTSA"),
    ("DESCRIBE_PEOPLE_PLACES", "توصیف آدم و مکان", "آدم‌ها و مکان‌ها را با جزئیات توصیف کند", "A1", "B2", "JTSA"),
    ("COMPARE", "مقایسه", "دو چیز را مقایسه کند و نظر بدهد", "A2", "B2", "JTSA"),
    ("INVITATIONS_PLANS", "دعوت و قرار", "دعوت کند، بپذیرد یا رد کند و قرار بگذارد", "A1", "B2", "KJTSA"),
    ("FUTURE_PLANS", "برنامه‌های آینده", "برنامه‌ها و تصمیم‌هایش را برای آینده بگوید", "A2", "B2", "TSA"),
    ("STORYTELLING", "داستان‌گویی", "داستان کوتاه بسازد و تعریف کند", "A1", "C2", "KJTS"),
    ("MEDIA_CARTOONS", "کارتون و فیلم", "درباره‌ی فیلم یا کارتون موردعلاقه‌اش حرف بزند", "A2", "C2", "JTSA"),
    ("BOOKS", "کتاب", "کتاب را خلاصه و نقد کند", "A2", "C2", "TSA"),
    ("FRIENDS", "دوستان و رابطه", "درباره‌ی دوستان و رابطه‌اش حرف بزند", "A2", "C2", "TSA"),
    ("SCHOOL_STUDY", "مدرسه و درس", "درس‌ها، امتحان‌ها و برنامه‌ی مدرسه را بگوید", "A1", "B2", "JTS"),
    ("TECH_INTERNET", "فناوری", "از ابزارها و اپ‌ها بگوید و مزایا و معایب را توضیح دهد", "A2", "C2", "TSA"),
    ("NATURE_ANIMALS", "طبیعت و حیوانات", "درباره‌ی طبیعت و محیط زیست نظر بدهد", "A2", "C2", "JTSA"),
    ("SCIENCE_SPACE", "علم و فضا", "درباره‌ی موضوع‌های علمی ساده توضیح دهد", "A2", "C2", "JTS"),
    ("CULTURE_HOLIDAYS", "فرهنگ و جشن‌ها", "جشن‌های ایران و جهان را مقایسه کند", "A2", "C2", "JTSA"),
    ("OPINION_DEBATE", "نظر و بحث", "نظر بدهد، دلیل بیاورد و با نظر مخالف برخورد کند", "B1", "C2", "TSA"),
    ("PROBLEM_SOLVING", "حل مسئله", "مشکلی را توضیح دهد و راه‌حل پیشنهاد کند", "A2", "C2", "TSA"),
    ("HEALTH_DOCTOR", "سلامتی و پزشک", "علائم را بگوید و با پزشک صحبت کند", "A2", "C2", "TSA"),
    ("EMERGENCY_HELP", "کمک فوری", "در موقعیت اضطراری کمک بخواهد و موقعیت را توضیح دهد", "A2", "C2", "TSA"),
    ("TRAVEL_AIRPORT", "سفر و فرودگاه", "بلیت، هتل و مسیر سفر را هماهنگ کند", "A2", "C2", "TSA"),
    ("PHONE_MESSAGING", "تلفن و پیام", "تماس بگیرد، پیام بگذارد و پیام را تأیید کند", "A1", "C2", "TSA"),
    ("NEWS_EVENTS", "اخبار و رویداد", "خبر ساده را خلاصه و درباره‌اش نظر بدهد", "B1", "C2", "SA"),
    ("WORK_JOB", "کار و شغل", "شغل خود را معرفی و وظیفه‌هایش را توضیح دهد", "A2", "C2", "SA"),
    ("MEETINGS_PRESENTATION", "جلسه و ارائه", "در جلسه‌ی کاری نظر بدهد و ارائه‌ی کوتاه بدهد", "B1", "C2", "A"),
    ("CAREER_FUTURE", "شغل آینده", "درباره‌ی هدف شغلی و مسیر آینده صحبت کند", "B1", "C2", "SA"),
    ("HOUSING_RENT", "خانه و اجاره", "درباره‌ی اجاره، آپارتمان و قرارداد ساده بپرسد", "B1", "C2", "A"),
    ("SOCIAL_SMALL_TALK", "گفتگوی اجتماعی", "در مهمانی یا جمع گفتگو را شروع و ادامه دهد", "B1", "C2", "SA"),
]

# (variant id, topic id, band code, level, opener, target phrases, style)
VARIANTS = [
    ("INTRO.K.A1", "INTRO", "K", "A1", "My name is…",
     ["My name is…", "I am…", "I like…"], "بازی و تصویر، جمله‌ی یک تا سه کلمه‌ای"),
    ("INTRO.J.A1", "INTRO", "J", "A1", "Hi, my name is…",
     ["I'm…", "I'm… years old.", "I like…"], "دوستانه، جمله‌ی کوتاه"),
    ("INTRO.T.A2", "INTRO", "T", "A2", "Hi! I'm… Let me tell you about me.",
     ["I'm…", "I'm from…", "I like… because…"], "جمله‌ی کامل با دلیل"),
    ("INTRO.S.B1", "INTRO", "S", "B1", "Hi, I'm… A little about me:",
     ["I've been…", "I'm interested in…", "One thing I enjoy is…"], "گفتگوی باز، کمی رسمی"),
    ("INTRO.A.B2", "INTRO", "A", "B2", "Let me introduce myself.",
     ["I work as…", "I'm particularly interested in…", "What I enjoy most is…"], "حرفه‌ای، ساختار شغلی"),
    ("INTRO.A.C1", "INTRO", "A", "C1", "Hi, I'm… and I'd say I'm…",
     ["What I do is…", "What drives me is…", "I tend to…"], "ظریف، اصطلاح‌های رایج"),
    ("INTRO.A.C2", "INTRO", "A", "C2", "Allow me to introduce myself.",
     ["I've spent most of my career in…", "What genuinely sets me apart is…", "I'd put it this way:"],
     "ظریف، دقت در لحن و کنایه‌ی ملایم"),
]
