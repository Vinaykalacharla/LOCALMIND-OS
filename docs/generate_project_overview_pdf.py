from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    PageBreak,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUT_FILE = ROOT / "docs" / "LocalMind_OS_Project_Overview.pdf"


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="TitleCenter",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=colors.HexColor("#F5F7FB"),
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SubCenter",
            parent=styles["BodyText"],
            alignment=TA_CENTER,
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#CBD5E1"),
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PageTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#111827"),
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=14.5,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Small",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#4B5563"),
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionHeader",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12.5,
            leading=16,
            textColor=colors.HexColor("#0F172A"),
            spaceBefore=6,
            spaceAfter=4,
        )
    )
    return styles


def bullet_list(items, styles, bullet_color="#2563EB"):
    return ListFlowable(
        [
            ListItem(
                Paragraph(item, styles["Body"]),
                leftIndent=8,
            )
            for item in items
        ],
        bulletType="bullet",
        bulletFontName="Helvetica-Bold",
        bulletFontSize=9,
        bulletColor=colors.HexColor(bullet_color),
        leftIndent=16,
    )


def page_frame(canvas, doc):
    page_num = canvas.getPageNumber()
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#0F172A"))
    canvas.rect(0, height - 22 * mm, width, 22 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(16 * mm, height - 13 * mm, "LocalMind OS")
    canvas.setFont("Helvetica", 8.5)
    canvas.drawRightString(width - 16 * mm, 10 * mm, f"Page {page_num}")
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(16 * mm, 8.7 * mm, "Project overview and workflow explanation")
    canvas.restoreState()


def cover_page(styles):
    story = []
    story.append(Spacer(1, 42 * mm))
    story.append(Paragraph("LocalMind OS", styles["TitleCenter"]))
    story.append(Paragraph("Project Overview, Architecture, and End-to-End Workflow", styles["SubCenter"]))
    story.append(Spacer(1, 8 * mm))
    story.append(
        Paragraph(
            "This document explains what the project does, how the frontend and backend work together, "
            "and what happens step by step when a user uploads a PDF, searches it, or asks a grounded question.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("What this PDF covers", styles["SectionHeader"]))
    story.append(
        bullet_list(
            [
                "What LocalMind OS is and why it exists",
                "How the application is structured",
                "What happens when a PDF is uploaded",
                "How chunking, embeddings, and indexing work",
                "How search and trust-mode chat produce answers",
                "Which models and fallbacks the app uses today",
            ],
            styles,
        )
    )
    return story


def section_page(title, paragraphs, bullets=None, note=None, styles=None):
    story = [Spacer(1, 18 * mm), Paragraph(title, styles["PageTitle"])]
    for paragraph in paragraphs:
        story.append(Paragraph(paragraph, styles["Body"]))
    if bullets:
        story.append(Spacer(1, 2 * mm))
        story.append(bullet_list(bullets, styles))
    if note:
        story.append(Spacer(1, 3 * mm))
        story.append(
            Paragraph(
                f"<b>Example:</b> {note}",
                styles["Small"],
            )
        )
    return story


def architecture_page(styles):
    story = [Spacer(1, 18 * mm), Paragraph("2. What the Project Is", styles["PageTitle"])]
    story.append(
        Paragraph(
            "LocalMind OS is a local-first knowledge workspace. It lets a user upload private documents, "
            "turn them into searchable chunks, ask grounded questions, and explore related topics without "
            "sending the data to a cloud service by default.",
            styles["Body"],
        )
    )
    story.append(
        Paragraph(
            "The frontend is a Next.js app, while the backend is a FastAPI service. The backend owns the "
            "document pipeline, search pipeline, knowledge graph, security vault, and model selection.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 2 * mm))
    table = Table(
        [
            ["Layer", "Role"],
            ["Frontend", "Upload, search, chat, model controls, graph and evaluation views"],
            ["Backend", "Ingestion, chunking, embeddings, retrieval, RAG, security, persistence"],
            ["Storage", "Encrypted runtime data under backend/data and uploaded files under backend/data/uploads"],
            ["Models", "Local embeddings, optional reranker, local GGUF LLM or extractive fallback"],
        ],
        colWidths=[42 * mm, 118 * mm],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.2),
                ("LEADING", (0, 0), (-1, -1), 11),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)
    story.append(
        Paragraph(
            "The core idea is simple: documents come in, are transformed into smaller meaning-rich pieces, "
            "and those pieces are made available for search and answer generation.",
            styles["Body"],
        )
    )
    return story


def workflow_page(styles):
    story = [Spacer(1, 18 * mm), Paragraph("3. End-to-End Workflow", styles["PageTitle"])]
    story.append(
        Paragraph(
            "The app follows a consistent pipeline. First, a file is uploaded. Then the backend extracts text, "
            "chunks the content, embeds each chunk, stores the vectors, and updates the graph and metadata. "
            "After that, the data becomes available for search, chat, and analytics.",
            styles["Body"],
        )
    )
    story.append(
        bullet_list(
            [
                "User selects files in the frontend.",
                "Frontend calls POST /ingest with the files.",
                "Backend stores uploads in backend/data/uploads.",
                "Text is extracted from PDFs or other supported formats.",
                "chunk_document() splits content into structured chunks.",
                "EmbeddingService converts chunks into vectors.",
                "VectorIndex stores those vectors in FAISS or NumPy fallback.",
                "Search and chat use the indexed chunks as evidence.",
            ],
            styles,
        )
    )
    story.append(
        Paragraph(
            "This design keeps the system offline-friendly and makes every stage inspectable. The same uploaded "
            "source can be reused for semantic search, grounded chat, and graph generation.",
            styles["Body"],
        )
    )
    return story


def upload_page(styles):
    story = [Spacer(1, 18 * mm), Paragraph("4. What Happens When You Upload a PDF", styles["PageTitle"])]
    story.append(
        Paragraph(
            "When a PDF is uploaded, the backend first validates that the app is unlocked. The file is saved to "
            "disk and a background ingestion job is created so the frontend can keep polling job status.",
            styles["Body"],
        )
    )
    story.append(
        bullet_list(
            [
                "The upload endpoint is POST /ingest.",
                "Files are stored with their original names under the uploads directory.",
                "The job status endpoint lets the UI show progress.",
                "Duplicate source files are skipped during ingestion if already indexed.",
                "The system can also ingest built-in demo files through /ingest_demo.",
            ],
            styles,
        )
    )
    story.append(Paragraph("Concrete example", styles["SectionHeader"]))
    story.append(
        Paragraph(
            "Suppose you upload <b>ML_Loss_Comparison.pdf</b>. The backend keeps the original PDF, extracts text "
            "page by page, and then passes the text to the chunking pipeline. The file then becomes searchable "
            "and usable in chat without any manual labeling.",
            styles["Body"],
        )
    )
    return story


def chunking_page(styles):
    story = [Spacer(1, 18 * mm), Paragraph("5. How Chunking Is Done", styles["PageTitle"])]
    story.append(
        Paragraph(
            "Chunking is the step that turns large documents into smaller retrieval units. In this project, "
            "the backend uses a structured chunker with heading awareness and overlap. The current chunking "
            "version is <b>structured-v3</b>.",
            styles["Body"],
        )
    )
    story.append(
        bullet_list(
            [
                "The backend calls chunk_document(doc.text, chunk_size=900, overlap=150).",
                "Headings are preserved as a section path, such as Section: Chapter 2 > Loss Functions.",
                "Paragraphs, lists, and long sentences are split differently so chunks stay readable.",
                "Adjacent chunks share overlap so context is not lost at boundaries.",
            ],
            styles,
        )
    )
    story.append(Paragraph("Example chunking flow", styles["SectionHeader"]))
    story.append(
        Paragraph(
            "If a PDF page contains a section called <b>Loss Functions</b> with three paragraphs, the first chunk "
            "may contain the heading plus the first paragraph, and the second chunk may reuse the last part of the "
            "first chunk as overlap. That means a query about the transition between two ideas can still be answered "
            "from retrieval.",
            styles["Body"],
        )
    )
    story.append(
        Paragraph(
            "This is important because retrieval works better when each chunk is a self-contained evidence unit "
            "instead of a raw page dump.",
            styles["Body"],
        )
    )
    return story


def models_page(styles):
    story = [Spacer(1, 18 * mm), Paragraph("6. Which Models the App Uses", styles["PageTitle"])]
    story.append(
        Paragraph(
            "The app uses a layered model strategy rather than a single fixed model. The selected model depends on "
            "what is available on the machine and what the user has configured in the model manager.",
            styles["Body"],
        )
    )
    table = Table(
        [
            ["Component", "Current behavior"],
            ["LLM", "Defaults to extractive-fallback at startup; can switch to a local GGUF model via llama-cpp-python"],
            ["Embeddings", "Tries sentence-transformers/all-MiniLM-L6-v2 or local embedding folders first"],
            ["Embedding fallback", "Uses hashed TF-IDF if no sentence-transformer model loads"],
            ["Vector index", "Uses FAISS when installed, otherwise NumPy similarity fallback"],
            ["Reranker", "Optional local cross-encoder; otherwise lexical reranking only"],
        ],
        colWidths=[42 * mm, 118 * mm],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.1),
                ("LEADING", (0, 0), (-1, -1), 11),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)
    story.append(
        Paragraph(
            "In practice, the default setup is intentionally safe for a laptop: the backend does not require a "
            "cloud API key, and it can still function even when a higher-end local model is not installed.",
            styles["Body"],
        )
    )
    return story


def indexing_page(styles):
    story = [Spacer(1, 18 * mm), Paragraph("7. How Indexing and Search Work", styles["PageTitle"])]
    story.append(
        Paragraph(
            "After chunking, the embedding service converts each chunk into a numerical vector. The vector index "
            "stores those vectors so the app can find similar chunks when the user searches.",
            styles["Body"],
        )
    )
    story.append(
        bullet_list(
            [
                "EmbeddingService first tries a sentence-transformers model.",
                "If that is unavailable, it falls back to hashed TF-IDF.",
                "VectorIndex stores the embeddings in FAISS or in-memory NumPy similarity.",
                "Search combines vector similarity with lexical scoring and diversity selection.",
                "A reranker can improve ordering when a local cross-encoder is installed.",
            ],
            styles,
        )
    )
    story.append(Paragraph("Search example", styles["SectionHeader"]))
    story.append(
        Paragraph(
            "If the user searches for <b>How does cross entropy compare to hinge loss?</b>, the backend builds an "
            "embedding for that question, retrieves the nearest chunks, adds lexical variants, and then reranks the "
            "results so the most relevant chunk appears first.",
            styles["Body"],
        )
    )
    return story


def chat_page(styles):
    story = [Spacer(1, 18 * mm), Paragraph("8. How Grounded Chat Produces an Answer", styles["PageTitle"])]
    story.append(
        Paragraph(
            "The ask endpoint uses the search pipeline as its evidence source. It retrieves chunks, evaluates how "
            "strong the evidence is, and then decides whether to answer directly, fall back to extractive answering, "
            "or refuse weakly grounded requests in trust mode.",
            styles["Body"],
        )
    )
    story.append(
        bullet_list(
            [
                "The frontend sends a question to POST /ask.",
                "The backend optionally follows chat history for follow-up questions.",
                "Relevant chunks become cited sources like S1, S2, and S3.",
                "If evidence is weak, trust mode can return a refusal or a short extractive answer.",
                "If a GGUF model is available, rag_engine.generate_answer() can produce the final response.",
            ],
            styles,
        )
    )
    story.append(Paragraph("Why this matters", styles["SectionHeader"]))
    story.append(
        Paragraph(
            "This keeps answers grounded in the uploaded documents instead of letting the model invent details. "
            "The chat experience is therefore tied to the actual corpus you uploaded.",
            styles["Body"],
        )
    )
    return story


def walkthrough_page(styles):
    story = [Spacer(1, 18 * mm), Paragraph("9. Worked Example", styles["PageTitle"])]
    story.append(
        Paragraph(
            "Here is a complete example from upload to answer generation.",
            styles["Body"],
        )
    )
    story.append(Paragraph("Step-by-step example", styles["SectionHeader"]))
    story.append(
        bullet_list(
            [
                "You upload a PDF about machine learning losses.",
                "The backend extracts text and splits it into structured chunks.",
                "A chunk may look like: Section: Loss Functions > Hinge Loss ...",
                "The embedding model turns that chunk into a vector.",
                "The index stores the vector and metadata such as source file and page number.",
                "You ask: What is the difference between hinge loss and cross entropy?",
                "Search retrieves the most relevant chunks and chat uses them as sources.",
            ],
            styles,
        )
    )
    story.append(Paragraph("Example output shape", styles["SectionHeader"]))
    story.append(
        Paragraph(
            "The answer may include a direct explanation, a short comparison, and citations like [S1] and [S2]. "
            "If the question is a study task, the same sources can be reformatted into a guide, flashcards, or a quiz.",
            styles["Body"],
        )
    )
    return story


def security_page(styles):
    story = [Spacer(1, 18 * mm), Paragraph("10. Security, Storage, and Closing Notes", styles["PageTitle"])]
    story.append(
        Paragraph(
            "LocalMind OS is designed to keep data local. The backend stores uploads, chunks, graph data, query logs, "
            "and model settings under backend/data, and the vault layer encrypts persisted runtime artifacts when the "
            "passphrase is configured.",
            styles["Body"],
        )
    )
    story.append(
        bullet_list(
            [
                "First launch asks the user to create a passphrase.",
                "Later launches require the same passphrase to unlock the backend.",
                "If the passphrase is lost, encrypted runtime data cannot be recovered through the app.",
                "The app still works in fallback modes even when high-end local models are not installed.",
            ],
            styles,
        )
    )
    story.append(Paragraph("Summary", styles["SectionHeader"]))
    story.append(
        Paragraph(
            "The project is a local knowledge workspace built around a reliable retrieval pipeline: upload, "
            "extract, chunk, embed, index, retrieve, and answer with evidence. That is the full loop the user sees "
            "in the product.",
            styles["Body"],
        )
    )
    story.append(
        Paragraph(
            "If you add stronger local models later, the architecture already supports them without changing the "
            "basic workflow.",
            styles["Body"],
        )
    )
    return story


def build_pdf():
    styles = build_styles()
    doc = SimpleDocTemplate(
        str(OUT_FILE),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=28 * mm,
        bottomMargin=18 * mm,
        title="LocalMind OS Project Overview",
        author="Codex",
        subject="Project overview and workflow explanation",
    )

    story = []
    story.extend(cover_page(styles))
    story.append(PageBreak())
    story.extend(architecture_page(styles))
    story.append(PageBreak())
    story.extend(workflow_page(styles))
    story.append(PageBreak())
    story.extend(upload_page(styles))
    story.append(PageBreak())
    story.extend(chunking_page(styles))
    story.append(PageBreak())
    story.extend(models_page(styles))
    story.append(PageBreak())
    story.extend(indexing_page(styles))
    story.append(PageBreak())
    story.extend(chat_page(styles))
    story.append(PageBreak())
    story.extend(walkthrough_page(styles))
    story.append(PageBreak())
    story.extend(security_page(styles))

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    doc.build(story, onFirstPage=page_frame, onLaterPages=page_frame)


if __name__ == "__main__":
    build_pdf()
    print(f"Created {OUT_FILE}")
