# Account menu and personal details (website header)

This note is for any developer or AI coding agent working on the website. It describes what the signed-in header does, where the code lives, and how the pieces connect. It does not depend on any one tool.

## What the user sees

- **Signed out:** the header shows only the "ورود" button, linking to `/login`. The login page lists, one per line under the form: "ورود با کد پیامکی", "رمز عبور را فراموش کرده‌ام", and "ثبت‌نام".
- **Signed in:** the header shows the signed-in person's name and a round profile button. There is no parent panel link. The button shows the profile photo, or a plain silhouette when there is none. There is no "یادگیری من" link in the top row.
- **Second header row (signed in only):** the person's own items, filled by `initSiteHeader` from `#memberNav`. For every signed-in person: جلسه, گفتگوی آزاد, لهجه, خودت رو محک بزن, گزارش‌ها, کمک‌آموزشی, پلن و اعتبار, اطلاعات آموزشی, تعیین سطح, and «دانش‌آموزان من» once at least one adult has chosen them as a teacher. The item for the current page gets `aria-current="page"` and a filled style.
  - «جلسه» and the other learning items open the learner page (`/student`, with `?tab=` for the tab). Every signed-in person has a learner profile, so there is no separate «آموزش من» item. If a learner profile is missing, `startOwnLearning` in `common.js` first calls `POST /v1/web/user/self`, then the learner page opens.
  - «پرداخت‌ها» (adults) opens `/payments`, a plain list of the adult's payments from `GET /v1/web/billing/payments`. Learners keep their own payments tab.
  - «پلن و اعتبار» opens `/plan`. Its «خرید یا تمدید پلن» button does nothing yet; what it should do is still to be decided.
- **Learning tabs:** the `.tabs` nav in `student.html` stays hidden (`#appView > .tabs`). The side menu is the tab menu. On the learner page an entry clicks the page's own tab button, so no reload happens, and `history.replaceState` updates `?tab=`. The entry marked `aria-current` follows the active tab (a `MutationObserver` on `.tabs`). On the free talk page the tabs are not shown, so entries are normal links to `/student?tab=…`. The payments tab has its own main-row item and is not in the side menu.
- **Profile menu** (opens from the round button; closes on outside click or Escape):
  - اطلاعات شخصی / Personal details: opens the profile dialog (`accInfoDialog`): photo, name, mobile (read-only, used to sign in), email, age and gender. Age and gender are also copied to the learner profile when it exists.
  - تغییر رمز عبور / Change password: opens the password dialog.
  - خروج / Sign out: asks for confirmation first (a thank-you line, then the question). Then it ends the sign-in on this browser (every role cookie).
  - خروج از همه‌ی دستگاه‌ها / Sign out of all devices: only for an adult (the one website cookie). Asks for confirmation first, then ends every sign-in for the adult and their own learner profile.

"Sign out of all devices" appears only in this menu. It is not on any page body.

- Dialogs (personal details, password, sign-out confirmation) close on the Close or Cancel button, or on a click on the grey area outside the box.
- The personal details dialog is wider on desktop (`account-dialog-wide`).

## Plan and credit page

- Menu item «پلن و اعتبار» (adults only), page `/plan` (`static/plan.html`, `static/js/plan.js`).
- Shows the plan name, the start of the current paid period, the expiry date and the days left.
- Data: `GET /v1/web/billing/plan`. The plan name comes from the last confirmed payment. The start date is `guardians.plan_started_at`, set in `confirm_payment` when no plan is active. A renewal before the old plan ends keeps that date.

## Personal details fields

| Field | Stored in | Notes |
|---|---|---|
| Full name | `guardians.full_name` | One field. There is no separate first and last name. |
| Mobile number | `guardians.phone` | Read only. It is the sign-in, so it cannot change here. |
| Email | `guardians.email` | Optional. Lower-cased. Must be unique across adults. |
| Age | `guardians.age` | Optional. Integer 18 to 120. |
| Gender | `guardians.gender` | Optional. `female` (زن) or `male` (مرد). Empty means not chosen. The select shows a disabled «انتخاب کنید» placeholder for empty. Older rows may hold `other`; the form shows them as empty. |
| Photo | `guardians.avatar_data` | Optional. A `data:image/jpeg|png|webp;base64,...` string, at most 200,000 characters. |

