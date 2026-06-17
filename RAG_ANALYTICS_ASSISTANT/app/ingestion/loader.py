from langchain_community.document_loaders import TextLoader
# TextLoader is a LangChain class that reads a plain text (.txt) file whole
# the entire file becomes ONE Document object with .page_content and .metadata
# there is no page-by-page split — that only applies to loaders like PyPDFLoader
# we import only TextLoader because all 5 source files are .txt

from app.utils.logger import get_logger, log_event
# get_logger  → creates a named logger for this module
# log_event   → writes a structured key=value line to the log file

from app.config import settings
# settings holds all config values loaded from .env
# we need settings.DOCS_DIR to know where the .txt files live

log = get_logger(__name__)
# __name__ is automatically "app.ingestion.loader" inside this file
# every log line from this module will show that name as the source
# this makes it easy to find which file produced a log line


def load() -> list:
# define a function called load that takes no arguments
# -> list means it returns a list (of Document objects)
# this is called by ingest.py to get one Document per .txt file

  docs_dir = settings.DOCS_DIR
  # settings.DOCS_DIR is defined in settings.py as BASE_DIR / "docs"
  # we assign it to a local variable docs_dir for convenience
  # we do NOT rebuild it here with Path(BASE_DIR) / "docs" — that would be duplication

  documents = []
  # start with an empty list
  # one Document object per .txt file will be added here (TextLoader does not split by page)
  # by the end of the loop this will contain 5 Documents — one per .txt file

  for filepath in sorted(docs_dir.iterdir()):
  # docs_dir.iterdir() returns every item inside docs/ as a Path object
  # sorted() ensures files are always processed in alphabetical order
  # without sorted() different operating systems return files in different orders
  # filepath is a Path object e.g. /home/you/docs/sales_playbook.txt

    if filepath.suffix.lower() == ".txt" and filepath.stat().st_size == 0:
    # skip 0-byte .txt files silently — no warning logged
    # known gap: a better version would log a warning here
      continue

    if filepath.suffix.lower() != ".txt":
    # skip non-.txt files silently (e.g. .DS_Store, README.md, stray .pdf)
      continue

    loader = TextLoader(str(filepath))
    # create a TextLoader instance for this specific .txt file
    # str(filepath) converts the Path object to a plain string
    # TextLoader expects a string path — passing a Path object may cause a TypeError

    docs = loader.load()
    # loader.load() reads the entire .txt file in one go
    # returns a list with exactly ONE Document object — TextLoader does not page-split
    # a single .txt file always returns [Doc] — never more than one element
    # that Document has:
    #   .page_content → the full text content of the file
    #   .metadata     → {"source": "/path/to/file.txt"}
    # there is no "page" key in metadata — that only exists for PDF-style loaders

    documents.extend(docs)
    # .extend() adds the Document from docs individually into our documents list
    # result stays a flat list: [Doc, Doc, Doc, Doc, Doc] — one per file
    # if we used .append(docs) instead it would create a nested list:
    #   [[Doc], [Doc], ...] — chunker.py cannot handle this

    log_event(log, "info", "file_loaded",
                  file=filepath.name,
                  pages=len(docs))
    # log a structured line for this specific file
    # filepath.name is just the filename e.g. "sales_playbook.txt" (not the full path)
    # len(docs) is always 1 here since TextLoader returns one Document per file
    # "pages" is a leftover/generic field name — for .txt it is always 1, not a real page count
    # appears in logs as: event=file_loaded file=sales_playbook.txt pages=1
    # this is inside the loop so it runs once per .txt file — correct

  txt_count = len([f for f in docs_dir.iterdir()
                     if f.suffix.lower() == ".txt"])
  # this line is OUTSIDE the loop — runs once after all files are processed
  # counts how many .txt files exist in docs/ regardless of whether they were loaded
  # [f for f in docs_dir.iterdir() if f.suffix.lower() == ".txt"] builds a list of .txt files
  # len(...) counts how many items are in that list
  # used in the summary log line below

  log_event(log, "info", "documents_loaded",
              total_pages=len(documents),
              files=txt_count)
  # log a final summary of the entire load operation
  # this is OUTSIDE the loop — runs once after all .txt files are processed
  # total_pages = total number of Document objects across all files (e.g. 5, one per file)
  # "total_pages" is a leftover field name from a PDF-oriented version — for .txt
  #   it equals the number of files loaded, not a true page count
  # files       = number of .txt files found in docs/ (e.g. 5)
  # appears in logs as: event=documents_loaded total_pages=5 files=5

  return documents
  # return the complete flat list of Document objects to whoever called load()
  # this is OUTSIDE the loop — if it were inside, it would return after the first file
  # ingest.py receives this list and passes it to chunker.py for splitting