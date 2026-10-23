"""Generate the evaluation documents (fictional company "Acme Corporation") into eval/docs/.

    uv run python eval/make_docs.py

Facts are deliberately specific (odd numbers, names, dates) so a correct answer can only come
from the documents, never from general knowledge. dataset.jsonl and TEST_QUESTIONS.md are
written against exactly these facts: change both if you change a document.
Also writes eval/transcripts/atlas_weekly_sync.txt for the meeting tool (not ingested).
"""

from pathlib import Path

import docx
import openpyxl
import pymupdf
from openpyxl.styles import Font
from pptx import Presentation
from pptx.util import Pt

EVAL_DIR = Path(__file__).resolve().parent
DOCS = EVAL_DIR / "docs"
TRANSCRIPTS = EVAL_DIR / "transcripts"

CSS = """
body { font-family: sans-serif; font-size: 11pt; line-height: 1.4; }
h1 { font-size: 18pt; margin-bottom: 4pt; }
h2 { font-size: 13pt; margin-top: 12pt; }
p.meta { color: #555; font-size: 9pt; }
"""


def write_pdf(path: Path, title: str, meta: str, sections: list[tuple[str, list[str]]]) -> None:
    """Each section starts on a new page, so citations point at a predictable page number."""
    writer = pymupdf.DocumentWriter(str(path))
    mediabox = pymupdf.paper_rect("a4")
    where = mediabox + (60, 60, -60, -60)
    for i, (heading, paragraphs) in enumerate(sections):
        head = f"<h1>{title}</h1><p class='meta'>{meta}</p>" if i == 0 else ""
        body = "".join(f"<p>{p}</p>" for p in paragraphs)
        story = pymupdf.Story(html=f"{head}<h2>{heading}</h2>{body}", user_css=CSS)
        more = True
        while more:
            device = writer.begin_page(mediabox)
            more, _ = story.place(where)
            story.draw(device)
            writer.end_page()
    writer.close()


def write_docx(path: Path, title: str, meta: str, sections: list[tuple[str, list[str]]]) -> None:
    d = docx.Document()
    d.add_heading(title, level=0)
    d.add_paragraph().add_run(meta).italic = True
    for heading, paragraphs in sections:
        d.add_heading(heading, level=1)
        for p in paragraphs:
            if p.startswith("- "):
                d.add_paragraph(p[2:], style="List Bullet")
            else:
                d.add_paragraph(p)
    d.save(str(path))


# --- 1. HR policy (PDF, 4 pages) -----------------------------------------------------------------

HR_POLICY = [
    (
        "1. Annual leave",
        [
            "All full-time employees receive 24 days of paid annual leave per calendar year. "
            "Part-time employees receive leave in proportion to their contracted hours.",
            "Up to 6 unused days may be carried over into the next year. Carried-over days must "
            "be used by 31 March; any carried-over days not used by then are forfeited.",
            "Requests for more than 3 consecutive days of leave must be submitted in the HR "
            "portal at least 10 working days in advance and approved by the line manager.",
            "Acme observes 11 public holidays per year. The list is published every December.",
        ],
    ),
    (
        "2. Sick leave and other leave",
        [
            "Employees receive 10 days of paid sick leave per year. "
            "Sick leave does not carry over.",
            "A doctor's note is required for an absence of more than 3 consecutive working days.",
            "Bereavement leave: up to 5 paid days on the death of an immediate family member.",
            "Jury duty and court summons are granted as paid leave for the required period.",
        ],
    ),
    (
        "3. Remote and hybrid work",
        [
            "Employees may work remotely up to 2 days per week, agreed with their manager.",
            "Monday and Wednesday are company anchor days: all hybrid employees work from the "
            "office on these days.",
            "Remote work from outside the country of employment is limited to 15 working days "
            "per year and needs HR approval.",
            "Acme pays a one-time home office allowance of 300 USD to hybrid employees.",
        ],
    ),
    (
        "4. Probation, notice period and working hours",
        [
            "New employees serve a probation period of 4 months. During probation the notice "
            "period is 2 weeks for either side.",
            "After probation the notice period is 45 days for employees and 60 days for managers.",
            "Core working hours are 10:00 to 16:00. Overtime must be approved in advance and is "
            "compensated as time off in lieu.",
        ],
    ),
]

# --- 2. Travel and expense policy (DOCX) --------------------------------------------------------

