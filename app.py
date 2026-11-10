import sqlite3
from collections import deque
from datetime import datetime, time, timedelta, timezone
from functools import wraps
from itertools import combinations
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import os

from flask import Flask, render_template, session, redirect, url_for, g, request, flash
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_db, close_db, ensure_schema
from forms import RegistrationForm, LoginForm
from airgroundcrewsys import AirportError, Flight, GroundCrew, RampAgent, TeamLeader


app = Flask(__name__)
app.teardown_appcontext(close_db)
# Sessions are kept in a signed cookie in the browser (Flask's default), not in files
# on the server. Vercel starts a fresh copy of the app for many requests, so files
# saved on one request are gone by the next, which broke logins and the CSRF token.
# Set SECRET_KEY in Vercel (Settings > Environment Variables) to keep it out of the code.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "6062-corkathon")
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = bool(os.environ.get("VERCEL"))   # HTTPS-only cookie when live
app.config["WTF_CSRF_TIME_LIMIT"] = None    # the token lasts as long as the session
CSRFProtect(app)          # every POST form must send a csrf_token
ensure_schema()           # adds the flights.approved column to an older app.db


# ---------------------------------------------------------------
# Settings
# ---------------------------------------------------------------
REQUIRED_SKILLS = ("Tug", "Belt loader", "Baggage", "Steps")   # every crew must cover all four
CREW_ROLES = ("team_leader", "ramp_agent")                      # roles that can be put in a crew
FLIGHT_STATUSES = ("on_time", "delayed", "arrived", "departed", "cancelled")
TIME_FMT = "%Y-%m-%dT%H:%M:%SZ"
TURNAROUND_BUFFER = timedelta(minutes=15)                       # rest gap between two flights for one crew


# ---------------------------------------------------------------
# Login and permissions
# ---------------------------------------------------------------
@app.before_request
def load_logged_in_user():
    g.user = session.get("id", None)
    g.isAdmin = session.get("isAdmin", None)
    g.role = session.get("role", None)
    # Supervisors (admins) and managers can use the supervisor page
    g.is_supervisor = g.isAdmin == 1 or g.role == "manager"

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped_view

def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login", next=request.path))
        if not g.is_supervisor:
            flash("Only supervisors can open that page.", "error")
            return redirect(url_for("employee_flights"))
        return view(*args, **kwargs)
    return wrapped_view

# Shared by login and register: replaces any old session with one for this account
def start_session(account):
    session.clear()
    session["id"] = account["id"]
    session["airport_code"] = account["airportCode"]
    session["employee_id"] = account["employee_id"]
    session["isAdmin"] = account["isAdmin"]
    session["role"] = account["role"]

# Supervisors and managers land on the supervisor page, everyone else on their flights
def redirect_for_role():
    is_supervisor = session.get("isAdmin") == 1 or session.get("role") == "manager"
    return redirect(url_for("supervisor" if is_supervisor else "employee_flights"))

# Only follow ?next= if it is a path on this site, never an external URL
def is_safe_next(target):
    return bool(target) and target.startswith("/") and not target.startswith(("//", "/\\"))

def current_user():
    return get_db().execute("SELECT * FROM users WHERE id = ? AND isActive = 1;", (g.user,)).fetchone()


# ---------------------------------------------------------------
# Time helpers: the database stores UTC, pages show airport local time
# ---------------------------------------------------------------
def parse_utc(text):
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

def to_utc_text(moment):
    return moment.astimezone(timezone.utc).strftime(TIME_FMT)

def local_hhmm(text, tz):
    return parse_utc(text).astimezone(tz).strftime("%H:%M") if text else None

# Everything about "today" at one airport, in one place
def airport_day(airport_code):
    airport = get_db().execute("SELECT * FROM airports WHERE airportCode = ?;", (airport_code,)).fetchone()
    try:
        tz = ZoneInfo(airport["timezone"] if airport else "UTC")
    except ZoneInfoNotFoundError:
        tz = timezone.utc   # on Windows, run: pip install tzdata
    now = datetime.now(timezone.utc)
    local_midnight = datetime.combine(now.astimezone(tz).date(), time.min, tzinfo=tz)
    return {
        "tz": tz,
        "now": now,
        "today": local_midnight.date().isoformat(),
        "start": to_utc_text(local_midnight),
        "end": to_utc_text(local_midnight + timedelta(days=1)),
        "local_midnight": local_midnight,
    }


# ---------------------------------------------------------------
# Data helpers shared by several routes
# ---------------------------------------------------------------
def skills_for(user_ids):
    """Returns {user id: [skills]} for the given users."""
    user_ids = list(user_ids)
    if not user_ids:
        return {}
    marks = ",".join("?" * len(user_ids))
    skills = {}
    for row in get_db().execute(f"SELECT userID, skill FROM userSkills WHERE userID IN ({marks}) ORDER BY skill;", user_ids):
        skills.setdefault(row["userID"], []).append(row["skill"])
    return skills

def sick_today(airport_code, today):
    rows = get_db().execute("""SELECT shiftAssignments.userID FROM shiftAssignments
                            JOIN shifts ON shifts.id = shiftAssignments.shiftID
                            WHERE shifts.airportCode = ? AND shifts.shiftDate = ?
                            AND shiftAssignments.status = 'sick';""", (airport_code, today))
    return {row["userID"] for row in rows}

def team_shift(team_id, today):
    return get_db().execute("""SELECT * FROM shifts WHERE teamID = ? AND shiftDate = ?
                            ORDER BY startTime LIMIT 1;""", (team_id, today)).fetchone()

