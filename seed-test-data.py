"""
seed_test_data.py — Populate the database with a test user and 90 days of habit history.

Usage:
    python seed_test_data.py

This will:
  - Create a test user (username: testuser, password: password123)
  - Create 4 sample habits with varied schedules
  - Fill in realistic (randomised) checkbox data for the past 90 days

Run from the project root directory. Safe to re-run — it skips creation if
the test user already exists, but will add any missing checkbox records.
"""

import random
from datetime import date, timedelta
from werkzeug.security import generate_password_hash

# Import the app and models directly so we share the same DB config
from app import app, db, User, Habit, Checkbox, Settings

# ── Configuration ──────────────────────────────────────────────────────────────

TEST_USERNAME = "testuser"
TEST_PASSWORD = "password123"
TEST_NAME     = "Test User"

# Habits: (name, frequency_appdays, time_of_day, notes, completion_rate)
# App day numbering: 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat
HABITS = [
    {
        "name": "Morning Run",
        "frequency": [1, 3, 5, 6],       # Mon, Wed, Fri, Sat
        "time_of_day": "7:00 AM",
        "notes": "At least 30 minutes",
        "rate": 0.80,                     # completed ~80% of scheduled days
    },
    {
        "name": "Read 20 Pages",
        "frequency": [0, 1, 2, 3, 4, 5, 6],  # Every day
        "time_of_day": "9:00 PM",
        "notes": "Any book counts",
        "rate": 0.65,
    },
    {
        "name": "Meditate",
        "frequency": [1, 2, 3, 4, 5],    # Mon–Fri
        "time_of_day": "8:00 AM",
        "notes": "10 minutes minimum",
        "rate": 0.70,
    },
    {
        "name": "Meal Prep",
        "frequency": [0, 6],             # Sun, Sat
        "time_of_day": "12:00 PM",
        "notes": "Prep for the week ahead",
        "rate": 0.90,
    },
]

DAYS_BACK = 90  # how many days of history to generate

# ── Seed logic ─────────────────────────────────────────────────────────────────

with app.app_context():
    # 1. Get or create test user
    user = User.query.filter_by(username=TEST_USERNAME).first()
    if user is None:
        user = User(
            username=TEST_USERNAME,
            name=TEST_NAME,
            hash=generate_password_hash(TEST_PASSWORD),
        )
        db.session.add(user)
        db.session.flush()
        db.session.refresh(user)
        print(f"Created user: {TEST_USERNAME}")
    else:
        print(f"User '{TEST_USERNAME}' already exists — skipping user creation.")

    # 2. Create habits if they don't exist for this user
    existing_habits = Habit.query.filter_by(user_id=user.id).all()
    existing_names  = {h.description for h in existing_habits}

    created_habits = list(existing_habits)
    for h_def in HABITS:
        if h_def["name"] not in existing_names:
            freq_str = " ".join(str(d) for d in h_def["frequency"])
            habit = Habit(
                description=h_def["name"],
                frequency=freq_str,
                time_of_day=h_def["time_of_day"],
                notes=h_def["notes"],
                user_id=user.id,
            )
            db.session.add(habit)
            db.session.flush()
            db.session.refresh(habit)
            created_habits.append(habit)
            print(f"  Created habit: {h_def['name']}")
        else:
            print(f"  Habit '{h_def['name']}' already exists — skipping.")

    db.session.commit()

    # Build a lookup: habit description -> (habit object, completion rate)
    habit_rate = {}
    for h_def in HABITS:
        habit_obj = next((h for h in created_habits if h.description == h_def["name"]), None)
        if habit_obj:
            habit_rate[habit_obj.description] = (habit_obj, h_def["rate"])

    # 3. Generate checkbox records for the past DAYS_BACK days
    today     = date.today()
    start_day = today - timedelta(days=DAYS_BACK)

    added = 0
    skipped = 0

    current = start_day
    while current <= today:
        date_str = current.isoformat()
        # App weekday: 0=Sun..6=Sat; Python weekday: Mon=0..Sun=6
        app_day = (current.weekday() + 1) % 7

        for desc, (habit, rate) in habit_rate.items():
            scheduled_days = [int(d) for d in habit.frequency.split()]
            if app_day not in scheduled_days:
                current = current + timedelta(days=1) if False else current
                continue  # habit not scheduled today

            cb_id = f"{app_day} {habit.id} {date_str}"

            # Skip if already exists
            if Checkbox.query.get(cb_id) is not None:
                skipped += 1
                continue

            # Randomly mark as checked based on completion rate
            # Make it slightly less likely for very recent days (feels more natural)
            effective_rate = rate * 0.5 if current == today else rate
            value = "checked" if random.random() < effective_rate else ""

            cb = Checkbox(
                id=cb_id,
                value=value,
                user_id=user.id,
                date=date_str,
            )
            db.session.add(cb)
            added += 1

        current += timedelta(days=1)

    db.session.commit()

    # 4. Ensure settings row exists
    if not Settings.query.filter_by(user_id=user.id).first():
        db.session.add(Settings(user_id=user.id))
        db.session.commit()

    print(f"\nDone! Added {added} checkbox records, skipped {skipped} existing.")
    print(f"\nLog in with:  username='{TEST_USERNAME}'  password='{TEST_PASSWORD}'")