import os

from flask import Flask, render_template, request, redirect, session, flash, jsonify
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import date, timedelta
from time import strftime
import calendar

app = Flask(__name__)

app.config["TEMPLATES_AUTO_RELOAD"] = True

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///habit_tracker.db'
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    hash = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return '<User %r>' % self.username


class Habit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(100), nullable=False)
    frequency = db.Column(db.String(14), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    notes = db.Column(db.Text)

    def __repr__(self):
        return '<Habit %r>' % self.id


class Checkbox(db.Model):
    id = db.Column(db.String(20), primary_key=True)
    value = db.Column(db.String(8), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    time_of_day = db.Column(db.String(20), nullable=False, default="9:00 AM")
    date = db.Column(db.String(10), nullable=False, default="")

    def __repr__(self):
        return '<Check %r>' % self.id

with app.app_context():     
    db.create_all()

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


days = {
    0: "Sun",
    1: "Mon",
    2: "Tues",
    3: "Wed",
    4: "Thurs",
    5: "Fri",
    6: "Sat",
}

time_options = [
    "6:00 AM", "6:30 AM",
    "7:00 AM", "7:30 AM",
    "8:00 AM", "8:30 AM",
    "9:00 AM", "9:30 AM",
    "10:00 AM", "10:30 AM",
    "11:00 AM", "11:30 AM",
    "12:00 PM", "12:30 PM",
    "1:00 PM", "1:30 PM",
    "2:00 PM", "2:30 PM",
    "3:00 PM", "3:30 PM",
    "4:00 PM", "4:30 PM",
    "5:00 PM", "5:30 PM",
    "6:00 PM", "6:30 PM",
    "7:00 PM", "7:30 PM",
    "8:00 PM", "8:30 PM",
    "9:00 PM", "9:30 PM",
    "10:00 PM"
]


def habit_table(habits):
    return [
        {
            "id": habit.id,
            "name": habit.description,
            "frequency": [int(day) for day in habit.frequency.split()],
            "notes": habit.notes
            "time_of_day": habit.time_of_day
        } for habit in habits
    ]


def checkboxes(checks):
    return {check.id: check.value for check in checks}


@app.route("/", methods=["GET", "POST"])
def index():
    if session.get("user_id") is None:
        return redirect("/login")

    user = User.query.filter_by(id=session["user_id"]).first()
    if user is None:
        session.clear()
        return redirect("/login")
    name = user.name
    habits = habit_table(Habit.query.filter_by(
        user_id=session["user_id"]).all())
    today = date.today()
    today_str = today.isoformat()
    formatted_date = today.strftime("%d %B, %Y")

    # Build a map of weekday number -> actual calendar date for this week
    # days dict uses 0=Sun,1=Mon,...,6=Sat (matching JS getDay())
    # Find the Sunday that starts this week
    week_start = today - timedelta(days=today.weekday() + 1) if today.weekday() != 6 else today
    # weekday(): Mon=0...Sun=6, so Sunday offset = -(weekday+1), but if today is Sunday offset=0
    days_to_sunday = (today.weekday() + 1) % 7
    week_start = today - timedelta(days=days_to_sunday)
    # day_dates[day_num] = "YYYY-MM-DD" for each column (0=Sun ... 6=Sat)
    day_dates = {i: (week_start + timedelta(days=i)).isoformat() for i in range(7)}

    if request.method == "POST":
        if request.json.get("type") == "clear":
            # Clear all checkboxes for this entire week
            week_dates = list(day_dates.values())
            checks_to_clear = Checkbox.query.filter(
                Checkbox.user_id == session["user_id"],
                Checkbox.date.in_(week_dates)
            ).all()
            for checkbox in checks_to_clear:
                checkbox.value = ""
        else:
            cb_id = request.json.get("id")
            cb_date = request.json.get("date", today_str)
            checkbox = Checkbox.query.get(cb_id)
            if checkbox is None:
                checkbox = Checkbox(id=cb_id, value="", user_id=session["user_id"], date=cb_date)
                db.session.add(checkbox)
            checkbox.value = request.json.get("value")
        db.session.commit()

    # Load checkboxes for the whole week
    week_dates = list(day_dates.values())
    checks = checkboxes(Checkbox.query.filter(
        Checkbox.user_id == session["user_id"],
        Checkbox.date.in_(week_dates)
    ).all())
    return render_template('index.html', name=name, days=days, habits=habits,
                           date=formatted_date, checks=checks,
                           today_str=today_str, day_dates=day_dates)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not request.form.get("username") or not request.form.get("password"):
            flash("Must provide username and password...")
            return redirect("/login")
        user = User.query.filter_by(
            username=request.form.get("username")).first()
        if user is None or not check_password_hash(user.hash, request.form.get("password")):
            flash("Invalid username and/or password...")
            return redirect("/login")
        session["user_id"] = user.id
        return redirect("/")
    else:
        return render_template("login.html")


@app.route("/register", methods=["POST", "GET"])
def register():
    if request.method == "POST":
        if not request.form.get("name") or not request.form.get("username") or not request.form.get("password") or not request.form.get("confirmation"):
            flash("All fields must be filled...")
            return redirect("/register")
        usernameNotAvailable = User.query.filter_by(
            username=request.form.get("username")).first()
        if usernameNotAvailable != None:
            flash("Username not available...")
            return redirect("/register")
        if request.form.get("password") != request.form.get("confirmation"):
            flash("Passwords did not match...")
            return redirect("/register")
        user = User(name=request.form.get("name"), username=request.form.get(
            "username"), hash=generate_password_hash(request.form.get("password")))
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user.id
        return redirect("/")
    else:
        return render_template("register.html")


def habits_display(habits):
    return [
        {
            "id": habit.id,
            "name": habit.description,
            "frequency": " - ".join([days[int(day)] for day in habit.frequency.split()]),
            "notes": habit.notes        
            "time_of_day": habit.time_of_day
        } for habit in habits
    ]


@app.route("/habits")
def habits():
    if session.get("user_id") is None:
        return redirect("/login")
    hab_dis = habits_display(Habit.query.filter_by(
        user_id=session["user_id"]).all())
    return render_template("habits.html", habits=hab_dis)


@app.route("/new-habit", methods=["POST", "GET"])
def new_habit():
    if session.get("user_id") is None:
        return redirect("/login")
    if request.method == "POST":
        if not request.form.get("name") or not request.form.getlist("frequency"):
            flash("Invalid name and/or frequency...")
            return redirect("/new-habit")
        frequency_str = " ".join(request.form.getlist("frequency"))
        notes = request.form.get("notes")
        habit = Habit(description=request.form.get("name"),
                      frequency=frequency_str, notes=notes, time_of_day=request.form.get("time_of_day"), user_id=session["user_id"])
        db.session.add(habit)
        db.session.flush()
        db.session.refresh(habit)
        today_str = date.today().isoformat()
        for day in days:
            checkbox = Checkbox(id=str(day)+" "+str(habit.id)+" "+today_str, value="", user_id=session["user_id"], date=today_str)
            db.session.add(checkbox)
        db.session.commit()
        
        return redirect("/")
    else:
        return render_template("new-habit.html", days=days, time_options=time_options)


def habit_edit(habit):
    return {
        "id": habit.id,
        "name": habit.description,
        "time_of_day": habit.time_of_day,
        "frequency": ["checked" if str(i) in habit.frequency.split() else "" for i in range(7)],
        "notes": habit.notes
    }


@app.route("/edit/<int:id>", methods=["POST", "GET"])
def edit(id):
    if session.get("user_id") is None:
        return redirect("/login")
    habit = Habit.query.get_or_404(id)
    if request.method == "POST":
        if not request.form.get("name") or not request.form.getlist("frequency"):
            flash("Invalid name and/or frequency...")
            return redirect("/edit/"+str(id))
        habit.description = request.form.get("name")
        frequency_str = " ".join(request.form.getlist("frequency"))
        habit.frequency = frequency_str
        habit.notes = request.form.get("notes")
        habit.time_of_day = request.form.get("time_of_day")
        try:
            db.session.commit()
            return redirect("/")
        except:
            flash("There was an error editing the habit...")
            return redirect("/")
    else:
        return render_template("edit.html", habit=habit_edit(habit), days=days, time_options=time_options)


@app.route("/delete/<int:id>")
def delete(id):
    if session.get("user_id") is None:
        return redirect("/login")
    habit = Habit.query.get_or_404(id)
    try:
        db.session.delete(habit)
        # Delete all checkboxes for this habit (any date)
        Checkbox.query.filter(
            Checkbox.user_id == session["user_id"],
            Checkbox.id.like("% " + str(id) + " %")
        ).delete(synchronize_session=False)
        Checkbox.query.filter(
            Checkbox.user_id == session["user_id"],
            Checkbox.id.like("% " + str(id))
        ).delete(synchronize_session=False)
        db.session.commit()
        return redirect("/habits")
    except:
        flash("There was an error deleting the habit...")
        return redirect("/habits")
    
    
@app.route("/history")
def history():
    if session.get("user_id") is None:
        return redirect("/login")

    user = User.query.filter_by(id=session["user_id"]).first()
    if user is None:
        session.clear()
        return redirect("/login")

    # Get year/month from query params, default to current month
    today = date.today()
    year = request.args.get("year", today.year, type=int)
    month = request.args.get("month", today.month, type=int)

    # Build date range for the requested month
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    # Get all habits for this user, including frequency
    user_habits = Habit.query.filter_by(user_id=session["user_id"]).all()
    habit_map = {h.id: h.description for h in user_habits}

    # Build a map: app_weekday (0=Sun..6=Sat) -> [habit_names scheduled that day]
    # The app's days dict: 0=Sun,1=Mon,2=Tues,3=Wed,4=Thurs,5=Fri,6=Sat
    # habit.frequency stores space-separated app_weekday numbers
    habits_by_appday = {i: [] for i in range(7)}
    for h in user_habits:
        for day_num in h.frequency.split():
            habits_by_appday[int(day_num)].append(h.description)

    # Get all checked checkboxes in this month
    month_start_str = first_day.isoformat()
    month_end_str = last_day.isoformat()
    checked_boxes = Checkbox.query.filter(
        Checkbox.user_id == session["user_id"],
        Checkbox.value == "checked",
        Checkbox.date >= month_start_str,
        Checkbox.date <= month_end_str
    ).all()

    # Build a dict: { "YYYY-MM-DD": [habit_name, ...] }
    completions = {}
    for cb in checked_boxes:
        # cb.id format: "day habit_id YYYY-MM-DD"
        parts = cb.id.split(" ")
        if len(parts) >= 3:
            try:
                habit_id = int(parts[1])
            except ValueError:
                continue
            habit_name = habit_map.get(habit_id, "Unknown")
            d = cb.date
            if d not in completions:
                completions[d] = []
            if habit_name not in completions[d]:
                completions[d].append(habit_name)

    # Build calendar weeks for the template
    cal = calendar.Calendar(firstweekday=0)  # Monday first
    weeks = cal.monthdatescalendar(year, month)

    # Prev/next month navigation
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    month_name = first_day.strftime("%B %Y")

    return render_template(
        "history.html",
        weeks=weeks,
        month_name=month_name,
        year=year,
        month=month,
        today=today,
        completions=completions,
        habits=habit_map,
        habits_by_appday=habits_by_appday,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
        current_month=month,
    )


@app.route("/logout")
def logout():
    if session.get("user_id") is None:
        return redirect("/login")
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run(debug=True)