The browser resizes a picked photo to a 256 px square JPEG (`readPhoto` in `common.js`) before it is sent, so the stored value stays small.

## Endpoints (all under `/v1`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/web/user/profile` | Read the adult's profile. Works with either sign-in cookie. |
| PUT | `/web/user/profile` | Update the profile. Only fields that are sent change. An empty `email` or `avatar` clears it. `gender: null` clears it. |
| POST | `/web/user/password` | Change password. Needs the current password. |
| POST | `/web/user/logout-all` | Sign out everywhere. Needs the adult cookie. |
| POST | `/web/logout` | Sign out on this browser. |
| GET | `/web/me` | Who is signed in (name, plan status, own learning). |

Validation lives in `src/zaban/account.py` (`ProfileUpdate`, `EMAIL_PATTERN`, `AVATAR_PATTERN`). Errors use the server's English detail strings. The browser turns them into Persian or English sentences through `ERROR_TEXT` and `ERROR_TEXT_EN` in `common.js`. A new server message needs an entry in both lists, or it shows the generic text.

## Where the code is

- `src/zaban/static/partials/header.html`: the header markup and the two `<dialog>` forms (`accInfoDialog`, `accPasswordDialog`). The header partial is injected into every page by `_page` in `main.py`.
- `src/zaban/static/js/common.js`:
  - `initSiteHeader()`: checks sign-in with `/web/me`, draws the signed-in header, and draws the second row. It can run again. The listeners are wired once (`headerWired`).
  - `buildAccountMenu()`: the round button and its menu.
  - `openPersonalDetails()`, `setupAccountForms()`, `readPhoto()`, `signOut()`, `signOutEverywhere()`.
- `src/zaban/static/css/app.css`: header and menu styles, search for `account-menu`, `account-dialog`, `avatar-`.
- `src/zaban/static/js/login.js` and `student.js`: their `login()` calls `Z.initSiteHeader()` after a successful sign-in. The header is drawn as a guest on page load, so this call is what shows the menu without a refresh.
- `src/zaban/static/profile.html` and `js/profile.js`: an older profile page with a name form and a password form. It still works, because `PUT /web/user/profile` accepts a name alone. It duplicates the header dialogs, so it may be removed later.
- Database: `src/zaban/models.py` (`Guardian`), and `ADDED_COLUMNS` in `src/zaban/db.py`. The new columns are added to an existing database at startup.

## Element IDs

The dialog controls use the `acc` prefix (`accName`, `accEmail`, `accAge`, `accGender`, `accInfoForm`, `accAvatarFile`, `accPwCurrent`...). Page scripts also use `infoForm`, `infoName` and `passwordForm`, so the prefix stops the two from clashing. Do not rename `acc*` back to the generic names.

## Testing

- Backend: `tests/test_adult_profile.py` covers the profile, partial saves, validation, the unique email rule and password change. Run it with `pytest tests/test_adult_profile.py`.
- Full backend suite: `pytest`.
- Browser: the sign-in flow was checked with real clicks on the Docker build (port 8020). Sign-in updates the header without a reload. The menu opens and closes.
- Static files are copied into the Docker image at build time. After a change to any `static/` file, rebuild with `docker compose build --no-cache app`, then `docker compose up -d --force-recreate app`, then check with curl that the new text is served. Browsers may keep an old `common.js`, so a hard refresh (Ctrl+F5) may be needed.

## Known gaps

- The name is one field. A first name and last name split would need a migration and changes to every place that reads `full_name`.
- Changing the password does not end other sign-ins. Only "sign out of all devices" does that.
- The phone number cannot be changed. Changing it needs an SMS check.