def todays_assignment(user_id, airport_code, today):
    return get_db().execute("""SELECT shiftAssignments.*, shifts.teamID FROM shiftAssignments
                            JOIN shifts ON shifts.id = shiftAssignments.shiftID
                            WHERE shiftAssignments.userID = ? AND shifts.airportCode = ? AND shifts.shiftDate = ?
                            ORDER BY shiftAssignments.id DESC LIMIT 1;""",
                            (user_id, airport_code, today)).fetchone()

def status_note(status, expected_arrival, tz):
    if status == "delayed" and expected_arrival:
        return "Arriving " + local_hhmm(expected_arrival, tz)
    if status == "sick":
        return "Called in sick"
    return None

def team_members(team_id, shift, tz, me_id=None):
    """Members of a team with their skills, covering skill and status today. Leader first."""
    rows = get_db().execute("""SELECT users.id, users.employee_id, users.firstName, users.lastName, users.role,
                            shiftAssignments.status, shiftAssignments.coveringSkill, shiftAssignments.expectedArrival
                            FROM users
                            LEFT JOIN shiftAssignments ON shiftAssignments.userID = users.id
                                                      AND shiftAssignments.shiftID = ?
                            WHERE users.teamID = ? AND users.isActive = 1
                            ORDER BY CASE users.role WHEN 'team_leader' THEN 0 ELSE 1 END,
                                     users.lastName, users.firstName;""",
                            (shift["id"] if shift else None, team_id)).fetchall()
    skills = skills_for(row["id"] for row in rows)
    members = []
    for row in rows:
        status = row["status"] or "ready"
        members.append({
            "id": row["id"],
            "employee_id": row["employee_id"],
            "name": row["firstName"] + " " + row["lastName"],
            "role": row["role"],
            "is_leader": row["role"] == "team_leader",
            "is_me": row["id"] == me_id,
            "status": status,
            "covering": row["coveringSkill"],
            "status_note": status_note(status, row["expectedArrival"], tz),
            "skills": skills.get(row["id"], []),
        })
    return members

def todays_roster(airport_code, today):
    return [{"name": r["firstName"] + " " + r["lastName"], "role": r["role"], "status": r["status"]}
            for r in get_db().execute("""SELECT users.firstName, users.lastName, users.role, shiftAssignments.status
                                      FROM shiftAssignments
                                      JOIN shifts ON shifts.id = shiftAssignments.shiftID
                                      JOIN users ON users.id = shiftAssignments.userID
                                      WHERE shifts.airportCode = ? AND shifts.shiftDate = ?
                                      ORDER BY users.lastName, users.firstName;""",
                                      (airport_code, today))]

def flight_view(row, tz):
    """A flight row with its times shown in the airport's local time."""
    flight = dict(row)
    flight["scheduledArrival"] = local_hhmm(row["scheduledArrival"], tz)
    flight["scheduledDeparture"] = local_hhmm(row["scheduledDeparture"], tz)
    return flight

def notifications_for(user_id, tz):
    return [{"message": n["message"], "time": local_hhmm(n["createdAt"], tz)}
            for n in get_db().execute("""SELECT * FROM notifications WHERE userID = ? AND isRead = 0
                                      ORDER BY createdAt DESC, id DESC LIMIT 6;""", (user_id,))]

def notify(user_id, message):
    get_db().execute("INSERT INTO notifications (userID, message) VALUES (?, ?);", (user_id, message))

def notify_supervisors(airport_code, message):
    for row in get_db().execute("""SELECT id FROM users WHERE airportCode = ? AND isActive = 1
                                AND (isAdmin = 1 OR role = 'manager');""", (airport_code,)).fetchall():
        notify(row["id"], message)

def flight_at_airport(flight_id, airport_code):
    return get_db().execute("SELECT * FROM flights WHERE id = ? AND airportCode = ?;",
                            (flight_id, airport_code)).fetchone()

def team_at_airport(team_id, airport_code):
    return get_db().execute("SELECT * FROM teams WHERE id = ? AND airportCode = ?;",
                            (team_id, airport_code)).fetchone()


# ---------------------------------------------------------------
# Crew rules
# ---------------------------------------------------------------
def match_skills(people):
    """people: list of (user id, set of skills).
    Gives each person at most one skill so that as many required skills as possible are covered.
    Returns {user id: skill they cover}."""
    best = {}

    def search(index, used, current):
        nonlocal best
        if len(current) > len(best):
            best = dict(current)
        if index == len(people) or len(best) == len(REQUIRED_SKILLS):
            return
        person_id, skills = people[index]
        for skill in REQUIRED_SKILLS:
            if skill in skills and skill not in used:
                current[person_id] = skill
                used.add(skill)
                search(index + 1, used, current)
                used.discard(skill)
                del current[person_id]
        search(index + 1, used, current)   # this person covers nothing

    search(0, set(), {})
    return best

def build_crew(number, people):
    """Puts people into a GroundCrew using the classes from airgroundcrewsys.
    Raises AirportError if the crew breaks a rule."""
    crew = GroundCrew(number)
    leaders = []
    for person in people:
        if person["role"] == "team_leader":
            member = TeamLeader(person["name"], str(person["employee_id"]))
            leaders.append(member)
        else:
            member = RampAgent(person["name"], str(person["employee_id"]))
        crew.add_member(member)
    if not leaders:
        raise AirportError("the team has no team leader")
    leaders[0].approve_crew(crew)      # raises if not 4 members with exactly 1 leader
    return crew

def check_crew(team_id, airport_code, today, tz):
    """Is this team fit to work a flight right now? Returns (True, "") or (False, reason)."""
    shift = team_shift(team_id, today)
    members = [m for m in team_members(team_id, shift, tz) if m["status"] != "sick"]
    if len(members) < 4:
        return False, f"only {len(members)} of 4 crew available"
    try:
        build_crew(team_id, members)
    except AirportError as error:
        return False, str(error)
    cover = match_skills([(m["id"], set(m["skills"])) for m in members])
    missing = [skill for skill in REQUIRED_SKILLS if skill not in cover.values()]
    if missing:
        return False, "missing " + ", ".join(missing)
    return True, ""

