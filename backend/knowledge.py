import re
from pathlib import Path


class KnowledgeBase:
    """Local lexical retrieval, replaceable without changing the agent tool interface."""
    def __init__(self, root=None):
        self.root = Path(root or Path(__file__).resolve().parents[1]/"knowledge"/"elasticsearch")

    def search(self, query: str, limit: int = 4):
        words = set(re.findall(r"[a-z]{3,}", query.lower()))
        ranked = []
        for path in self.root.glob("*.md"):
            text = path.read_text(encoding="utf-8")
            score = sum(text.lower().count(word) for word in words)
            if score:
                lines = text.splitlines()
                source = next((x[8:] for x in lines if x.startswith("Source: ")), "")
                ranked.append((score, {"id": path.stem, "title": lines[0].lstrip("# "), "source": source, "excerpt": text[:2000]}))
        return [x[1] for x in sorted(ranked, key=lambda x: x[0], reverse=True)[:limit]]
