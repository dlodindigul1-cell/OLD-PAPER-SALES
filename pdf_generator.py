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

LABEL_W = 30  # பொருள் / பார்வை / முன்னிலை போன்ற லேபிள்களின் இடது இண்டெண்ட்


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

    # ---------- அடிப்படை உதவி methods ----------

    def heading(self, text, size=12, gap=1.3, indent=0):
        self.set_font("Tamil", "B", size)
        if indent:
            self.set_x(self.l_margin + indent)
        self.multi_cell(self.epw - indent, 6.5, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(gap)

    def p(self, text, size=11, gap=1.3, indent=0):
        self.set_font("Tamil", "", size)
        if indent:
            self.set_x(self.l_margin + indent)
        self.multi_cell(self.epw - indent, 6, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(gap)

    def signature_space(self, height=12):
        """கையொப்பம் இட (pen-ஆல்) காலியிடம்"""
        self.ln(height)

    def two_col_line(self, left, right, bold_left=False, bold_right=False,
                      underline_left=False, underline_right=False, size=11, gap=1.3):
        """ஒரே வரியில் இடது + வலது பகுதிகள் (எ.கா: ந.க.எண் ... நாள்)."""
        y = self.get_y()
        self.set_xy(self.l_margin, y)
        style_l = ("B" if bold_left else "") + ("U" if underline_left else "")
        self.set_font("Tamil", style_l, size)
        self.cell(self.epw / 2, 6, left, new_x="LEFT", new_y="TOP")

        style_r = ("B" if bold_right else "") + ("U" if underline_right else "")
        self.set_font("Tamil", style_r, size)
        self.set_xy(self.l_margin + self.epw / 2, y)
        self.cell(self.epw / 2, 6, right, align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(gap)

    def label_para(self, label, text, indent=LABEL_W, size=11, gap=1.3, bold_label=True, label_w=32):
        """இடதுபுறம் bold label, அதே வரியில் தொடங்கி wrap ஆகும் பத்தி வலதுபுறம்."""
        self.set_x(self.l_margin + indent)
        self.set_font("Tamil", "B" if bold_label else "", size)
        self.cell(label_w, 6, label, new_x="RIGHT", new_y="TOP")
        self.set_font("Tamil", "", size)
        self.multi_cell(self.epw - indent - label_w, 6, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(gap)

    def vendor_heading(self, index, name, size=11, gap=0.5):
        y = self.get_y()
        self.set_font("Tamil", "", size)
        self.set_xy(self.l_margin, y)
        self.cell(45, 6, f"விலைப்புள்ளி {index}", new_x="LEFT", new_y="TOP")
        self.set_xy(self.l_margin + 45, y)
        self.cell(0, 6, name, new_x="LMARGIN", new_y="NEXT")
        self.ln(gap)

    def quote_table(self, weights, prices, total_label="மொத்தம்-ரூ"):
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
        rows_data.append(["", total_label, "", f"{total_weight:.2f}", f"{total_amount:.2f}"])

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


def _new_pdf():
    pdf = OrderPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.set_margins(15, 12, 15)
    pdf.setup_fonts()
    return pdf


def _subject_and_common(record):
    libname = _lib_full_name(record)
    period = record.get("period", "")
    letter_date = record.get("letterDate", "")
    rcnum = record.get("rcnum", "")
    subject = (
        f"{libname} - நூலகத்தில்- {period} "
        f"இருப்பில் உள்ள பழைய நாளிதழ்களை விற்பனை செய்ய ஆணை வழங்குதல் குறித்து"
    )
    return libname, period, letter_date, rcnum, subject


def _get_selected(record, vendor_index):
    quotes = record.get("quotes") or []
    if vendor_index is None or vendor_index < 0 or vendor_index >= len(quotes):
        raise ValueError("சரியான வழங்குநர் தேர்வு இல்லை")
    return quotes, quotes[vendor_index]


# ==========================================
# 1. அலுவலகக் குறிப்பு (Office Note) வரைதல் - pic-1.pdf போன்று
# ==========================================
def _draw_office_note(pdf, record, vendor_index):
    weights = record.get("weights") or {}
    libname, period, letter_date, rcnum, subject = _subject_and_common(record)
    quotes, selected = _get_selected(record, vendor_index)
    selected_name = selected.get("vendorName", "")

    pdf.two_col_line(
        "அ.கு சமர்ப்பிக்கப் படுகிறது", f"ந.க.எண்.        {rcnum}",
        underline_left=True, bold_right=True,
    )
    pdf.ln(1)
    pdf.label_para("பொருள்", subject)
    pdf.label_para("பார்வை", f"{libname} - நூலகரின் கடிதம் நாள். {letter_date}")
    pdf.ln(1)

    pdf.p(
        f"திண்டுக்கல் மாவட்ட நூலக ஆணைக்குழுவின் கீழ் செயல்படும் {libname} "
        f"{period} இருப்பில் உள்ள பழைய நாளிதழ்களை விற்பனை செய்ய "
        f"பின்வருமாறு விலைப்புள்ளிகள் பெறப்பட்டுள்ளன"
    )
    pdf.ln(1)

    for i, q in enumerate(quotes, start=1):
        vname = q.get("vendorName", "")
        pdf.vendor_heading(i, vname)
        pdf.quote_table(weights, q.get("prices") or {}, total_label="மொத்தம்-ரூ")
        pdf.ln(1)

    pdf.p(
        f"மேற்கண்ட விலைப்புள்ளிகளில் அதிக விலைக்கு ஒப்பப்புள்ளி வழங்கியுள்ள திரு. "
        f"{selected_name} என்பவருக்கு பழைய நாளிதழ்கள்/சஞ்சிகைகள் விற்பனை செய்ய "
        f"அனுமதிப்பது மீதான நடவடிக்கைக்கு ஒப்புதல் கோரி இக்கோப்பு பணிந்து "
        f"சமர்ப்பிக்கப்படுகிறது."
    )
    pdf.ln(2)
    pdf.p("ஆணைக்காக")


def generate_office_note_pdf(record, vendor_index, officer_name=None, officer_designation=None):
    """பக்கம் 1 மட்டும் - அலுவலகக் குறிப்பு (pic-1.pdf போன்ற வடிவம்)."""
    pdf = _new_pdf()
    pdf.add_page()
    _draw_office_note(pdf, record, vendor_index)
    return bytes(pdf.output())


# ==========================================
# 2. விற்பனை ஆணை (Sales Order) வரைதல் - pic-2.pdf போன்று
# ==========================================
def _draw_sales_order(pdf, record, vendor_index, officer_name, officer_designation):
    weights = record.get("weights") or {}
    libname, period, letter_date, rcnum, subject = _subject_and_common(record)
    quotes, selected = _get_selected(record, vendor_index)
    selected_name = selected.get("vendorName", "")
    today_str = datetime.now().strftime("%d-%m-%Y")
    designation_line = officer_designation
    if designation_line and not designation_line.endswith("."):
        designation_line += "."

    # -------- Letterhead --------
    pdf.heading(
        "திண்டுக்கல் மாவட்ட நூலக அலுவலரின் செயல்முறைகள் ,        திண்டுக்கல்",
        size=12, gap=1.0, indent=0,
    )
    pdf.label_para("முன்னிலை :-", officer_name or "", indent=LABEL_W, size=11, gap=0.3)
    pdf.p(designation_line or "", indent=LABEL_W + 32, gap=1.0)

    # -------- ந.க.எண் / நாள் --------
    pdf.two_col_line(
        f"ந.க.எண் {rcnum}", f"நாள்.-  {today_str}",
        bold_left=True, underline_left=True, bold_right=True, underline_right=True,
    )
    pdf.ln(1)

    pdf.label_para("பொருள்:-", subject)
    pdf.label_para("பார்வை:-", f"{libname} - நூலகரின் கடிதம் நாள். {letter_date}")
    pdf.ln(1)

    pdf.heading("ஆணை", size=13, gap=1.0)
    pdf.p(
        f"பார்வையில் காணும் {libname} நூலகரின் கடிதத்துடன் இணைத்து சமர்ப்பித்த "
        f"ஒப்பப்புள்ளிகள் பரிசீலனை செய்யப்பட்டு, கூடுதல் விலைப்புள்ளி அளித்த "
        f"கீழ்க்காணும் நபருக்கு {period} உள்ள பழைய செய்தி ஏடுகள் விற்பனை செய்ய "
        f"ஆணை வழங்கப்படுகிறது."
    )

    pdf.set_font("Tamil", "B", 11)
    pdf.cell(28, 6, "திருவாளர் -", new_x="RIGHT", new_y="TOP")
    pdf.cell(0, 6, selected_name, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(0.5)

    total_amount = pdf.quote_table(weights, selected.get("prices") or {}, total_label="மொத்தம்")
    pdf.ln(1)

    pdf.set_font("Tamil", "B", 11)
    pdf.cell(70, 6, "மொத்த விற்பனை தொகை – ரூ", new_x="RIGHT", new_y="TOP")
    pdf.set_font("Tamil", "", 11)
    pdf.cell(0, 6, f"{total_amount:.2f}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1.5)

    pdf.p("1. விற்பனை தொகைக்கு அன்றைய தினமே இரசீது கொடுக்க வேண்டும்.")
    pdf.p("2.விற்பனை செய்து முடித்த பின்னர் தொகையினை வங்கி அல்லது கருவூலத்தில் செலுத்த வேண்டும்")
    pdf.p(
        "3.நூலகரால் விற்பனை சமர்ப்பிக்கப்பட்ட பட்டியலில் குறிப்பிட்ட எடைக்கு "
        "எடை குறைவு ஏற்படாமல் இருத்தல் வேண்டும். எடை குறைவு ஏற்படும் பட்சத்தில் "
        "அதற்குரிய தொகையை நூலகரிடமிருந்து வசூலிக்கப்படும் என நூலகர் "
        "அறிவுறுத்தப்படுகிறார்."
    )
    pdf.ln(2)

    # -------- கையொப்ப பகுதி --------
    pdf.two_col_line("", designation_line.rstrip(".") if designation_line else "", gap=0.3)
    pdf.two_col_line("பெறுநர்    நூலகர்", "திண்டுக்கல்.", gap=0.3)
    pdf.p(libname, indent=18, gap=0)


def generate_sales_order_pdf(record, vendor_index, officer_name, officer_designation):
    """ஒரு பக்கம் மட்டும் - விற்பனை ஆணை (pic-2.pdf போன்ற வடிவம்)."""
    pdf = _new_pdf()
    pdf.add_page()
    _draw_sales_order(pdf, record, vendor_index, officer_name, officer_designation)
    return bytes(pdf.output())


# ==========================================
# 3. இரண்டையும் இணைத்த முழு PDF (தேடல்/காப்பக பதிவிறக்கத்திற்கு)
# ==========================================
def generate_order_pdf(record, vendor_index, officer_name, officer_designation):
    """
    record: sales_records-லிருந்து பெறப்பட்ட dict (libraryName, libraryType, period,
            rcnum, letterDate, weights, quotes)
    vendor_index: 0-based, Order tab-ல் தேர்ந்தெடுக்கப்பட்ட வழங்குநர்
    officer_name, officer_designation: settings-லிருந்து
    Returns: PDF bytes - பக்கம் 1: அலுவலகக் குறிப்பு, பக்கம் 2: விற்பனை ஆணை
    """
    pdf = _new_pdf()
    pdf.add_page()
    _draw_office_note(pdf, record, vendor_index)
    pdf.add_page()
    _draw_sales_order(pdf, record, vendor_index, officer_name, officer_designation)
    return bytes(pdf.output())
