from langchain_community.document_loaders import TextLoader
# TextLoader is a LangChain class that reads a PDF file page by page
# each page becomes one Document object with .page_content and .metadata
# we import only TextLoader because all 5 source files are PDFs

from app.utils.logger import get_logger, log_event
# get_logger  → creates a named logger for this module
# log_event   → writes a structured key=value line to the log file

from app.config import settings
# settings holds all config values loaded from .env
# we need settings.DOCS_DIR to know where the PDF files live

log = get_logger(__name__)
# __name__ is automatically "app.ingestion.loader" inside this file
# every log line from this module will show that name as the source
# this makes it easy to find which file produced a log line


def load() -> list:
# define a function called load that takes no arguments
# -> list means it returns a list (of Document objects)
# this is called by ingest.py to get all pages from all PDFs

  docs_dir = settings.DOCS_DIR
  # settings.DOCS_DIR is defined in settings.py as BASE_DIR / "docs"
  # we assign it to a local variable docs_dir for convenience
  # we do NOT rebuild it here with Path(BASE_DIR) / "docs" — that would be duplication

  documents = []
  # start with an empty list
  # every Document object loaded from every PDF page will be added here
  # by the end of the loop this will contain 20 Documents (one per page)

  for filepath in sorted(docs_dir.iterdir()):
  # docs_dir.iterdir() returns every item inside docs/ as a Path object
  # sorted() ensures files are always processed in alphabetical order
  # without sorted() different operating systems return files in different orders
  # filepath is a Path object e.g. /home/you/docs/sales_playbook.pdf

    if filepath.suffix.lower() == ".txt" and filepath.stat().st_size == 0:
    # skip 0-byte PDF files silently — no warning logged
    # known gap: a better version would log a warning here
      continue

    if filepath.suffix.lower() != ".txt":
    # skip non-PDF files silently
      continue

    loader = TextLoader(str(filepath))
    # create a TextLoader instance for this specific PDF file
    # str(filepath) converts the Path object to a plain string
    # TextLoader expects a string path — passing a Path object may cause a TypeError

    docs = loader.load()
    # loader.load() reads every page of the PDF
    # returns a list of Document objects — one per page
    # a 4-page PDF returns [Doc, Doc, Doc, Doc]
    # each Document has:
    #   .page_content → text extracted from that page
    #   .metadata     → {"source": "/path/to/file.pdf", "page": 0}
    # "page" in metadata is 0-indexed so first page = 0, second page = 1

    documents.extend(docs)
    # .extend() adds each Document from docs individually into our documents list
    # result stays a flat list: [Doc, Doc, Doc, Doc, Doc, ...]
    # if we used .append(docs) instead it would create a nested list:
    #   [[Doc, Doc], [Doc, Doc, Doc], ...] — chunker.py cannot handle this

    log_event(log, "info", "file_loaded",
                  file=filepath.name,
                  pages=len(docs))
    # log a structured line for this specific file
    # filepath.name is just the filename e.g. "sales_playbook.pdf" (not the full path)
    # len(docs) is the number of pages loaded from this file
    # appears in logs as: event=file_loaded file=sales_playbook.pdf pages=4
    # this is inside the loop so it runs once per PDF file — correct

  pdf_count = len([f for f in docs_dir.iterdir()
                     if f.suffix.lower() == ".txt"])
  # this line is OUTSIDE the loop — runs once after all files are processed
  # counts how many .pdf files exist in docs/ regardless of whether they were loaded
  # [f for f in docs_dir.iterdir() if f.suffix.lower() == ".pdf"] builds a list of PDFs
  # len(...) counts how many items are in that list
  # used in the summary log line below

  log_event(log, "info", "documents_loaded",
              total_pages=len(documents),
              files=pdf_count)
  # log a final summary of the entire load operation
  # this is OUTSIDE the loop — runs once after all PDFs are processed
  # total_pages = total number of Document objects across all PDFs (e.g. 20)
  # files       = number of PDF files found in docs/ (e.g. 5)
  # appears in logs as: event=documents_loaded total_pages=20 files=5

  return documents
  # return the complete flat list of Document objects to whoever called load()
  # this is OUTSIDE the loop — if it were inside, it would return after the first PDF
  # ingest.py receives this list and passes it to chunker.py for splitting