def form_crews(staff):
    """staff: list of dicts with id, employee_id, name, role, skills (a set).
    Each team leader gets the 3 ramp agents that, together with them, cover all four skills.
    Agents with fewer skills are used first, so versatile agents are saved for later crews.
    Returns (crews, leftover staff). Each crew is (members, {user id: covering skill})."""
    leaders = [person for person in staff if person["role"] == "team_leader"]
    agents = [person for person in staff if person["role"] == "ramp_agent"]
    leaders.sort(key=lambda person: len(person["skills"]))
    crews, unused_leaders = [], []

    for leader in leaders:
        best = None
        for trio in combinations(agents, 3):
            group = [leader, *trio]
            cover = match_skills([(person["id"], person["skills"]) for person in group])
            if len(cover) == len(REQUIRED_SKILLS):
                score = sum(len(person["skills"]) for person in trio)
                if best is None or score < best[0]:
                    best = (score, group, cover)
        if best is None:
            unused_leaders.append(leader)
            continue
        _, group, cover = best
        try:
            build_crew(len(crews) + 1, group)     # double-check with the GroundCrew rules
        except AirportError:
            unused_leaders.append(leader)
            continue
        crews.append((group, cover))
        for person in group[1:]:
            agents.remove(person)

    return crews, unused_leaders + agents


# ---------------------------------------------------------------
# Pages
# ---------------------------------------------------------------
@app.route('/')
def home():
    return render_template("home.html", title="CrewOps")


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        account = get_db().execute("""SELECT * FROM users
                    WHERE airportCode = ? AND employee_id = ? AND isActive = 1;""",
                    (form.airport_code.data, form.employee_id.data)).fetchone()

        # One message for both failures so the form doesn't reveal which IDs exist
        if account is None or not check_password_hash(account["password"], form.password.data):
            form.password.errors.append("Incorrect airport code, employee ID or password")
        else:
            start_session(account)
            next_page = request.args.get("next")
            if is_safe_next(next_page):
                return redirect(next_page)
            return redirect_for_role()

    return render_template("login.html", form=form, title="Log in · CrewOps")


@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()

    if form.validate_on_submit():
        employee_id = form.employee_id.data
        db = get_db()

        airport = db.execute("SELECT 1 FROM airports WHERE airportCode = ?;",
                             (form.airport_code.data,)).fetchone()

        if airport is None:
            form.airport_code.errors.append("Unknown airport code")
        else:
            # Supervisors (admins) have an employee ID ending in 400
            is_admin = employee_id % 1000 == 400
            role = "supervisor" if is_admin else form.role.data
            try:
                cursor = db.execute("""INSERT INTO users (airportCode, employee_id, password, role, isAdmin, firstName, lastName)
                           VALUES (?,?,?,?,?,?,?);""",
                           (form.airport_code.data, employee_id, generate_password_hash(form.password.data),
                            role, int(is_admin), form.f_name.data, form.s_name.data))
            except sqlite3.IntegrityError:
                form.employee_id.errors.append("Employee ID already exists at this airport")
            else:
                for skill in form.skills.data:
                    db.execute("INSERT OR IGNORE INTO userSkills (userID, skill) VALUES (?, ?);",
                               (cursor.lastrowid, skill))
                db.commit()
                start_session(db.execute("SELECT * FROM users WHERE id = ?;", (cursor.lastrowid,)).fetchone())
                return redirect_for_role()

    return render_template("register.html", form=form, title="Register · CrewOps")


@app.route('/employee_flights')
@login_required
def employee_flights():
    db = get_db()
    user = current_user()
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    day = airport_day(user["airportCode"])
    tz, now = day["tz"], day["now"]

    # The user's team, its shift today, and each member's skills and status
    team = {"name": "No team assigned", "members": []}
    shift = None
    if user["teamID"] is not None:
        team_row = db.execute("SELECT * FROM teams WHERE id = ?;", (user["teamID"],)).fetchone()
        if team_row is not None:
            team["name"] = team_row["name"]
        shift = team_shift(user["teamID"], day["today"])
        team["members"] = team_members(user["teamID"], shift, tz, me_id=user["id"])

    # The user's own status today (for the "My status" card)
    assignment = todays_assignment(user["id"], user["airportCode"], day["today"])
    my_status = None
    if assignment is not None:
        my_status = {"status": assignment["status"],
                     "note": status_note(assignment["status"], assignment["expectedArrival"], tz)}

    roster = todays_roster(user["airportCode"], day["today"])
    roster_sick = sum(1 for person in roster if person["status"] == "sick")

    # Flights arriving today: the team's own, and all at the airport
    my_rows = []
    if user["teamID"] is not None:
        my_rows = db.execute("""SELECT flights.*, teams.name AS team_name
                             FROM flights LEFT JOIN teams ON teams.id = flights.teamID
                             WHERE flights.airportCode = ? AND flights.teamID = ?
                             AND flights.scheduledArrival >= ? AND flights.scheduledArrival < ?
                             ORDER BY flights.scheduledArrival;""",
                             (user["airportCode"], user["teamID"], day["start"], day["end"])).fetchall()
    all_rows = db.execute("""SELECT flights.*, teams.name AS team_name
                          FROM flights LEFT JOIN teams ON teams.id = flights.teamID
                          WHERE flights.airportCode = ?
                          AND flights.scheduledArrival >= ? AND flights.scheduledArrival < ?
                          ORDER BY flights.scheduledArrival;""",
                          (user["airportCode"], day["start"], day["end"])).fetchall()

    # Next flight still to leave: the team's, or the airport's if the user has no team
    now_text = to_utc_text(now)
    candidates = my_rows if user["teamID"] is not None else all_rows
    next_row = next((f for f in candidates
                     if f["scheduledDeparture"] >= now_text
                     and f["status"] not in ("departed", "cancelled")), None)
    next_flight = None
    if next_row is not None:
        next_flight = flight_view(next_row, tz)
        arrival, departure = parse_utc(next_row["scheduledArrival"]), parse_utc(next_row["scheduledDeparture"])
        if arrival > now:
            next_flight["countdown"] = f"Arrives in {int((arrival - now).total_seconds() // 60)} min"
        else:
            next_flight["countdown"] = f"Departs in {int((departure - now).total_seconds() // 60)} min"

    return render_template('employee_flights.html',
                           title="My flights · CrewOps",
                           user=user,
                           team=team,
                           shift_start=local_hhmm(shift["startTime"], tz) if shift else None,
                           shift_end=local_hhmm(shift["endTime"], tz) if shift else None,
                           next_flight=next_flight,
                           my_status=my_status,
                           notifications=notifications_for(user["id"], tz),
                           roster=roster,
                           roster_total=len(roster),
                           roster_available=len(roster) - roster_sick,
                           roster_sick=roster_sick,
                           team_ready=sum(1 for m in team["members"] if m["status"] == "ready"),
                           team_size=len(team["members"]),
                           my_flights=[flight_view(f, tz) for f in my_rows],
                           all_flights=[flight_view(f, tz) for f in all_rows])