## Layout and menu (current)

- **Shell (`/app`):** member pages open in a frame below the header and the side menu, so those stay in place while the page changes. `shell.html` and `js/shell.js` build it; `common.js` decides which pages are member pages (`MEMBER_PATHS`). A member page opened on its own address moves to `/app?p=<page>`. Pages inside the frame hide their own header and side menu (`html.framed`). Sign-in, sign-out and payment navigate the whole window (`Z.go`).
- **Phone menu:** the bar shows four items (جلسه, گفتگوی آزاد, آزمون‌ها, گزارش‌ها) and an icon button with three lines. The button opens a sheet with the other items, on the side of the button (in Persian the left side). The sheet closes on a tap outside it, on a tap inside the frame, or on Escape. The button is marked current only when the open page is in the sheet.
- The test item is called «آزمون‌ها» everywhere.
- The header shows the profile photo first and the name after it. The sign-in buttons stay hidden until the visitor is known (`data-state="loading"`).
- Adults only. There are no child accounts. Learning is for the adult, through `POST /v1/web/user/self`.
- Guests see one «ورود» link to `/login`. The header has no sign-in menu.
- Signed in, the public links are hidden and the header is one row: logo, greeting and the profile button.
- The side menu (`nav#memberNav`, `app-side`, built by `initSiteHeader`) holds one level with no sub-lists: جلسه, گفتگوی آزاد, لهجه, خودت رو محک بزن, گزارش‌ها, کمک‌آموزشی, پلن و اعتبار, اطلاعات آموزشی, تعیین سطح, and دانش‌آموزان من when the person is a teacher. «اطلاعات آموزشی» is a page of its own, `/learning-info` (`learning-info.html`, `js/learning-info.js`), like «تعیین سطح»: goal, how the teacher should talk, the teacher's style, one sample sentence, anything else. The levels are not on this page any more: they show on the reports page, and are chosen on «تعیین سطح». The goal is saved on the adult's profile, the rest on the learner profile. The five skill levels show here: listening, speaking (with its five criteria), writing, reading, and grammar and vocabulary. Listening, reading and grammar change through their tests and the «تعیین سطح» page. Speaking and writing can be chosen until the first lesson; after that they are read-only (`speaking_locked` in `GET /v1/web/student/details`) and change only through lessons and tests. On the learner page each learning entry clicks the page's own tab and the marked entry follows the active tab. On the free talk page an entry opens the tab's own address (`/student?tab=…`).
- On desktop the side menu is a column beside the content. On a phone (up to 760 px) it is a bar at the bottom with the same items, each in an equal share of the width. With the current number of items the labels are tight and still need a look on a phone.
- Tenant API keys manage students through `/v1/students` (`require_manager` accepts only API keys). The admin students list shows every learner, with `kind` set to `self` for an adult learning for themself and `tenant` for a learner from a customer's API.

## Teacher and students

- Each adult has one referral code (`guardians.referral_code`). The same code is the teacher code: anyone who enters it can choose that adult as their teacher.
- Profile menu «تعیین مربی» (`accTeacherDialog` in `partials/header.html`, logic in `common.js`): shows the adult's own code, the current teacher, and lets them look up a code, confirm it, and save. Removing the teacher is immediate.
- Choosing a teacher is stored in `guardians.teacher_id`. One teacher per adult, no limit on students per teacher.
- Endpoints (`src/zaban/teaching.py`): `GET/PUT/DELETE /v1/web/user/teacher`, `POST /v1/web/user/teacher/lookup`, `GET /v1/web/user/students`, `GET /v1/web/user/students/{id}/progress` and `/report`. A teacher can read only the adults whose `teacher_id` is theirs; anyone else gets 404.
- «دانش‌آموزان من» (`/students`, `static/students.html`, `static/js/students.js`) appears in the header only when `/v1/web/me` reports at least one student.
