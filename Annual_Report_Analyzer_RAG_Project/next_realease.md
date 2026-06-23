# Next Release — Planned Features

---

## Feature: User-Scoped Document Deletion

A user can only delete documents they personally uploaded. Documents
uploaded by other users remain visible in the knowledge base for querying
but cannot be deleted by anyone other than the original uploader.

**Key points:**

- Document ownership is established at upload time by embedding the
  username as a suffix in the filename:
  `Salesforce-FY25-Annual-Report-john_doe.pdf`
- The delete button is shown only on documents the current user owns;
  it is hidden for all other documents
- Ownership is enforced server-side on every delete request — the
  frontend restriction alone is not relied upon
- Two different users can upload the same company report without conflict;
  they are stored as separate documents
- If a delete is attempted on a document the user does not own, an error
  message is displayed: *"You do not have permission to delete this document."*
- Documents uploaded before this feature is released have no recorded
  owner and cannot be deleted through the UI until ownership is assigned