@app.route('/supervisor')
@admin_required
def supervisor():
    db = get_db()
    employee = current_user()
    if employee is None:
        session.clear()
        return redirect(url_for("login"))

    code = employee["airportCode"]
    day = airport_day(code)
    tz = day["tz"]

    span = db.execute("""SELECT MIN(startTime) AS first, MAX(endTime) AS last
                      FROM shifts WHERE airportCode = ? AND shiftDate = ?;""", (code, day["today"])).fetchone()

    # Flights arriving today, with the team handling each
    flight_rows = db.execute("""SELECT flights.*, teams.name AS team_name
                             FROM flights LEFT JOIN teams ON teams.id = flights.teamID
                             WHERE flights.airportCode = ?
                             AND flights.scheduledArrival >= ? AND flights.scheduledArrival < ?
                             ORDER BY flights.scheduledArrival;""",
                             (code, day["start"], day["end"])).fetchall()
    flights = [flight_view(row, tz) for row in flight_rows]

    # Every team, with its shift, members and any missing skills
    sick = sick_today(code, day["today"])
    teams = []
    for team_row in db.execute("SELECT * FROM teams WHERE airportCode = ? ORDER BY id;", (code,)).fetchall():
        shift = team_shift(team_row["id"], day["today"])
        members = team_members(team_row["id"], shift, tz)
        working = [m for m in members if m["status"] != "sick"]
        # Use the skills people are actually covering today; work it out only if some are blank
        covered = {m["covering"] for m in working if m["covering"]}
        if len(covered) == len(working):
            cover = {m["id"]: m["covering"] for m in working}
        else:
            cover = match_skills([(m["id"], set(m["skills"])) for m in working])
        leader = next((m["name"] for m in members if m["is_leader"]), None)
        teams.append({
            "id": team_row["id"],
            "name": team_row["name"],
            "leader": leader,
            "members": members,
            "shift": (local_hhmm(shift["startTime"], tz) + " – " + local_hhmm(shift["endTime"], tz)) if shift else None,
            "missing_skills": [skill for skill in REQUIRED_SKILLS if skill not in cover.values()] if members else [],
            "short": 4 - len(working) if members and len(working) < 4 else 0,
        })

    # Active crew staff with no team who are not off sick today
    unassigned_rows = db.execute("""SELECT id, firstName, lastName, role, employee_id FROM users
                                 WHERE airportCode = ? AND isActive = 1 AND teamID IS NULL
                                 AND role IN ('team_leader', 'ramp_agent')
                                 ORDER BY lastName, firstName;""", (code,)).fetchall()
    unassigned_rows = [row for row in unassigned_rows if row["id"] not in sick]
    skills = skills_for(row["id"] for row in unassigned_rows)
    unassigned_staff = [{"id": r["id"], "name": r["firstName"] + " " + r["lastName"], "role": r["role"],
                         "employee_id": r["employee_id"], "skills": skills.get(r["id"], [])}
                        for r in unassigned_rows]

    # Sick cover requests waiting for a decision
    cover_requests = [dict(r) for r in db.execute("""
        SELECT reassignmentRequests.id,
               sickUser.firstName || ' ' || sickUser.lastName AS sick_name,
               teams.name AS team_name,
               shiftAssignments.coveringSkill AS skill,
               coverUser.firstName || ' ' || coverUser.lastName AS proposed_name,
               reassignmentRequests.proposedUserID AS proposed_id,
               coverUser.teamID AS proposed_team
        FROM reassignmentRequests
        JOIN absenceReports ON absenceReports.id = reassignmentRequests.absenceReportID
        JOIN shiftAssignments ON shiftAssignments.id = absenceReports.shiftAssignmentID
        JOIN shifts ON shifts.id = shiftAssignments.shiftID
        JOIN users AS sickUser ON sickUser.id = shiftAssignments.userID
        LEFT JOIN users AS coverUser ON coverUser.id = reassignmentRequests.proposedUserID
        LEFT JOIN teams ON teams.id = shifts.teamID
        WHERE shifts.airportCode = ? AND shifts.shiftDate = ? AND reassignmentRequests.status = 'pending'
        ORDER BY reassignmentRequests.createdAt;""", (code, day["today"]))]
    # A suggested person who has since joined a team is no longer free to cover
    for req in cover_requests:
        if req["proposed_team"] is not None:
            req["proposed_id"] = req["proposed_name"] = None

    roster = todays_roster(code, day["today"])
    roster_sick = sum(1 for person in roster if person["status"] == "sick")

    return render_template('supervisor.html',
                           title="Supervisor · CrewOps",
                           employee=employee,
                           shift_start=local_hhmm(span["first"], tz) if span["first"] else None,
                           shift_end=local_hhmm(span["last"], tz) if span["last"] else None,
                           flights=flights,
                           flights_total=len(flights),
                           teams=teams,
                           teams_total=sum(1 for t in teams if t["members"]),
                           unassigned_total=sum(1 for f in flight_rows
                                                if f["teamID"] is None and f["status"] != "cancelled"),
                           delays_total=sum(1 for f in flight_rows if f["status"] == "delayed"),
                           pending_total=sum(1 for f in flight_rows if f["teamID"] is not None
                                             and not f["approved"]
                                             and f["status"] not in ("departed", "cancelled")),
                           flight_statuses=FLIGHT_STATUSES,
                           unassigned_staff=unassigned_staff,
                           cover_requests=cover_requests,
                           notifications=notifications_for(employee["id"], tz),
                           roster=roster,
                           roster_total=len(roster),
                           roster_available=len(roster) - roster_sick,
                           roster_sick=roster_sick)


