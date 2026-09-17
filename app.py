# ==========================================
# app.py - பழைய பத்திரிக்கை விற்பனை மேலாண்மை (Flask + Neon Postgres)
# ==========================================
import os
import json
from datetime import datetime

from flask import Flask, render_template, request, jsonify
import psycopg2
import psycopg2.extras

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def get_conn():
    # Render free plan-க்கு sslmode=require அவசியம் (Neon)
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def init_db():
    """Render free plan-ல் shell access இல்லை என்பதால், app தொடங்கும்போதே
    தேவையான tables/indexes தானாக உருவாகும் (neon_setup.sql-க்கு இணையானது)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS libraries (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            type TEXT DEFAULT ''
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sales_records (
            id SERIAL PRIMARY KEY,
            library_name TEXT NOT NULL,
            library_type TEXT DEFAULT '',
            period TEXT NOT NULL,
            rcnum TEXT DEFAULT '',
            letter_date TEXT DEFAULT '',
            weights JSONB DEFAULT '{}'::jsonb,
            quotes JSONB DEFAULT '[]'::jsonb,
            saved_at TIMESTAMP DEFAULT NOW(),
            UNIQUE (library_name, period)
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_library ON sales_records (library_name);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sales_period ON sales_records (period);")
    conn.commit()
    cur.close()
    conn.close()


# App import ஆகும்போதே ஒரு முறை run ஆகும் (gunicorn workers-ல் ஒவ்வொன்றும் இதை
# அழைத்தாலும் CREATE TABLE IF NOT EXISTS என்பதால் பாதுகாப்பானது)
try:
    if DATABASE_URL:
        init_db()
except Exception as e:
    print("init_db failed:", e)


def record_to_json(row):
    """DB row (dict, from RealDictCursor) -> பழைய JSON structure போலவே"""
    return {
        "libraryName": row["library_name"],
        "libraryType": row["library_type"],
        "period": row["period"],
        "rcnum": row["rcnum"],
        "fileNumber": row["rcnum"],
        "letterDate": row["letter_date"],
        "weights": row["weights"] or {},
        "quotes": row["quotes"] or [],
        "savedAt": row["saved_at"].isoformat() if row["saved_at"] else None,
    }


# ==========================================
# Page
# ==========================================
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/admin/libraries")
def admin_libraries():
    return render_template("admin_libraries.html")


# ==========================================
# நூலகங்கள் பட்டியல்
# ==========================================
@app.route("/api/libraries", methods=["GET"])
def get_libraries():
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT name, type FROM libraries ORDER BY name;")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify({"success": True, "data": [{"name": r["name"], "type": r["type"]} for r in rows]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/libraries", methods=["POST"])
def add_library():
    """ஒரு நூலகம் சேர்க்க: {"name": "...", "type": "..."}"""
    try:
        data = request.get_json(force=True)
        name = (data.get("name") or "").strip()
        ltype = (data.get("type") or "").strip()
        if not name:
            return jsonify({"success": False, "error": "பெயர் தேவை"})
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO libraries (name, type) VALUES (%s, %s) "
            "ON CONFLICT (name) DO UPDATE SET type = EXCLUDED.type;",
            (name, ltype),
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/libraries/bulk", methods=["POST"])
def bulk_add_libraries():
    """Bulk import: {"text": "நூலகம்1,வகை1\\nநூலகம்2,வகை2\\n..."}"""
    try:
        data = request.get_json(force=True)
        text = data.get("text") or ""
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            name = parts[0]
            ltype = parts[1] if len(parts) > 1 else ""
            if name:
                rows.append((name, ltype))
        if not rows:
            return jsonify({"success": False, "error": "தரவு காணப்படவில்லை"})
        conn = get_conn()
        cur = conn.cursor()
        cur.executemany(
            "INSERT INTO libraries (name, type) VALUES (%s, %s) "
            "ON CONFLICT (name) DO UPDATE SET type = EXCLUDED.type;",
            rows,
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "count": len(rows)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# ஒரு பதிவை பெறுதல் (நூலகம் + காலம்)
# ==========================================
@app.route("/api/record", methods=["GET"])
def get_record():
    library = request.args.get("library", "")
    period = request.args.get("period", "")
    if not library or not period:
        return jsonify({"success": False, "error": "library, period தேவை"})
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM sales_records WHERE library_name = %s AND period = %s;",
            (library, period),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return jsonify({"success": True, "data": record_to_json(row)})
        return jsonify({"success": True, "data": None})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# பதிவு சேமிக்க / புதுப்பிக்க
# ==========================================
@app.route("/api/record", methods=["POST"])
def save_record():
    try:
        data = request.get_json(force=True)
        library = (data.get("libraryName") or "").strip()
        period = (data.get("period") or "").strip()
        if not library or not period:
            return jsonify({"success": False, "error": "நூலகம், காலம் தேவை"})

        rcnum = data.get("rcnum") or ""
        library_type = data.get("libraryType") or ""
        letter_date = data.get("letterDate") or ""
        weights = json.dumps(data.get("weights") or {})
        quotes = json.dumps(data.get("quotes") or [])

        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO sales_records
                (library_name, library_type, period, rcnum, letter_date, weights, quotes, saved_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (library_name, period) DO UPDATE SET
                library_type = EXCLUDED.library_type,
                rcnum = EXCLUDED.rcnum,
                letter_date = EXCLUDED.letter_date,
                weights = EXCLUDED.weights,
                quotes = EXCLUDED.quotes,
                saved_at = EXCLUDED.saved_at;
            """,
            (library, library_type, period, rcnum, letter_date, weights, quotes, datetime.now()),
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True, "fileNumber": rcnum})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# தேடல் (நூலகம் / காலம் மூலம் filter — SQL-லேயே)
# ==========================================
@app.route("/api/records", methods=["GET"])
def list_records():
    library = request.args.get("library", "")
    period = request.args.get("period", "")
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        query = "SELECT * FROM sales_records WHERE 1=1"
        params = []
        if library:
            query += " AND library_name = %s"
            params.append(library)
        if period:
            query += " AND period = %s"
            params.append(period)
        query += " ORDER BY library_name;"
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify({"success": True, "data": [record_to_json(r) for r in rows]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