TRAVEL_POLICY = [
    (
        "Approval",
        [
            "All business trips must be approved by the employee's manager before booking. "
            "International trips also need approval from the department head.",
            "Bookings are made through the Acme travel desk (travel@acme-demo.com).",
        ],
    ),
    (
        "Flights and transport",
        [
            "Economy class is used for flights under 6 hours. Premium economy is allowed for "
            "flights of 6 hours or more. Business class is not reimbursed.",
            "Mileage for use of a private car is reimbursed at 0.42 USD per km.",
            "Taxis are reimbursed between 22:00 and 06:00, "
            "or when no public transport is available.",
        ],
    ),
    (
        "Hotels and meals",
        [
            "The hotel limit is 150 USD per night. In London, New York and Tokyo the limit is "
            "210 USD per night.",
            "The meal per diem is 55 USD per day for domestic travel and 70 USD per day for "
            "international travel. Alcohol is not reimbursed.",
        ],
    ),
    (
        "Expense claims",
        [
            "Expense claims must be submitted within 30 days of the end of the trip.",
            "Receipts are required for every expense above 25 USD.",
            "Approved claims are reimbursed with the next monthly salary.",
            "Questions about expenses go to finance-help@acme-demo.com.",
        ],
    ),
]

# --- 3. IT security policy (PDF, 3 pages) -------------------------------------------------------

IT_SECURITY = [
    (
        "1. Accounts and passwords",
        [
            "Passwords must be at least 14 characters long. Multi-factor authentication (MFA) "
            "is mandatory for email, VPN and all company applications.",
            "Passwords are not rotated on a fixed schedule; they must be changed immediately if "
            "a compromise is suspected.",
            "Computers must lock automatically after 5 minutes of inactivity.",
        ],
    ),
    (
        "2. Devices and data",
        [
            "All company laptops are encrypted with BitLocker and managed by the IT desk.",
            "USB storage devices are blocked on company laptops. Files are shared through the "
            "company drive only.",
            "Critical security patches must be installed within 7 days of release.",
            "The VPN is required when working on public Wi-Fi.",
        ],
    ),
    (
        "3. Incidents and engineering rules",
        [
            "Security incidents, including lost devices and suspected phishing, must be reported "
            "to security@acme-demo.com within 1 hour of discovery.",
            "Containers must run as a non-root user, and production images are rebuilt at least "
            "monthly.",
            "Secrets (API keys, passwords) must never be committed to source control; they are "
            "stored in the company vault.",
        ],
    ),
]

# --- 4. Project Atlas status (DOCX) -------------------------------------------------------------

ATLAS_STATUS = [
    (
        "Summary",
        [
            "Project Atlas is the new customer self-service portal. This report covers Sprint 7, "
            "6 to 17 October 2026.",
            "Project manager: Priya Nair. Tech lead: Rohit Mehta. Sponsor: Daniel Okafor (COO).",
        ],
    ),
    (
        "Progress in Sprint 7",
        [
            "- The beta was released to 40 pilot customers on 14 October.",
            "- Single sign-on with the customer directory was completed.",
            "- Invoice download went live for pilot customers.",
            "- 2 open bugs remain, both in the payment flow; neither blocks the pilot.",
        ],
    ),
    (
        "Budget and timeline",
        [
            "Total budget: 380,000 USD. Spent to date: 61% (231,800 USD).",
            "Public launch is planned for 1 December 2026.",
        ],
    ),
    (
        "Risks",
        [
            "- The payment vendor's new API is 3 weeks late; this could delay online payments "
            "past the launch date.",
            "- Load testing has not started; it is planned for Sprint 8.",
        ],
    ),
    (
        "Next steps (Sprint 8)",
        [
            "- Start load testing with 5,000 simulated users.",
            "- Fix the 2 payment-flow bugs.",
            "- Collect feedback from pilot customers with a short survey.",
        ],
    ),
]

# --- 5. Benefits overview (PDF, 2 pages) --------------------------------------------------------

BENEFITS = [
    (
        "Health and wellbeing",
        [
            "Health insurance covers the employee, spouse and up to 2 children, with annual "
            "coverage of 50,000 USD per family.",
            "Acme reimburses gym memberships up to 40 USD per month.",
            "Employees and their families can use the confidential counselling line "
            "free of charge.",
        ],
    ),
    (
        "Learning and referrals",
        [
            "Each employee has a learning budget of 1,200 USD per year for courses, books and "
            "conferences. Unused budget does not carry over.",
            "The employee referral bonus is 1,500 USD, paid after the referred hire completes "
            "90 days.",
            "Salaries are paid on the 28th of every month.",
        ],
    ),
]