# ---------------------------------------------------------------
# Supervisor actions
# ---------------------------------------------------------------
@app.route("/generate", methods=["POST"])
@admin_required
def generate_teams():
    """Builds crews of 4 for today and gives every open flight a crew."""
    db = get_db()
    code = current_user()["airportCode"]
    day = airport_day(code)

    # 1. Who can work today: active leaders and agents who have not called in sick
    sick = sick_today(code, day["today"])
    rows = db.execute("""SELECT id, employee_id, firstName, lastName, role FROM users
                      WHERE airportCode = ? AND isActive = 1 AND role IN ('team_leader', 'ramp_agent');""",
                      (code,)).fetchall()
    skills = skills_for(row["id"] for row in rows)
    staff = [{"id": r["id"], "employee_id": r["employee_id"], "name": r["firstName"] + " " + r["lastName"],
              "role": r["role"], "skills": set(skills.get(r["id"], []))}
             for r in rows if r["id"] not in sick]

    # 2. Form the crews
    crews, leftover = form_crews(staff)
    if not crews:
        flash("Couldn't form any complete crew: each needs a team leader and all four skills.", "error")
        return redirect(url_for("supervisor"))

    # Keep anyone's "delayed" status and arrival time when they move to a new crew
    previous = {r["userID"]: r for r in db.execute("""SELECT shiftAssignments.* FROM shiftAssignments
                                                   JOIN shifts ON shifts.id = shiftAssignments.shiftID
                                                   WHERE shifts.airportCode = ? AND shifts.shiftDate = ?
                                                   AND shiftAssignments.status != 'sick';""",
                                                   (code, day["today"]))}

    # 3. One team row per crew (make new teams if there are more crews than teams)
    team_rows = db.execute("SELECT id, name FROM teams WHERE airportCode = ? ORDER BY id;", (code,)).fetchall()
    team_ids = [row["id"] for row in team_rows]
    names = {row["name"] for row in team_rows}
    number = len(team_ids)
    while len(team_ids) < len(crews):
        number += 1
        while f"Team {number}" in names:
            number += 1
        team_ids.append(db.execute("INSERT INTO teams (airportCode, name) VALUES (?, ?);",
                                   (code, f"Team {number}")).lastrowid)

    # 4. Clear today's crews (sick reports stay, so their absence history is kept)
    db.execute("UPDATE users SET teamID = NULL WHERE airportCode = ? AND role IN ('team_leader', 'ramp_agent');", (code,))
    db.execute("""DELETE FROM shiftAssignments WHERE status != 'sick'
                  AND shiftID IN (SELECT id FROM shifts WHERE airportCode = ? AND shiftDate = ?);""",
               (code, day["today"]))

    # 5. Save each crew: team, shift, covering skill
    windows = {}
    for index, (members, cover) in enumerate(crews):
        team_id = team_ids[index]
        shift = team_shift(team_id, day["today"])
        if shift is None:
            # Teams without a shift today get a default 06:00-14:00 local shift
            start = day["local_midnight"] + timedelta(hours=6)
            shift_id = db.execute("""INSERT INTO shifts (airportCode, teamID, shiftDate, startTime, endTime)
                                  VALUES (?, ?, ?, ?, ?);""",
                                  (code, team_id, day["today"], to_utc_text(start),
                                   to_utc_text(start + timedelta(hours=8)))).lastrowid
            shift = db.execute("SELECT * FROM shifts WHERE id = ?;", (shift_id,)).fetchone()
        windows[team_id] = (parse_utc(shift["startTime"]), parse_utc(shift["endTime"]))
        team_name = db.execute("SELECT name FROM teams WHERE id = ?;", (team_id,)).fetchone()["name"]

        for person in members:
            old = previous.get(person["id"])
            db.execute("UPDATE users SET teamID = ? WHERE id = ?;", (team_id, person["id"]))
            db.execute("""INSERT INTO shiftAssignments (shiftID, userID, coveringSkill, status, expectedArrival)
                          VALUES (?, ?, ?, ?, ?);""",
                       (shift["id"], person["id"], cover.get(person["id"]),
                        old["status"] if old else "ready", old["expectedArrival"] if old else None))
            notify(person["id"], f"You're in {team_name} today, covering {cover.get(person['id'])}.")

    # 6. Give open flights to crews, earliest arrival first (a queue)
    flight_rows = db.execute("""SELECT * FROM flights WHERE airportCode = ?
                             AND scheduledArrival >= ? AND scheduledArrival < ?
                             ORDER BY scheduledArrival;""", (code, day["start"], day["end"])).fetchall()
    free_at = {team_id: start for team_id, (start, end) in windows.items()}

    # Flights already being worked keep their crew, and that crew is busy until they leave
    for flight in flight_rows:
        if flight["status"] == "arrived" and flight["teamID"] in free_at:
            free_at[flight["teamID"]] = max(free_at[flight["teamID"]],
                                            parse_utc(flight["scheduledDeparture"]) + TURNAROUND_BUFFER)

    queue = deque(f for f in flight_rows if f["status"] in ("on_time", "delayed"))
    assigned = unassigned = 0
    while queue:
        flight = queue.popleft()
        arrival, departure = parse_utc(flight["scheduledArrival"]), parse_utc(flight["scheduledDeparture"])
        free = [team_id for team_id, (start, end) in windows.items()
                if start <= arrival and departure <= end and free_at[team_id] <= arrival]
        if free:
            team_id = min(free, key=lambda t: free_at[t])     # the crew that has been free longest
            db.execute("UPDATE flights SET teamID = ?, approved = 0 WHERE id = ?;", (team_id, flight["id"]))
            free_at[team_id] = departure + TURNAROUND_BUFFER
            assigned += 1
        else:
            db.execute("UPDATE flights SET teamID = NULL, approved = 0 WHERE id = ?;", (flight["id"],))
            unassigned += 1

    db.commit()
    message = f"Formed {len(crews)} crews and assigned {assigned} flights."
    if unassigned:
        message += f" {unassigned} flight(s) had no free crew during their shift; assign them by hand."
    if leftover:
        message += f" {len(leftover)} staff are left without a crew."
    flash(message, "success")
    return redirect(url_for("supervisor"))


