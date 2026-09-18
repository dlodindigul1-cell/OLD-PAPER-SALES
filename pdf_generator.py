# ==========================================
# pdf_generator.py - ஆணை/குறிப்பு PDF உருவாக்கம்
# fpdf2 + HarfBuzz text shaping (uharfbuzz) பயன்படுத்தி சரியான தமிழ் எழுத்து வடிவமைப்பு
# ==========================================
import os
from datetime import datetime
from fpdf import FPDF

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")

CATEGORIES = [
    ("tamilDaily", "தமிழ் நாளிதழ்கள்"),
    ("englishDaily", "ஆங்கில நாளிதழ்கள்"),
    ("tamilPeriodical", "தமிழ் பருவ இதழ்கள்"),
    ("englishPeriodical", "ஆங்கில பருவ இதழ்கள்"),
    ("freePublication", "இலவச வெளியீடுகள்"),
]

COL_WIDTHS = [12, 65, 30, 30, 33]  # வ.எண் | விவரம் | விலை | எடை | மொத்தம்


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _lib_full_name(record):
    name = record.get("libraryName", "")
    ltype = record.get("libraryType", "")
    return f"{name} - {ltype}" if ltype else name


class OrderPDF(FPDF):
    def setup_fonts(self):
        self.add_font("Tamil", "", os.path.join(FONT_DIR, "NotoSansTamil-Regular.ttf"))
        self.add_font("Tamil", "B", os.path.join(FONT_DIR, "NotoSansTamil-Bold.ttf"))
        self.set_text_shaping(True)

    def heading(self, text, size=12, gap=1.3):
        self.set_font("Tamil", "B", size)
        self.multi_cell(0, 6.5, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(gap)

    def p(self, text, size=11, gap=1.3):
        self.set_font("Tamil", "", size)
        self.multi_cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(gap)

    def signature_space(self, height=12):
        """கையொப்பம் இட (pen-ஆல்) காலியிடம்"""
        self.ln(height)

    def quote_table(self, weights, prices):
        headers = ["வ.எண்", "பத்திரிக்கைகள் விவரம்", "கிலோ 1க்கு விலை", "மொத்த எடை", "மொத்தம்"]
        total_weight = 0.0
        total_amount = 0.0
        rows_data = []
        for idx, (key, label) in enumerate(CATEGORIES, start=1):
            rate = _num(prices.get(key))
            weight = _num(weights.get(key))
            amount = rate * weight
            total_weight += weight
            total_amount += amount
            rows_data.append([str(idx), label, f"{rate:.2f}", f"{weight:.2f}", f"{amount:.2f}"])
        rows_data.append(["", "மொத்தம்-ரூ", "", f"{total_weight:.2f}", f"{total_amount:.2f}"])

        self.set_font("Tamil", "", 10)
        with self.table(
            col_widths=COL_WIDTHS,
            text_align=("CENTER", "LEFT", "CENTER", "CENTER", "CENTER"),
            line_height=5.3,
        ) as table:
            row = table.row()
            self.set_font("Tamil", "B", 10)
            for htext in headers:
                row.cell(htext)
            for i, r in enumerate(rows_data):
                self.set_font("Tamil", "B" if i == len(rows_data) - 1 else "", 10)
                row = table.row()
                for val in r:
                    row.cell(val)
        return total_amount


def generate_order_pdf(record, vendor_index, officer_name, officer_designation):
    """
    record: sales_records-லிருந்து பெறப்பட்ட dict (libraryName, libraryType, period,
            rcnum, letterDate, weights, quotes)
    vendor_index: 0-based, Order tab-ல் தேர்ந்தெடுக்கப்பட்ட வழங்குநர்
    officer_name, officer_designation: settings-லிருந்து
    Returns: PDF bytes
    """
    quotes = record.get("quotes") or []
    weights = record.get("weights") or {}
    libname = _lib_full_name(record)
    period = record.get("period", "")
    letter_date = record.get("letterDate", "")
    rcnum = record.get("rcnum", "")
    today_str = datetime.now().strftime("%d-%m-%Y")

    if vendor_index is None or vendor_index < 0 or vendor_index >= len(quotes):
        raise ValueError("சரியான வழங்குநர் தேர்வு இல்லை")
    selected = quotes[vendor_index]

    subject = (
        f"{libname} - நூலகத்தில் {period} இருப்பு உள்ள "
        f"பழைய நாளிதழ்களை விற்பனை செய்ய ஆணைவழங்கிய குறிப்பு"
    )

    pdf = OrderPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.set_margins(15, 12, 15)
    pdf.setup_fonts()

    # ================= PAGE 1: குறிப்பு =================
    pdf.add_page()
    pdf.p(f"அ. சமர்ப்பிக்கப்படுகிற குறிப்பு                                    ந.க.எண். {rcnum}")
    pdf.p(f"பொருள்:- {subject}")
    pdf.p(f"பார்வை:- {libname} கடித நாள். {letter_date}")
    pdf.p(
        f"திண்டுக்கல் மாவட்ட நூலக ஆணையருக்கு கீழ் செயல்படும் {libname} "
        f"{period} இருப்புள்ள பழைய நாளிதழ்களை விற்பனை செய்ய "
        f"பின்வருமாறு விலைப்புள்ளிகள் பெறப்பட்டுள்ளன."
    )
    pdf.ln(1)

    for i, q in enumerate(quotes):
        vname = q.get("vendorName", "")
        pdf.heading(f"விலைப்புள்ளி {i + 1}   {vname}", size=11, gap=0.5)
        pdf.quote_table(weights, q.get("prices") or {})
        pdf.ln(1)

    selected_name = selected.get("vendorName", "")
    pdf.p(
        f"மேற்கண்ட விலைப்புள்ளிகளில் அதிக விலைக்கு ஒப்பந்தம் வழங்கியுள்ள "
        f"திரு. {selected_name} என்பவருக்கு பழைய நாளிதழ்/சஞ்சிகைகள் விற்பனை செய்ய "
        f"அனுமதிக்கும் மேலான நடவடிக்கைக்கு ஒப்புதல் கோரி இக்கோரிக்கை பணிவுடன் "
        f"சமர்ப்பிக்கப்படுகிறது."
    )
    pdf.ln(2)
    pdf.p("ஆணைக்காக")
    pdf.p("திண்டுக்கல் மாவட்ட நூலக அலுவலகத்தில் செயல்முறைகள், திண்டுக்கல்")
    pdf.signature_space(12)  # கையொப்பம் இட காலியிடம்
    pdf.p(f"முன்னிலை:- {officer_name}")
    pdf.p(f"{officer_designation}.")

    # ================= PAGE 2: ஆணை =================
    pdf.add_page()
    pdf.p(f"ந.க.எண். {rcnum}                                    நாள்:- {today_str}")
    pdf.p(f"பொருள்:- {subject}")
    pdf.p(f"பார்வை:- {libname} கடித நாள். {letter_date}")
    pdf.ln(1)
    pdf.heading("ஆணை", size=13, gap=1.5)
    pdf.p(
        f"பார்வையில் காணும் {libname} நூலகர் கடிதத்துடன் இணைத்து சமர்ப்பித்த "
        f"ஒப்பந்தப் புள்ளிகள் பரிசீலனை செய்யப்பட்டு, அதில் விலைப்புள்ளி அளித்த "
        f"கீழ்க்கண்ட நபருக்கு {period} உள்ள பழைய செய்தி ஏடுகள் விற்பனை செய்ய "
        f"ஆணை வழங்கப்படுகிறது."
    )
    pdf.ln(1)
    pdf.p(f"திருவாளர்:- {selected_name}")
    total_amount = pdf.quote_table(weights, selected.get("prices") or {})
    pdf.ln(1)
    pdf.heading(f"மொத்த விற்பனை தொகை – ரூ {total_amount:.2f}", size=11, gap=1.5)

    pdf.p("1. விற்பனை தொகைக்கு அன்றைய தினமே ரசீது கொடுக்க வேண்டும்.")
    pdf.p("2. விற்பனை செய்து முடித்த பின்னர் தொகையை வங்கி அல்லது ரொக்கமூலம் செலுத்த வேண்டும்.")
    pdf.p(
        "3. நூலகரால் விற்பனை சமர்ப்பிக்கப்பட்ட பட்டியலில் குறிப்பிட்ட எடைக்கு "
        "எடை குறைவு ஏற்படாமல் இருக்க வேண்டும். எடை குறைவு ஏற்பட்டால் அதற்கிணங்க "
        "தொகையினை நூலகரிடமிருந்து வசூலிக்கப்படும் என நூலகர் அறிவுறுத்தப்படுகிறார்."
    )
    pdf.signature_space(12)  # கையொப்பம் இட காலியிடம்
    pdf.p(officer_designation)
    pdf.p("பொறுப்பு நூலகர், திண்டுக்கல்.")
    pdf.ln(2)
    pdf.p(f"நகல்:- {libname} அவர்களுக்கு.")

    return bytes(pdf.output())
