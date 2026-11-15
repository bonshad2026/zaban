# The starting curriculum: topics, and the variants written so far. It is copied into the database once,
# on first start. After that the administrator edits the database, so this file is only the first version.
# The text follows docs/curriculum.md. The product serves adults only, so every topic and variant uses band A.

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

# Age band codes used in the curriculum, and the age_band value each code maps to in the student records.
BAND_CODES = {"A": "adult"}
BAND_LABELS = {"A": "بزرگسال"}

# (id, title, goal, first level, last level, age band codes)
TOPICS = [
    ("INTRO", "معرفی خود", "خودش را معرفی کند و چند جمله درباره‌ی خودش بگوید", "A1", "C2", "A"),
    ("GREET", "احوال‌پرسی و گفتگوی کوتاه", "سلام کند و گفتگوی کوتاه روزانه را شروع و تمام کند", "A1", "B2", "A"),
    ("FEELINGS", "احساسات", "احساس خود را بگوید و دلیلش را توضیح دهد", "A1", "B2", "A"),
    ("FAVORITES", "علاقه‌ها", "غذا، رنگ، فعالیت و چیز موردعلاقه‌اش را بگوید", "A1", "C2", "A"),
    ("DAILY_ROUTINE", "روال روزانه", "روز خود را از صبح تا شب تعریف کند", "A1", "B2", "A"),
    ("TIME_DATE", "ساعت و تاریخ", "ساعت، روز و تاریخ را بگوید و زمان قرار را هماهنگ کند", "A1", "B1", "A"),
    ("FOOD_DRINK", "غذا و نوشیدنی", "غذا و نوشیدنی موردعلاقه را بگوید و سفارش دهد", "A1", "B1", "A"),
    ("SHOPPING", "خرید", "در فروشگاه بپرسد، انتخاب کند و قیمت را بفهمد", "A1", "B2", "A"),
    ("RESTAURANT", "رستوران", "سفارش دهد، غذا را توصیف کند و صورت‌حساب بپرسد", "A1", "C2", "A"),
    ("HOBBIES_SPORTS", "سرگرمی و ورزش", "سرگرمی و ورزش خود را توصیف کند", "A1", "B2", "A"),
    ("CITY_DIRECTIONS", "شهر و مسیر", "مسیر را بپرسد و توضیح دهد", "A1", "B1", "A"),
    ("WEATHER_SEASONS", "آب‌وهوا و فصل‌ها", "آب‌وهوا را توصیف کند و لباس مناسب را بگوید", "A1", "B1", "A"),
    ("PAST_EVENTS", "رویدادهای گذشته", "دیروز و تجربه‌های گذشته را تعریف کند", "A2", "B2", "A"),
    ("DESCRIBE_PEOPLE_PLACES", "توصیف آدم و مکان", "آدم‌ها و مکان‌ها را با جزئیات توصیف کند", "A1", "B2", "A"),
    ("COMPARE", "مقایسه", "دو چیز را مقایسه کند و نظر بدهد", "A2", "B2", "A"),
    ("INVITATIONS_PLANS", "دعوت و قرار", "دعوت کند، بپذیرد یا رد کند و قرار بگذارد", "A1", "B2", "A"),
    ("FUTURE_PLANS", "برنامه‌های آینده", "برنامه‌ها و تصمیم‌هایش را برای آینده بگوید", "A2", "B2", "A"),
    ("MEDIA_CARTOONS", "کارتون و فیلم", "درباره‌ی فیلم یا کارتون موردعلاقه‌اش حرف بزند", "A2", "C2", "A"),
    ("BOOKS", "کتاب", "کتاب را خلاصه و نقد کند", "A2", "C2", "A"),
    ("FRIENDS", "دوستان و رابطه", "درباره‌ی دوستان و رابطه‌اش حرف بزند", "A2", "C2", "A"),
    ("TECH_INTERNET", "فناوری", "از ابزارها و اپ‌ها بگوید و مزایا و معایب را توضیح دهد", "A2", "C2", "A"),
    ("NATURE_ANIMALS", "طبیعت و حیوانات", "درباره‌ی طبیعت و محیط زیست نظر بدهد", "A2", "C2", "A"),
    ("CULTURE_HOLIDAYS", "فرهنگ و جشن‌ها", "جشن‌های ایران و جهان را مقایسه کند", "A2", "C2", "A"),
    ("OPINION_DEBATE", "نظر و بحث", "نظر بدهد، دلیل بیاورد و با نظر مخالف برخورد کند", "B1", "C2", "A"),
    ("PROBLEM_SOLVING", "حل مسئله", "مشکلی را توضیح دهد و راه‌حل پیشنهاد کند", "A2", "C2", "A"),
    ("HEALTH_DOCTOR", "سلامتی و پزشک", "علائم را بگوید و با پزشک صحبت کند", "A2", "C2", "A"),
    ("EMERGENCY_HELP", "کمک فوری", "در موقعیت اضطراری کمک بخواهد و موقعیت را توضیح دهد", "A2", "C2", "A"),
    ("TRAVEL_AIRPORT", "سفر و فرودگاه", "بلیت، هتل و مسیر سفر را هماهنگ کند", "A2", "C2", "A"),
    ("PHONE_MESSAGING", "تلفن و پیام", "تماس بگیرد، پیام بگذارد و پیام را تأیید کند", "A1", "C2", "A"),
    ("NEWS_EVENTS", "اخبار و رویداد", "خبر ساده را خلاصه و درباره‌اش نظر بدهد", "B1", "C2", "A"),
    ("WORK_JOB", "کار و شغل", "شغل خود را معرفی و وظیفه‌هایش را توضیح دهد", "A2", "C2", "A"),
    ("MEETINGS_PRESENTATION", "جلسه و ارائه", "در جلسه‌ی کاری نظر بدهد و ارائه‌ی کوتاه بدهد", "B1", "C2", "A"),
    ("CAREER_FUTURE", "شغل آینده", "درباره‌ی هدف شغلی و مسیر آینده صحبت کند", "B1", "C2", "A"),
    ("HOUSING_RENT", "خانه و اجاره", "درباره‌ی اجاره، آپارتمان و قرارداد ساده بپرسد", "B1", "C2", "A"),
    ("SOCIAL_SMALL_TALK", "گفتگوی اجتماعی", "در مهمانی یا جمع گفتگو را شروع و ادامه دهد", "B1", "C2", "A"),
]

