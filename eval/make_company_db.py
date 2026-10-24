"""Builds eval/data/company.db: a small synthetic HR/projects database.

It exists to test the agent on data the model cannot have memorised, with
deliberately awkward stored values (codes such as 'BLR' and 'P0', snake_case
statuses, mixed-case project stages). Deterministic: same file every run.

    python eval/make_company_db.py
"""
import random
import sqlite3
from pathlib import Path

OUT = Path(__file__).resolve().parent / "data" / "company.db"
rng = random.Random(7)

FIRST = ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Ananya", "Vikram", "Isha", "Arjun", "Priya", "Nikhil", "Sneha",
         "Rahul", "Kavya", "Siddharth", "Tara", "Manish", "Neha", "Farhan", "Lakshmi", "Dev", "Zoya", "Harsh", "Pooja"]
LAST = ["Sharma", "Iyer", "Nair", "Reddy", "Khan", "Gupta", "Menon", "Das", "Patel", "Singh", "Joshi", "Rao",
        "Kulkarni", "Bose", "Mehta", "Pillai"]
DEPTS = [("ENG", "Engineering"), ("HR", "Human Resources"), ("FIN", "Finance"),
         ("OPS", "Operations"), ("MKT", "Marketing"), ("SLS", "Sales")]
CITIES = ["BLR", "MUM", "DEL", "HYD", "PUN"]
STATUS = ["active"] * 8 + ["on_leave"] * 2 + ["resigned"] * 2
STAGES = ["In Progress", "Completed", "On Hold", "Not Started"]
PRIORITY = ["P0", "P1", "P1", "P2", "P2", "P2", "P3"]


def main():
    OUT.parent.mkdir(exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    c = sqlite3.connect(OUT)
    c.executescript("""
    CREATE TABLE departments (dept_code TEXT PRIMARY KEY, dept_name TEXT NOT NULL, head_staff_id INTEGER);
    CREATE TABLE staff (staff_id INTEGER PRIMARY KEY, full_name TEXT NOT NULL, dept_code TEXT NOT NULL,
        status TEXT NOT NULL, city TEXT NOT NULL, level TEXT NOT NULL, salary_inr INTEGER NOT NULL, hire_date TEXT NOT NULL,
        FOREIGN KEY (dept_code) REFERENCES departments(dept_code));
    CREATE TABLE projects (project_id INTEGER PRIMARY KEY, project_name TEXT NOT NULL, dept_code TEXT NOT NULL,
        stage TEXT NOT NULL, priority TEXT NOT NULL, budget_inr INTEGER NOT NULL, start_date TEXT NOT NULL,
        FOREIGN KEY (dept_code) REFERENCES departments(dept_code));
    CREATE TABLE timesheets (entry_id INTEGER PRIMARY KEY, staff_id INTEGER NOT NULL, project_id INTEGER NOT NULL,
        hours REAL NOT NULL, work_date TEXT NOT NULL,
        FOREIGN KEY (staff_id) REFERENCES staff(staff_id), FOREIGN KEY (project_id) REFERENCES projects(project_id));
    """)
    names = set()
    staff = []
    for i in range(1, 121):
        while True:
            n = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
            if n not in names:
                names.add(n)
                break
        dept = rng.choices([d[0] for d in DEPTS], weights=[40, 10, 15, 20, 15, 20])[0]
        level = rng.choice(["L1", "L2", "L2", "L3", "L3", "L4", "L5"])
        base = {"L1": 600000, "L2": 900000, "L3": 1400000, "L4": 2000000, "L5": 3000000}[level]
        salary = base + rng.randrange(0, 40) * 10000 + i  # +i keeps salaries unique (no ties)
        year = rng.choice([2019, 2020, 2021, 2022, 2023, 2024, 2025])
        hire = f"{year}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
        staff.append((i, n, dept, rng.choice(STATUS), rng.choice(CITIES), level, salary, hire))
    c.executemany("INSERT INTO staff VALUES (?,?,?,?,?,?,?,?)", staff)
    heads = {}
    for code, _ in DEPTS:
        heads[code] = min(s[0] for s in staff if s[2] == code and s[5] in ("L4", "L5") or s[2] == code)
    c.executemany("INSERT INTO departments VALUES (?,?,?)", [(code, name, heads[code]) for code, name in DEPTS])
    projects = []
    for p in range(1, 41):
        dept = rng.choice([d[0] for d in DEPTS])
        projects.append((p, f"PRJ-{1000 + p}-{rng.choice(['Atlas', 'Beacon', 'Comet', 'Delta', 'Ember', 'Falcon'])}",
                         dept, rng.choice(STAGES), rng.choice(PRIORITY), rng.randrange(5, 200) * 100000 + p,
                         f"{rng.choice([2023, 2024, 2025])}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"))
    c.executemany("INSERT INTO projects VALUES (?,?,?,?,?,?,?)", projects)
    rows = []
    for e in range(1, 1201):
        s = rng.choice(staff)[0]
        p = rng.choice(projects)[0]
        rows.append((e, s, p, round(rng.uniform(1, 8) + (e % 7) * 0.01, 2),
                     f"2025-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"))
    c.executemany("INSERT INTO timesheets VALUES (?,?,?,?,?)", rows)
    c.commit()
    c.close()
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
