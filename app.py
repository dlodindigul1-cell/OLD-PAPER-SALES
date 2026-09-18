# ==========================================
# app.py - பழைய பத்திரிக்கை விற்பனை மேலாண்மை (Flask + Neon Postgres)
# ==========================================
import os
import json
from datetime import datetime

from flask import Flask, render_template, request, jsonify, Response
import psycopg2
import psycopg2.extras

from pdf_generator import generate_order_pdf, generate_office_note_pdf, generate_sales_order_pdf

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
            selected_vendor_index INTEGER,
            saved_at TIMESTAMP DEFAULT NOW(),
            UNIQUE (library_name, period)
        );
    """)
    # பழைய table-களில் இந்த column இல்லாமல் இருக்கலாம் என்பதால் தனியாக சேர்க்கிறோம்
    cur.execute("ALTER TABLE sales_records ADD COLUMN IF NOT EXISTS selected_vendor_index INTEGER;")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
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
        "selectedVendorIndex": row.get("selected_vendor_index"),
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


@app.route("/admin/settings")
def admin_settings_page():
    return render_template("admin_settings.html")


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
            # Google Sheets-லிருந்து Paste செய்தால் Tab-ஆல் பிரிக்கும்;
            # கைமுறையாக type செய்தால் Comma-ஆல் பிரிக்கலாம் — இரண்டையும் ஏற்கும்
            if "\t" in line:
                parts = [p.strip() for p in line.split("\t")]
            else:
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


# ==========================================
# அமைப்புகள் (அலுவலர் பெயர்/பதவி — PDF கையொப்பத்திற்கு)
# ==========================================
DEFAULT_SETTINGS = {
    "officer_name": "மாவட்ட நூலக அலுவலர்",
    "officer_designation": "மாவட்ட நூலக அலுவலர்",
}


@app.route("/api/settings", methods=["GET"])
def get_settings():
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT key, value FROM settings;")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        data = dict(DEFAULT_SETTINGS)
        for r in rows:
            data[r["key"]] = r["value"]
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/settings", methods=["POST"])
def save_settings():
    try:
        data = request.get_json(force=True)
        conn = get_conn()
        cur = conn.cursor()
        for key, value in data.items():
            cur.execute(
                "INSERT INTO settings (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;",
                (key, value),
            )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ==========================================
# ஆணை PDF உருவாக்கம்
# ==========================================
@app.route("/api/generate-pdf", methods=["GET"])
def generate_pdf_route():
    library = request.args.get("library", "")
    period = request.args.get("period", "")
    vendor_index_param = request.args.get("vendor_index")
    # doc: "note" -> அலுவலகக் குறிப்பு மட்டும், "order" -> விற்பனை ஆணை மட்டும்,
    #      "full" (default) -> இரண்டையும் இணைத்தது
    doc_type = request.args.get("doc", "full")

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
        if not row:
            cur.close()
            conn.close()
            return jsonify({"success": False, "error": "தரவு கிடைக்கவில்லை"})

        record = record_to_json(row)

        if vendor_index_param is not None and vendor_index_param != "":
            vendor_index = int(vendor_index_param)
        elif record.get("selectedVendorIndex") is not None:
            vendor_index = record["selectedVendorIndex"]
        else:
            cur.close()
            conn.close()
            return jsonify({"success": False, "error": "வழங்குநர் தேர்வு செய்யப்படவில்லை"})

        # settings
        cur.execute("SELECT key, value FROM settings;")
        srows = cur.fetchall()
        settings = dict(DEFAULT_SETTINGS)
        for r in srows:
            settings[r["key"]] = r["value"]

        # தேர்ந்தெடுத்த வழங்குநரை பதிவில் சேமிக்கவும் (பின்னர் தேடலில் மீண்டும் பதிவிறக்க)
        cur.execute(
            "UPDATE sales_records SET selected_vendor_index = %s WHERE library_name = %s AND period = %s;",
            (vendor_index, library, period),
        )
        conn.commit()
        cur.close()
        conn.close()

        if doc_type == "note":
            pdf_bytes = generate_office_note_pdf(
                record, vendor_index, settings["officer_name"], settings["officer_designation"]
            )
            suffix = "note"
        elif doc_type == "order":
            pdf_bytes = generate_sales_order_pdf(
                record, vendor_index, settings["officer_name"], settings["officer_designation"]
            )
            suffix = "order"
        else:
            pdf_bytes = generate_order_pdf(
                record, vendor_index, settings["officer_name"], settings["officer_designation"]
            )
            suffix = "order"
        # HTTP header-கள் ASCII மட்டுமே ஏற்கும் — தமிழ் filename-ஐ நேரடியாக வைத்தால்
        # reject ஆகும் (400/502). RFC 5987 filename*=UTF-8''... பயன்படுத்துகிறோம்.
        from urllib.parse import quote
        raw_filename = f"{library}_{period}_{suffix}.pdf".replace(" ", "_")
        encoded_filename = quote(raw_filename)
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": (
                    f"inline; filename=\"order.pdf\"; filename*=UTF-8''{encoded_filename}"
                )
            },
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
