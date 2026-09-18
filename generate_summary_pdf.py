import os
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Preformatted
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

# Palette: Electric Blue & Cyan with Slate Neutrals
PRIMARY_BLUE = HexColor("#1d4ed8")   # Deep Blue 700
ACCENT_BLUE  = HexColor("#2563eb")   # Royal Blue 600
CYAN_ACCENT  = HexColor("#0284c7")   # Sky Cyan 600
LIGHT_BG     = HexColor("#f8fafc")   # Slate 50
CARD_BG      = HexColor("#f1f5f9")   # Slate 100
BORDER_COLOR = HexColor("#cbd5e1")   # Slate 300
TEXT_DARK    = HexColor("#0f172a")   # Slate 900
TEXT_MUTED   = HexColor("#475569")   # Slate 600
SUCCESS_GREEN= HexColor("#16a34a")   # Green 600

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        # Top Header (pages > 1)
        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(PRIMARY_BLUE)
            self.drawString(40, 805, "COGNIFY AI")
            self.setFont("Helvetica", 8)
            self.setFillColor(TEXT_MUTED)
            self.drawString(95, 805, "|   Daily Project Task Execution Tree (September 18, 2026)")
            self.setStrokeColor(BORDER_COLOR)
            self.setLineWidth(0.5)
            self.line(40, 798, 555, 798)

        # Bottom Footer (all pages)
        self.setStrokeColor(BORDER_COLOR)
        self.setLineWidth(0.5)
        self.line(40, 42, 555, 42)
        
        self.setFont("Helvetica", 8)
        self.setFillColor(TEXT_MUTED)
        self.drawString(40, 30, "Cognify — AI-Powered Academic Copilot | GitHub: kaifhussain128-dev/cognify")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(555, 30, page_str)
        self.restoreState()