# (variant id, topic id, band code, level, opener, target phrases, style)
VARIANTS = [
    ("INTRO.A.B2", "INTRO", "A", "B2", "Let me introduce myself.",
     ["I work as…", "I'm particularly interested in…", "What I enjoy most is…"], "حرفه‌ای، ساختار شغلی"),
    ("INTRO.A.C1", "INTRO", "A", "C1", "Hi, I'm… and I'd say I'm…",
     ["What I do is…", "What drives me is…", "I tend to…"], "ظریف، اصطلاح‌های رایج"),
    ("INTRO.A.C2", "INTRO", "A", "C2", "Allow me to introduce myself.",
     ["I've spent most of my career in…", "What genuinely sets me apart is…", "I'd put it this way:"],
     "ظریف، دقت در لحن و کنایه‌ی ملایم"),
]

# First batch of versions: FOOD_DRINK and DAILY_ROUTINE for adults.
# The phrases are a starting point. They are meant to be edited in the administrator page before wide use.
VARIANTS += [
    # FOOD_DRINK: A; A1 to B1
    ("FOOD_DRINK.A.A1", "FOOD_DRINK", "A", "A1", "Hello, what do you like to eat?", ["I like…", "I don't like…", "Could I have…, please?"], "ساده و مؤدبانه"),
    ("FOOD_DRINK.A.A2", "FOOD_DRINK", "A", "A2", "What do you usually order when you go out?", ["I usually order…", "It's… and I like it because…", "Could I have…?"], "کافه و رستوران، جمله‌ی کامل"),
    ("FOOD_DRINK.A.B1", "FOOD_DRINK", "A", "B1", "Do you enjoy cooking, or do you prefer eating out?", ["I enjoy cooking because…", "I'd rather… than…", "It depends on…"], "گفتگوی روزمره‌ی بزرگسال"),
    # DAILY_ROUTINE: A; A1 to B2
    ("DAILY_ROUTINE.A.A1", "DAILY_ROUTINE", "A", "A1", "Hello, what does your day usually look like?", ["I wake up at…", "I start work at…", "I finish at…"], "ساده و مؤدبانه"),
    ("DAILY_ROUTINE.A.A2", "DAILY_ROUTINE", "A", "A2", "What's your daily routine at work?", ["I usually start at…", "In the afternoon, I…", "I finish… and then I…"], "کار روزانه"),
    ("DAILY_ROUTINE.A.B1", "DAILY_ROUTINE", "A", "B1", "How do you fit everything into your day?", ["I usually… before work.", "I try to… in the evening.", "It's hard to… when…"], "گفتگوی روزمره‌ی بزرگسال"),
    ("DAILY_ROUTINE.A.B2", "DAILY_ROUTINE", "A", "B2", "How do you manage a busy schedule?", ["I usually plan… the night before.", "What helps me is…", "The hardest part is… so I…"], "برنامه‌ریزی و استدلال"),
]
