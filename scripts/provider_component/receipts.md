# Recording Admin documentation changes
[receipts.py](receipts.py) implements the standalone `receipt` operation in [review.py](review.py). Its sole write target is `00-governance/types/document-reviews.json`.
The operator or selected Admin names the maintained Markdown documents in the authorized Admin scope. The writer checks each path with the existing ownership policy, reads the actual bytes, compares them to HEAD and uses the shared documentation receipt builder. A repeated current receipt is skipped.
A directory lock serializes cooperating receipt writers. The existing file transaction checks the prior bytes and replaces the file. The operation owns the event type, hashes, time and null human approval. Existing events and metadata are preserved.
