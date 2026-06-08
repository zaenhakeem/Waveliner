from docx import Document
from docx.shared import Pt
import os


def generate_word_report(
    filepath,
    report_date,
    group_name,
    declared_total,
    actual_total,
    tally_match,
    summary,
    results
):

    doc = Document()

    # =========================
    # TITLE
    # =========================
    doc.add_heading(
        'QUALITY VERIFICATION REPORT',
        level=1
    )

    doc.add_paragraph(f"Date: {report_date}")
    doc.add_paragraph(f"Group: {group_name}")

    doc.add_paragraph(
        f"Declared Total: {declared_total}"
    )

    doc.add_paragraph(
        f"Actual Total: {actual_total}"
    )

    doc.add_paragraph(
        "Tally Status: "
        + ("MATCH" if tally_match else "MISMATCH")
    )

    doc.add_paragraph("")

    # =========================
    # SUMMARY SECTION
    # =========================
    doc.add_heading(
        'SUMMARY (BY AGENT)',
        level=2
    )

    for s in summary:

        doc.add_heading(
            s['agent'],
            level=3
        )

        doc.add_paragraph(
            f"Total Submitted: {s['total']}"
        )

        doc.add_paragraph(
            f"Quality: {s['quality']}"
        )

        doc.add_paragraph(
            f"Non Quality: {s['non_quality']}"
        )

        doc.add_paragraph(
            f"Not Found: {s['not_found']}"
        )

        # Non quality serials
        nq = ", ".join(
            s.get('non_quality_serials', [])
        )

        nf = ", ".join(
            s.get('not_found_serials', [])
        )

        doc.add_paragraph(
            "Non Quality Serial Ends: "
            + (nq if nq else "None")
        )

        doc.add_paragraph(
            "Not Found Serial Ends: "
            + (nf if nf else "None")
        )

        doc.add_paragraph("")

    # =========================
    # DETAILED TABLE
    # =========================
    doc.add_heading(
        'DETAILED RESULTS',
        level=2
    )

    table = doc.add_table(
        rows=1,
        cols=5
    )

    table.style = 'Table Grid'

    hdr = table.rows[0].cells

    hdr[0].text = "Agent"
    hdr[1].text = "Serial Number"
    hdr[2].text = "Usage"
    hdr[3].text = "Commission"
    hdr[4].text = "Status"

    for r in results:

        row_cells = table.add_row().cells

        row_cells[0].text = str(r['Agent'])
        row_cells[1].text = str(r['Serial Number'])
        row_cells[2].text = str(r['Usage'])
        row_cells[3].text = str(r['Commission'])
        row_cells[4].text = str(r['Status'])

    # =========================
    # SAVE FILE
    # =========================

    safe_group = group_name.replace(" ", "_")
    safe_date = report_date.replace("/", "-")

    filename = f"{safe_group}_{safe_date}.docx"

    full_path = os.path.join(
        filepath,
        filename
    )

    doc.save(full_path)

    return full_path