def write_q3_sales(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Q3 2026 by region"
    rows = [
        ("Region", "Q2 2026 revenue (USD)", "Q3 2026 revenue (USD)", "Top product", "Lead"),
        ("North", 104000, 120000, "Atlas Cloud", "Meera Iyer"),
        ("South", 91200, 98500, "Ledger Pro", "Carlos Mendes"),
        ("East", 128900, 143200, "Atlas Cloud", "Hana Sato"),
        ("West", 95400, 87300, "Ledger Pro", "Tom Becker"),
        ("Total", 419500, 449000, "", ""),
    ]
    for row in rows:
        ws.append(row)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    notes = wb.create_sheet("Notes")
    notes.append(("Note",))
    notes.append(("East was the best region in Q3 2026; West was the only region that declined.",))
    notes.append(("Q3 2026 company target was 440,000 USD; it was exceeded.",))
    wb.save(str(path))


def write_onboarding(path: Path) -> None:
    prs = Presentation()
    slides = [
        ("Welcome to Acme", ["Onboarding guide for new employees", "People Team, 2026"]),
        (
            "Your first day",
            [
                "Arrive at 09:30 at reception, Floor 2",
                "Collect your laptop from the IT desk in room 3B",
                "Lunch with your onboarding buddy, who is assigned before you join",
            ],
        ),
        (
            "Your first two weeks",
            [
                "Complete the mandatory security and compliance trainings within 14 days",
                "Set up MFA on day one",
                "Meet your manager for a 30-60-90 day plan",
            ],
        ),
        (
            "Who to contact",
            [
                "IT problems: it-desk@acme-demo.com or extension 4400",
                "HR and payroll questions: hr@acme-demo.com",
                "Your onboarding buddy for everything else",
            ],
        ),
    ]
    for title, bullets in slides:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = title
        body = slide.placeholders[1].text_frame
        body.text = bullets[0]
        for b in bullets[1:]:
            body.add_paragraph().text = b
        for p in body.paragraphs:
            for r in p.runs:
                r.font.size = Pt(20)
    prs.save(str(path))


TRANSCRIPT = """Atlas weekly sync, 20 October 2026
Attendees: Priya Nair (PM), Rohit Mehta (tech lead), Sara Lindqvist (QA), Daniel Okafor (COO)

Priya: Thanks everyone. Main topics: the pilot feedback, the payment vendor delay and load testing.
Sara: Pilot feedback is mostly positive. Customers like the invoice download. Three customers \
asked for a dark mode, and two reported slow page loads on the dashboard.
Rohit: The slow loads are from the dashboard query. I can fix that this sprint.
Daniel: What about the payment vendor? Are we still on for the first of December?
Rohit: Their API is three weeks late. If it isn't ready by 10 November we can't launch online \
payments on time.
Daniel: Then we launch on the first of December without online payments and add them later. \
I don't want to move the launch date.
Priya: Agreed. Decision: the launch date stays 1 December; online payments may follow \
in a later release.
Sara: For load testing I need the staging environment sized like production.
Rohit: I'll ask the platform team for that by Friday.
Priya: Action items then. Rohit fixes the dashboard query by 31 October. Rohit requests the \
production-sized staging environment by 24 October. Sara runs the load test with five thousand \
users once staging is ready. I'll send the pilot survey to all forty customers by 27 October.
Daniel: And someone should check with the vendor every week.
Priya: I'll take that. Open question: do we build dark mode before launch? Let's decide next week.
Priya: Thanks all.
"""


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    TRANSCRIPTS.mkdir(exist_ok=True)
    write_pdf(
        DOCS / "hr_policy.pdf",
        "Acme Corporation: HR Policy",
        "Version 3.2, effective 1 January 2026. Owner: People Team.",
        HR_POLICY,
    )
    write_docx(
        DOCS / "travel_policy.docx",
        "Acme Corporation: Travel and Expense Policy",
        "Version 2.0, effective 1 April 2026. Owner: Finance.",
        TRAVEL_POLICY,
    )
    write_pdf(
        DOCS / "it_security_policy.pdf",
        "Acme Corporation: IT Security Policy",
        "Version 1.4, effective 15 February 2026. Owner: IT Security.",
        IT_SECURITY,
    )
    write_docx(
        DOCS / "project_atlas_status.docx",
        "Project Atlas: Sprint 7 Status Report",
        "Prepared by Priya Nair, 18 October 2026.",
        ATLAS_STATUS,
    )
    write_pdf(
        DOCS / "benefits_overview.pdf",
        "Acme Corporation: Employee Benefits 2026",
        "Owner: People Team.",
        BENEFITS,
    )
    write_q3_sales(DOCS / "q3_sales.xlsx")
    write_onboarding(DOCS / "onboarding_guide.pptx")
    (TRANSCRIPTS / "atlas_weekly_sync.txt").write_text(TRANSCRIPT, encoding="utf-8")
    for p in sorted([*DOCS.iterdir(), *TRANSCRIPTS.iterdir()]):
        print(f"{p.relative_to(EVAL_DIR)}  ({p.stat().st_size // 1024 or 1} KB)")


if __name__ == "__main__":
    main()