@app.route("/approve/<int:flight_id>", methods=["POST"])
@admin_required
def approve_flight(flight_id):
    code = current_user()["airportCode"]
    day = airport_day(code)
    flight = flight_at_airport(flight_id, code)
    if flight is None or flight["teamID"] is None:
        flash("That flight has no team to approve.", "error")
        return redirect(url_for("supervisor"))

    ok, reason = check_crew(flight["teamID"], code, day["today"], day["tz"])
    if not ok:
        flash(f"Can't approve {flight['flightNumber']}: {reason}.", "error")
    else:
        get_db().execute("UPDATE flights SET approved = 1 WHERE id = ?;", (flight_id,))
        get_db().commit()
        flash(f"{flight['flightNumber']} approved.", "success")
    return redirect(url_for("supervisor"))


@app.route("/approve_all", methods=["POST"])
@admin_required
def approve_all():
    db = get_db()
    code = current_user()["airportCode"]
    day = airport_day(code)
    pending = db.execute("""SELECT * FROM flights WHERE airportCode = ? AND teamID IS NOT NULL AND approved = 0
                         AND status NOT IN ('departed', 'cancelled')
                         AND scheduledArrival >= ? AND scheduledArrival < ?;""",
                         (code, day["start"], day["end"])).fetchall()
    approved, skipped = 0, []
    checked = {}
    for flight in pending:
        if flight["teamID"] not in checked:
            checked[flight["teamID"]] = check_crew(flight["teamID"], code, day["today"], day["tz"])
        ok, reason = checked[flight["teamID"]]
        if ok:
            db.execute("UPDATE flights SET approved = 1 WHERE id = ?;", (flight["id"],))
            approved += 1
        else:
            skipped.append(f"{flight['flightNumber']} ({reason})")
    db.commit()
    flash(f"Approved {approved} flights.", "success")
    if skipped:
        flash("Not approved: " + "; ".join(skipped), "error")
    return redirect(url_for("supervisor"))


@app.route("/reassign/<int:flight_id>", methods=["POST"])
@admin_required
def reassign_flight(flight_id):
    db = get_db()
    code = current_user()["airportCode"]
    flight = flight_at_airport(flight_id, code)
    if flight is None:
        flash("Flight not found.", "error")
        return redirect(url_for("supervisor"))

    team_id = request.form.get("team_id", type=int)
    if team_id is None:
        db.execute("UPDATE flights SET teamID = NULL, approved = 0 WHERE id = ?;", (flight_id,))
        flash(f"{flight['flightNumber']} now has no team.", "success")
    else:
        team = team_at_airport(team_id, code)
        if team is None:
            flash("That team doesn't exist at your airport.", "error")
            return redirect(url_for("supervisor"))
        # The supervisor chose this team themselves, so it counts as approved
        db.execute("UPDATE flights SET teamID = ?, approved = 1 WHERE id = ?;", (team_id, flight_id))
        for member in db.execute("SELECT id FROM users WHERE teamID = ? AND isActive = 1;", (team_id,)).fetchall():
            notify(member["id"], f"{team['name']} now has {flight['flightNumber']} from {flight['origin']}.")
        flash(f"{flight['flightNumber']} given to {team['name']}.", "success")
    db.commit()
    return redirect(url_for("supervisor"))


