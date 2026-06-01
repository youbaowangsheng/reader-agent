"""CLI entry: poetry run python -m reader_agent <path>"""
import sys
from pathlib import Path
from reader_agent.service import generate_note_for_file


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m reader_agent <pdf_path|epub_path|folder_path>")
        sys.exit(1)

    target_path = Path(sys.argv[1]).expanduser().resolve()
    if not target_path.exists():
        print(f"Not found: {target_path}")
        sys.exit(1)

    if target_path.is_dir():
        print("Folder mode is not implemented in CLI yet. Use Streamlit for batch processing.")
        sys.exit(1)

    print(f"📖 File: {target_path}")
    print("🤖 Generating note...\n")
    result = generate_note_for_file(target_path)
    print(f"✅ Done: {result.note_path}")
    print(f"🔎 Index: {result.index_path}")


if __name__ == "__main__":
    main()
