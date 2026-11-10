# Account menu and personal details (website header)

This note is for any developer or AI coding agent working on the website. It describes what the signed-in header does, where the code lives, and how the pieces connect. It does not depend on any one tool.

## What the user sees

- **Signed out:** the header shows the "ورود" menu (parent or learner) and the "ثبت‌نام" button.
- **Signed in:** the header shows the signed-in person's name, the "پنل والد" and/or "یادگیری من" links, and a round profile button. The button shows the profile photo, or a plain silhouette when there is none.
- **Second header row (signed in only):** the person's own links (children, progress, requests, payments). Filled by `initSiteHeader` from `#memberNav`.
- **Profile menu** (opens from the round button; closes on outside click or Escape):
  - اطلاعات شخصی / Personal details: opens the personal details dialog.
  - تغییر رمز عبور / Change password: opens the password dialog.
  - خروج / Sign out: ends the sign-in on this browser (every role cookie).
  - خروج از همه‌ی دستگاه‌ها / Sign out of all devices: only for an adult (`zaban_parent` cookie). Ends every sign-in for the adult and their own learner profile.

"Sign out of all devices" appears only in this menu. It is not on any page body.

## Personal details fields

| Field | Stored in | Notes |
|---|---|---|
| Full name | `guardians.full_name` | One field. There is no separate first and last name. |
| Mobile number | `guardians.phone` | Read only. It is the sign-in, so it cannot change here. |
| Email | `guardians.email` | Optional. Lower-cased. Must be unique across adults. |
| Age | `guardians.age` | Optional. Integer 18 to 120. |
| Gender | `guardians.gender` | Optional. `female`, `male` or `other`. Empty means not stated. |
| Photo | `guardians.avatar_data` | Optional. A `data:image/jpeg|png|webp;base64,...` string, at most 200,000 characters. |

The browser resizes a picked photo to a 256 px square JPEG (`readPhoto` in `common.js`) before it is sent, so the stored value stays small.

## Endpoints (all under `/v1`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/web/user/profile` | Read the adult's profile. Works with either sign-in cookie. |
| PUT | `/web/user/profile` | Update the profile. Only fields that are sent change. An empty `email` or `avatar` clears it. `gender: null` clears it. |
| POST | `/web/user/password` | Change password. Needs the current password. |
| POST | `/web/user/logout-all` | Sign out everywhere. Needs the adult cookie. |
| POST | `/web/logout?role=parent\|student` | Sign out one role on this browser. |
| GET | `/web/me?role=parent\|student` | Who is signed in for that role (name, plan status). |

Validation lives in `src/zaban/account.py` (`ProfileUpdate`, `EMAIL_PATTERN`, `AVATAR_PATTERN`). Errors use the server's English detail strings. The browser turns them into Persian or English sentences through `ERROR_TEXT` and `ERROR_TEXT_EN` in `common.js`. A new server message needs an entry in both lists, or it shows the generic text.

## Where the code is

- `src/zaban/static/partials/header.html`: the header markup and the two `<dialog>` forms (`accInfoDialog`, `accPasswordDialog`). The header partial is injected into every page by `_page` in `main.py`.
- `src/zaban/static/js/common.js`:
  - `initSiteHeader()`: checks sign-in with `/web/me`, draws the signed-in header, and draws the second row. It can run again. The listeners are wired once (`headerWired`).
  - `buildAccountMenu()`: the round button and its menu.
  - `openPersonalDetails()`, `setupAccountForms()`, `readPhoto()`, `signOut()`, `signOutEverywhere()`.
- `src/zaban/static/css/app.css`: header and menu styles, search for `account-menu`, `account-dialog`, `avatar-`.
- `src/zaban/static/js/parent.js` and `student.js`: their `login()` calls `Z.initSiteHeader()` after a successful sign-in. The header is drawn as a guest on page load, so this call is what shows the menu without a refresh.
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