@app.route("/move_staff/<int:user_id>", methods=["POST"])
@admin_required
def move_staff(user_id):
    db = get_db()
    code = current_user()["airportCode"]
    day = airport_day(code)

    person = db.execute("""SELECT * FROM users WHERE id = ? AND airportCode = ? AND isActive = 1
                        AND role IN ('team_leader', 'ramp_agent');""", (user_id, code)).fetchone()
    team = team_at_airport(request.form.get("team_id", type=int), code)
    if person is None or team is None:
        flash("Pick a valid person and team.", "error")
        return redirect(url_for("supervisor"))

    shift = team_shift(team["id"], day["today"])
    members = [m for m in team_members(team["id"], shift, day["tz"]) if m["status"] != "sick"]
    name = person["firstName"] + " " + person["lastName"]

    # Use the GroundCrew rules: a crew can't have more than 4 people
    crew = GroundCrew(team["id"])
    try:
        for member in members + [{"name": name, "employee_id": person["employee_id"], "role": person["role"]}]:
            cls = TeamLeader if member["role"] == "team_leader" else RampAgent
            crew.add_member(cls(member["name"], str(member["employee_id"])))
    except AirportError as error:
        flash(f"Can't move {name} to {team['name']}: {error}", "error")
        return redirect(url_for("supervisor"))

    # Which skill this person should cover in the team
    group = [(m["id"], set(m["skills"])) for m in members] + [(person["id"], set(skills_for([person["id"]]).get(person["id"], [])))]
    covering = match_skills(group).get(person["id"])

    db.execute("UPDATE users SET teamID = ? WHERE id = ?;", (team["id"], person["id"]))
    if shift is not None:
        db.execute("""DELETE FROM shiftAssignments WHERE userID = ? AND status != 'sick'
                      AND shiftID IN (SELECT id FROM shifts WHERE airportCode = ? AND shiftDate = ?);""",
                   (person["id"], code, day["today"]))
        db.execute("""INSERT OR REPLACE INTO shiftAssignments (shiftID, userID, coveringSkill, status)
                      VALUES (?, ?, ?, 'ready');""", (shift["id"], person["id"], covering))
    notify(person["id"], f"You've been moved to {team['name']}" + (f", covering {covering}." if covering else "."))
    db.commit()
    flash(f"{name} moved to {team['name']}.", "success")
    return redirect(url_for("supervisor"))


@app.route("/flight/<int:flight_id>/status", methods=["POST"])
@admin_required
def update_flight(flight_id):
    db = get_db()
    code = current_user()["airportCode"]
    flight = flight_at_airport(flight_id, code)
    status = request.form.get("status")
    delay = request.form.get("delay_minutes", type=int) or 0
    if flight is None or status not in FLIGHT_STATUSES:
        flash("Pick a valid flight and status.", "error")
        return redirect(url_for("supervisor"))

    arrival, departure = flight["scheduledArrival"], flight["scheduledDeparture"]
    if delay:
        # Use the Flight class from airgroundcrewsys to apply the delay
        try:
            model = Flight(flight["flightNumber"], flight["origin"], parse_utc(departure))
            model.delay_flight(minutes=delay, hours=0)
        except ValueError as error:
            flash(f"Can't delay {flight['flightNumber']}: {error}", "error")
            return redirect(url_for("supervisor"))
        departure = to_utc_text(model.etd)
        arrival = to_utc_text(parse_utc(arrival) + timedelta(minutes=delay))
        status = "delayed"

    team_id = None if status == "cancelled" else flight["teamID"]     # a cancelled flight frees its crew
    db.execute("""UPDATE flights SET status = ?, scheduledArrival = ?, scheduledDeparture = ?, teamID = ?
                  WHERE id = ?;""", (status, arrival, departure, team_id, flight_id))
    if flight["teamID"] is not None:
        label = status.replace("_", " ")
        extra = f" by {delay} min" if delay else ""
        for member in db.execute("SELECT id FROM users WHERE teamID = ? AND isActive = 1;", (flight["teamID"],)).fetchall():
            notify(member["id"], f"{flight['flightNumber']} is now {label}{extra}.")
    db.commit()
    flash(f"{flight['flightNumber']} updated.", "success")
    return redirect(url_for("supervisor"))


# ---------------------------------------------------------------
# Sick and late reporting, cover requests
# ---------------------------------------------------------------
def find_cover(airport_code, today, skill):
    """An available person with no team who has the needed skill (fewest skills first)."""
    sick = sick_today(airport_code, today)
    already_asked = {row["proposedUserID"] for row in get_db().execute(
        "SELECT proposedUserID FROM reassignmentRequests WHERE status = 'pending' AND proposedUserID IS NOT NULL;")}
    rows = get_db().execute("""SELECT id, firstName, lastName FROM users
                            WHERE airportCode = ? AND isActive = 1 AND teamID IS NULL
                            AND role IN ('team_leader', 'ramp_agent');""", (airport_code,)).fetchall()
    rows = [r for r in rows if r["id"] not in sick and r["id"] not in already_asked]
    skills = skills_for(r["id"] for r in rows)
    if skill:
        rows = [r for r in rows if skill in skills.get(r["id"], [])]
    rows.sort(key=lambda r: len(skills.get(r["id"], [])))
    return rows[0] if rows else None