def build_pdf(filename="Cognify_Project_Execution_Summary.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=45,
        bottomMargin=45
    )

    styles = getSampleStyleSheet()
    
    # Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=PRIMARY_BLUE
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=TEXT_MUTED
    )
    
    section_h1 = ParagraphStyle(
        'SectionH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=PRIMARY_BLUE,
        spaceBefore=14,
        spaceAfter=6
    )
    
    section_h2 = ParagraphStyle(
        'SectionH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=CYAN_ACCENT,
        spaceBefore=8,
        spaceAfter=4
    )

    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=TEXT_DARK
    )

    mono_tree_style = ParagraphStyle(
        'TreeMonospace',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.5,
        leading=10.5,
        textColor=HexColor("#1e293b")
    )

    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )

    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=TEXT_DARK
    )

    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=PRIMARY_BLUE
    )

    story = []

    # ==================== HEADER BLOCK ====================
    header_table_data = [
        [
            Paragraph("COGNIFY — STUDYMATE AI", title_style),
            Paragraph("<b>STATUS:</b> <font color='#16a34a'>PRODUCTION READY</font><br/><b>VERSION:</b> 1.2.0 (Stable)", ParagraphStyle('MetaRight', parent=body_style, alignment=2))
        ],
        [
            Paragraph("Comprehensive Daily Project Execution Tree & Technical Deliverables Summary", subtitle_style),
            Paragraph("<b>DATE:</b> September 18, 2026<br/><b>AUTHOR:</b> kaifhussain128-dev", ParagraphStyle('MetaRight2', parent=body_style, alignment=2))
        ]
    ]
    t_header = Table(header_table_data, colWidths=[360, 155])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 10))

    # Executive Overview Metric Bar
    metric_data = [
        [
            Paragraph("<b>Core Pillars</b><br/><font size='13' color='#1d4ed8'><b>4 Areas</b></font>", ParagraphStyle('M1', alignment=1)),
            Paragraph("<b>Key Features Built</b><br/><font size='13' color='#1d4ed8'><b>18 Completed</b></font>", ParagraphStyle('M2', alignment=1)),
            Paragraph("<b>AI Engine</b><br/><font size='13' color='#1d4ed8'><b>Google Gemini</b></font>", ParagraphStyle('M3', alignment=1)),
            Paragraph("<b>Status</b><br/><font size='13' color='#16a34a'><b>Live & Ready</b></font>", ParagraphStyle('M4', alignment=1))
        ]
    ]
    t_metric = Table(metric_data, colWidths=[128, 128, 129, 130])
    t_metric.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), LIGHT_BG),
        ('BOX', (0,0), (-1,-1), 1, BORDER_COLOR),
        ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    story.append(t_metric)
    story.append(Spacer(1, 12))

    # ==================== SECTION 1: VISUAL TREE VIEW ====================
    story.append(Paragraph("1. Summary of Everything Done Today (Simple Tree View)", section_h1))
    story.append(Paragraph(
        "Here is a simple, plain-English breakdown of all the features, design upgrades, and cloud deployment steps completed for Cognify today.",
        body_style
    ))
    story.append(Spacer(1, 6))

    tree_ascii = """COGNIFY (AI STUDY ASSISTANT) — WHAT WE BUILT TODAY
│
├── [1.0] SMART AI & STUDY CAPABILITIES
│   ├── Connected latest Google Gemini AI for smart, rapid study answers
│   ├── Added conversation memory (it remembers your previous questions)
│   ├── Built PDF Document Reader (upload lecture notes and ask questions on them)
│   ├── Added safety fallbacks so the app never crashes on AI rate limits
│   └── Added "Clear Chat" button to wipe memory and start fresh
│
├── [2.0] DESIGN, THEME & USER EXPERIENCE
│   ├── Rebranded to "Cognify" with a modern glowing synapse logo
│   ├── Upgraded color scheme from purple to modern Electric Blue & Sky Cyan
│   ├── Added Light Mode and Dark Mode switch (remembers your choice)
│   ├── Fixed bug where chat answers were hiding behind the search bar
│   ├── Made chat automatically scroll down when new answers appear
│   ├── Added Text-to-Speech button (reads AI answers out loud to you)
│   ├── Added Voice Dictation (speak into your microphone instead of typing)
│   └── Added One-Click Copy buttons for quick note-taking and code
│
├── [3.0] PHONE & MULTI-DEVICE ACCESS
│   ├── Made the site openable on any phone or tablet on the same Wi-Fi
│   ├── Fixed all website links so they work on phones without errors
│   ├── Verified Windows Firewall permissions so other devices can connect
│   └── Created an instant public web link to use the site on mobile data anywhere
│
└── [4.0] 24/7 CLOUD HOSTING & AUTOMATION
    ├── Protected secret API keys so private credentials are never leaked
    ├── Uploaded all project code to your GitHub (kaifhussain128-dev/cognify)
    ├── Created a 1-click deploy script (deploy.bat) for instant future updates
    └── Set up Render cloud hosting so the website stays online 24/7 forever"""

    tree_table = Table([[Paragraph(f"<pre>{tree_ascii}</pre>", mono_tree_style)]], colWidths=[515])
    tree_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), HexColor("#f8fafc")),
        ('BOX', (0,0), (-1,-1), 1, HexColor("#94a3b8")),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(tree_table)
    
    # Page Break for the Detailed Task Breakdowns
    story.append(PageBreak())

    # ==================== SECTION 2: DETAILED BREAKDOWNS IN PLAIN ENGLISH ====================
    story.append(Paragraph("2. Plain-English Breakdown of Every Feature", section_h1))
    story.append(Paragraph(
        "Here is what each part of the project does, explained in straightforward, non-technical language.",
        body_style
    ))
    story.append(Spacer(1, 8))

    modules = [
        {
            "id": "1.0",
            "title": "Smart AI & Study Features",
            "badge": "COMPLETED",
            "badge_color": "#16a34a",
            "rows": [
                ("1.1", "Google Gemini AI Brain", "backend/main.py", "Connected the newest Google Gemini model to answer study questions accurately with explanations, bullet points, and code."),
                ("1.2", "Continuous Memory", "Chat System", "The AI now remembers what you asked earlier in the conversation, allowing you to ask follow-up questions naturally."),
                ("1.3", "PDF Document Reader", "backend/pdf_processor.py", "You can upload study slides, assignments, or textbook chapters (PDFs) and ask questions directly about the file."),
                ("1.4", "Fresh Start Button", "POST /clear-chat", "Added a button that cleans the conversation memory and removes the attached PDF whenever you want to begin a new study topic.")
            ]
        },
        {
            "id": "2.0",
            "title": "Design, Theme & User Experience",
            "badge": "COMPLETED",
            "badge_color": "#16a34a",
            "rows": [
                ("2.1", "New Cognify Brand & Logo", "Header & Logo", "Replaced the generic title with 'Cognify' and designed a sleek glowing brain synapse logo in vibrant blue and cyan."),
                ("2.2", "Electric Blue Theme", "Colors & Styles", "Replaced the dark purple theme with a clean, high-tech electric blue and sky cyan palette with soft ambient lighting."),
                ("2.3", "Fixed Search Bar Overlap", "Chat Window", "Fixed the bug where answers got cut off behind the search bar. Now answers scroll comfortably in their own clear view."),
                ("2.4", "Light & Dark Mode Switch", "Theme Toggle", "Users can toggle between a bright, clean Light Mode and an eye-friendly Dark Mode. The website remembers your choice automatically."),
                ("2.5", "Listen (Text-to-Speech)", "Audio Player", "Added a button to have the AI read its answers out loud to you, making it easy to listen to study explanations."),
                ("2.6", "Voice Typing (Dictation)", "Microphone Button", "You can click the microphone icon and speak your question instead of typing it out on your keyboard."),
                ("2.7", "1-Click Copy Buttons", "Message Cards", "Every answer has a copy button so you can instantly paste notes, summaries, or code into your documents.")
            ]
        },
        {
            "id": "3.0",
            "title": "Phone & Multi-Device Access",
            "badge": "COMPLETED",
            "badge_color": "#16a34a",
            "rows": [
                ("3.1", "Home Wi-Fi Access", "192.168.29.77:8000", "Configured the server so you can open the app on your iPhone, Android phone, or iPad as long as you are on the same Wi-Fi."),
                ("3.2", "Universal Device Links", "frontend/index.html", "Updated all backend connections so they work automatically from any phone or computer without setup errors."),
                ("3.3", "Anywhere Public Link", "Internet Tunnel", "Created an instant public web link so you can share and test the website on cellular data or outside your home.")
            ]
        },
        {
            "id": "4.0",
            "title": "24/7 Cloud Hosting & Automation",
            "badge": "COMPLETED",
            "badge_color": "#16a34a",
            "rows": [
                ("4.1", "Safe API Key Storage", ".gitignore & .env", "Configured strict security rules so your private Google API key remains protected on your computer and is never leaked publicly."),
                ("4.2", "Code Uploaded to GitHub", "kaifhussain128-dev/cognify", "Installed GitHub tools, linked your account, and uploaded all project code to your personal GitHub repository."),
                ("4.3", "1-Click Deploy Tool", "deploy.bat", "Created a helper file (deploy.bat) so whenever you make changes in the future, 1 click sends them to GitHub and updates your live site."),
                ("4.4", "Render 24/7 Cloud Host", "render.yaml", "Configured cloud hosting settings so Cognify can run on Render's free tier 24 hours a day without your PC staying on.")
            ]
        }
    ]

    for mod in modules:
        mod_header_data = [
            [
                Paragraph(f"<b>[{mod['id']}] {mod['title']}</b>", section_h2),
                Paragraph(f"<font color='{mod['badge_color']}'><b>● {mod['badge']}</b></font>", ParagraphStyle('Bdg', parent=body_style, alignment=2))
            ]
        ]
        t_mod_head = Table(mod_header_data, colWidths=[400, 115])
        t_mod_head.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
        
        table_rows = [
            [
                Paragraph("<b>ID</b>", table_header),
                Paragraph("<b>Subtask / Feature</b>", table_header),
                Paragraph("<b>Artifact / Path</b>", table_header),
                Paragraph("<b>Implementation Details & Impact</b>", table_header)
            ]
        ]
        
        for r in mod['rows']:
            table_rows.append([
                Paragraph(r[0], table_cell_bold),
                Paragraph(r[1], table_cell_bold),
                Paragraph(f"<code>{r[2]}</code>", table_cell),
                Paragraph(r[3], table_cell)
            ])
            
        t_mod = Table(table_rows, colWidths=[30, 115, 110, 260])
        t_mod.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), PRIMARY_BLUE),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
            ('BOX', (0,0), (-1,-1), 1, PRIMARY_BLUE),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, HexColor("#f8fafc")]),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 5),
            ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ]))
        
        story.append(KeepTogether([t_mod_head, t_mod, Spacer(1, 8)]))

    # ==================== SECTION 3: PROJECT REPOSITORY & ASSETS ====================
    story.append(Spacer(1, 6))
    story.append(Paragraph("3. Final Deliverables & Repository Metadata", section_h1))
    
    repo_data = [
        [Paragraph("<b>Resource</b>", table_header), Paragraph("<b>Endpoint / Target URI</b>", table_header), Paragraph("<b>Status / Verification</b>", table_header)],
        [Paragraph("<b>GitHub Repository</b>", table_cell_bold), Paragraph("https://github.com/kaifhussain128-dev/cognify", table_cell), Paragraph("Active / Up-to-date on main", table_cell)],
        [Paragraph("<b>Cloud Platform</b>", table_cell_bold), Paragraph("https://dashboard.render.com/select-repo?type=web", table_cell), Paragraph("render.yaml blueprint linked", table_cell)],
        [Paragraph("<b>Local Network (LAN)</b>", table_cell_bold), Paragraph("http://192.168.29.77:8000", table_cell), Paragraph("Accessible via Wi-Fi", table_cell)],
        [Paragraph("<b>Public Tunnel</b>", table_cell_bold), Paragraph("https://heavy-seals-argue.loca.lt", table_cell), Paragraph("External HTTPS tunnel ready", table_cell)],
        [Paragraph("<b>Automation Tool</b>", table_cell_bold), Paragraph("Cognify/deploy.bat", table_cell), Paragraph("1-Click automated deployer", table_cell)]
    ]
    t_repo = Table(repo_data, colWidths=[120, 245, 150])
    t_repo.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), CYAN_ACCENT),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('BOX', (0,0), (-1,-1), 1, CYAN_ACCENT),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, HexColor("#f8fafc")]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_repo)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF generated successfully: {filename}")

if __name__ == "__main__":
    out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Cognify_Project_Execution_Summary.pdf")
    build_pdf(out_file)
