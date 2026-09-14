import json
import logging
from typing import Any

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

logger = logging.getLogger("export.exporter")


def _clean_pdf_text(text: str) -> str:
    """Normalize unicode punctuation to standard Latin-1 equivalents for core Helvetica."""
    if not text:
        return ""
    replacements = {
        "—": "--",
        "–": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "•": "*",
        "…": "...",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", errors="replace").decode("latin-1")


if FPDF is not None:
    class ResearchPDF(FPDF):
        """Clean pure-Python PDF generator for research reports without native C dependencies."""

        def header(self):
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(100, 116, 139)
            self.cell(0, 8, _clean_pdf_text("Autonomous AI Research Platform -- Confidential Security Report"), align="R", new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(226, 232, 240)
            self.line(10, 18, 200, 18)
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(148, 163, 184)
            self.cell(0, 10, _clean_pdf_text(f"Page {self.page_no()}/{{nb}} -- Multi-Agent Research Platform"), align="C", new_x="RIGHT", new_y="TOP")
else:
    class ResearchPDF:
        pass


class ReportExporter:
    """Pure-Python exporter for Markdown, JSON, and PDF formats."""

    @staticmethod
    def export_markdown(report_data: dict[str, Any]) -> str:
        report_md = report_data.get("report_markdown", "")
        score = report_data.get("verification_score", 0.0)
        is_degraded = report_data.get("is_degraded", False)

        header = (
            f"<!-- Exported by Autonomous Multi-Agent AI Research Platform -->\n"
            f"<!-- Verification Score: {score:.2f} | Status: {'DEGRADED' if is_degraded else 'VERIFIED'} -->\n\n"
        )
        return header + report_md

    @staticmethod
    def export_json(report_data: dict[str, Any]) -> str:
        return json.dumps(report_data, indent=2, default=str)

    @staticmethod
    def export_pdf(report_data: dict[str, Any]) -> bytes:
        if FPDF is None:
            # Fallback to pure-Python valid PDF container when fpdf2 is not installed
            topic = report_data.get("topic", "Autonomous AI Research Report")
            content_stream = f"BT /F1 12 Tf 50 720 Td ({topic}) Tj ET\n".encode("latin1", errors="replace")
            stream_len = len(content_stream)
            p1 = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n"
            p2 = f"4 0 obj\n<< /Length {stream_len} >>\nstream\n".encode("ascii")
            p3 = b"\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000214 00000 n \ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n315\n%%EOF\n"
            return p1 + p2 + content_stream + p3

        topic = report_data.get("topic", "Autonomous AI Research Report")
        report_md = report_data.get("report_markdown", "")
        score = report_data.get("verification_score", 1.0)
        is_degraded = report_data.get("is_degraded", False)
        claims = report_data.get("claims_audit", [])

        pdf = ResearchPDF(orientation="P", unit="mm", format="A4")
        pdf.alias_nb_pages()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=18)

        # Title
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(15, 23, 42)
        pdf.multi_cell(0, 10, _clean_pdf_text(topic), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        # Metadata box
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(241, 245, 249)
        status_str = "DEGRADED (Under-verified)" if is_degraded else "VERIFIED EMPIRICALLY"
        pdf.cell(0, 8, _clean_pdf_text(f"  Audit Score: {score:.2f}  |  Integrity: {status_str}"), fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

        # Body Content
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(51, 65, 85)

        lines = report_md.split("\n")
        for line in lines:
            line_str = _clean_pdf_text(line.strip())
            if not line_str:
                pdf.ln(3)
                continue

            if line_str.startswith("# "):
                pdf.set_font("Helvetica", "B", 15)
                pdf.set_text_color(15, 23, 42)
                pdf.multi_cell(0, 8, line_str[2:], new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(51, 65, 85)
            elif line_str.startswith("## "):
                pdf.set_font("Helvetica", "B", 12)
                pdf.set_text_color(30, 41, 59)
                pdf.multi_cell(0, 7, line_str[3:], new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(51, 65, 85)
            elif line_str.startswith("- "):
                pdf.multi_cell(0, 5, f"  * {line_str[2:]}", new_x="LMARGIN", new_y="NEXT")
            elif line_str.startswith(">"):
                pdf.set_font("Helvetica", "I", 9)
                pdf.set_text_color(185, 28, 28)
                pdf.multi_cell(0, 5, f"  {line_str}", new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(51, 65, 85)
            else:
                pdf.multi_cell(0, 5, line_str, new_x="LMARGIN", new_y="NEXT")

        # Claims Audit Table
        if claims:
            pdf.ln(6)
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, "Empirical Claims Verification Audit Trail", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 8)
            for c in claims[:6]:
                verdict = c.get("verdict", "UNVERIFIED")
                claim_text = _clean_pdf_text(c.get("claim", "")[:90])
                url = _clean_pdf_text(c.get("citation_url", "")[:45])
                pdf.multi_cell(0, 4, f"[{verdict}] {claim_text}... (Source: {url})", new_x="LMARGIN", new_y="NEXT")

        return bytes(pdf.output())


exporter = ReportExporter()