@app.route("/report_status", methods=["POST"])
@login_required
def report_status():
    db = get_db()
    user = current_user()
    day = airport_day(user["airportCode"])
    status = request.form.get("status")
    if status not in ("ready", "delayed", "sick"):
        flash("Unknown status.", "error")
        return redirect(url_for("employee_flights"))

    assignment = todays_assignment(user["id"], user["airportCode"], day["today"])
    if assignment is None:
        flash("You're not on a shift today.", "error")
        return redirect(url_for("employee_flights"))

    name = user["firstName"] + " " + user["lastName"]
    team = db.execute("SELECT * FROM teams WHERE id = ?;", (assignment["teamID"],)).fetchone()
    team_name = team["name"] if team else "no team"
    leader = db.execute("SELECT id FROM users WHERE teamID = ? AND role = 'team_leader' AND isActive = 1 AND id != ?;",
                        (assignment["teamID"], user["id"])).fetchone()

    if status == "ready":
        db.execute("UPDATE shiftAssignments SET status = 'ready', expectedArrival = NULL WHERE id = ?;",
                   (assignment["id"],))
        flash("You're marked as ready.", "success")

    elif status == "delayed":
        minutes = max(5, min(240, request.form.get("minutes", type=int) or 15))
        arrival = to_utc_text(day["now"] + timedelta(minutes=minutes))
        db.execute("UPDATE shiftAssignments SET status = 'delayed', expectedArrival = ? WHERE id = ?;",
                   (arrival, assignment["id"]))
        message = f"{name} ({team_name}) is running {minutes} min late."
        if leader:
            notify(leader["id"], message)
        notify_supervisors(user["airportCode"], message)
        flash(f"Your team knows you're about {minutes} min late.", "success")

    else:   # sick
        db.execute("UPDATE shiftAssignments SET status = 'sick', expectedArrival = NULL WHERE id = ?;",
                   (assignment["id"],))
        report = db.execute("SELECT id FROM absenceReports WHERE shiftAssignmentID = ?;", (assignment["id"],)).fetchone()
        report_id = report["id"] if report else db.execute(
            "INSERT INTO absenceReports (shiftAssignmentID) VALUES (?);", (assignment["id"],)).lastrowid

        pending = db.execute("SELECT 1 FROM reassignmentRequests WHERE absenceReportID = ? AND status = 'pending';",
                             (report_id,)).fetchone()
        if pending is None:
            # Suggest someone with the skill this person was covering (or any of their skills)
            skill = assignment["coveringSkill"] or next(iter(skills_for([user["id"]]).get(user["id"], [])), None)
            cover = find_cover(user["airportCode"], day["today"], skill)
            db.execute("INSERT INTO reassignmentRequests (absenceReportID, proposedUserID) VALUES (?, ?);",
                       (report_id, cover["id"] if cover else None))
            suggestion = (f"Suggested cover: {cover['firstName']} {cover['lastName']}." if cover
                          else "No free cover found, please assign someone.")
            notify_supervisors(user["airportCode"], f"{name} ({team_name}) called in sick. {suggestion}")
        if leader:
            notify(leader["id"], f"{name} has called in sick for today's shift.")
        flash("You're marked as sick. Your supervisor has been told. Feel better!", "success")

    db.commit()
    return redirect(url_for("employee_flights"))


@app.route("/cover/<int:request_id>/<decision>", methods=["POST"])
@admin_required
def decide_cover(request_id, decision):
    db = get_db()
    supervisor_user = current_user()
    code = supervisor_user["airportCode"]
    day = airport_day(code)
    if decision not in ("approve", "reject"):
        flash("Unknown decision.", "error")
        return redirect(url_for("supervisor"))

    req = db.execute("""SELECT reassignmentRequests.*, shiftAssignments.shiftID, shiftAssignments.coveringSkill,
                     shiftAssignments.userID AS sickUserID, shifts.teamID, shifts.airportCode
                     FROM reassignmentRequests
                     JOIN absenceReports ON absenceReports.id = reassignmentRequests.absenceReportID
                     JOIN shiftAssignments ON shiftAssignments.id = absenceReports.shiftAssignmentID
                     JOIN shifts ON shifts.id = shiftAssignments.shiftID
                     WHERE reassignmentRequests.id = ?;""", (request_id,)).fetchone()
    if req is None or req["airportCode"] != code or req["status"] != "pending":
        flash("That cover request is no longer open.", "error")
        return redirect(url_for("supervisor"))

    now_text = to_utc_text(day["now"])
    if decision == "reject":
        db.execute("UPDATE reassignmentRequests SET status = 'rejected', decidedBy = ?, decidedAt = ? WHERE id = ?;",
                   (supervisor_user["id"], now_text, request_id))
        flash("Cover request rejected.", "success")
    else:
        if req["proposedUserID"] is None:
            flash("There's no suggested person to approve. Move someone into the team instead.", "error")
            return redirect(url_for("supervisor"))
        cover = db.execute("SELECT * FROM users WHERE id = ?;", (req["proposedUserID"],)).fetchone()
        if cover["teamID"] is not None:
            flash(f"{cover['firstName']} {cover['lastName']} is already in a team. Dismiss this request "
                  "and move someone in from Unassigned staff.", "error")
            return redirect(url_for("supervisor"))
        team = db.execute("SELECT * FROM teams WHERE id = ?;", (req["teamID"],)).fetchone()
        db.execute("UPDATE users SET teamID = ? WHERE id = ?;", (req["teamID"], cover["id"]))
        db.execute("""DELETE FROM shiftAssignments WHERE userID = ? AND status != 'sick'
                      AND shiftID IN (SELECT id FROM shifts WHERE airportCode = ? AND shiftDate = ?);""",
                   (cover["id"], code, day["today"]))
        db.execute("""INSERT OR REPLACE INTO shiftAssignments (shiftID, userID, coveringSkill, status)
                      VALUES (?, ?, ?, 'ready');""", (req["shiftID"], cover["id"], req["coveringSkill"]))
        db.execute("UPDATE reassignmentRequests SET status = 'approved', decidedBy = ?, decidedAt = ? WHERE id = ?;",
                   (supervisor_user["id"], now_text, request_id))
        skill_text = f", covering {req['coveringSkill']}" if req["coveringSkill"] else ""
        notify(cover["id"], f"You're covering in {team['name']} today{skill_text}.")
        leader = db.execute("SELECT id FROM users WHERE teamID = ? AND role = 'team_leader' AND isActive = 1;",
                            (req["teamID"],)).fetchone()
        if leader:
            notify(leader["id"], f"{cover['firstName']} {cover['lastName']} is joining {team['name']} as cover.")
        flash(f"{cover['firstName']} {cover['lastName']} added to {team['name']}.", "success")

    db.commit()
    return redirect(url_for("supervisor"))


@app.route("/notifications/read", methods=["POST"])
@login_required
def read_notifications():
    get_db().execute("UPDATE notifications SET isRead = 1 WHERE userID = ?;", (g.user,))
    get_db().commit()
    next_page = request.form.get("next")
    return redirect(next_page if is_safe_next(next_page) else url_for("employee_flights"))


if __name__ == "__main__":
    app.run(debug=True)
