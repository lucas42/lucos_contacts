---
description: How to update and compile translations
---
The project uses Django's translation system for English and Irish (Gaeilge).

### Steps to update translations:

1. **Extract new strings**:
   Run this command from the project root to scan for new strings wrapped in `{% trans %}` or `gettext()`:
   ```bash
   docker compose run --rm -v $(pwd)/app:/usr/src/app app django-admin makemessages --all --ignore=.venv
   ```
   *Note: Mounting the volume (`-v`) ensures the updated `.po` files are saved back to your host machine.*

2. **Translate the strings**:
   Open `app/locale/ga/LC_MESSAGES/django.po` and look for `msgid` entries with empty `msgstr` or `#, fuzzy` flags. Add the Irish translations.

3. **Compile the messages**:
   Run this to generate the binary `.mo` files:
   ```bash
   docker compose run --rm -v $(pwd)/app:/usr/src/app app django-admin compilemessages --ignore=.venv
   ```

4. **Verify**:
   Restart the application or rebuild the container to see the changes.
   ```bash
   docker compose up --build
   ```
