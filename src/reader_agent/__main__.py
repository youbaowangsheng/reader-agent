"""CLI entry: poetry run python -m reader_agent <path>"""
import sys
from pathlib import Path
from reader_agent.graph import build_agent


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m reader_agent <pdf_path|epub_path|folder_path>")
        sys.exit(1)

    target_path = Path(sys.argv[1]).expanduser().resolve()
    if not target_path.exists():
        print(f"Not found: {target_path}")
        sys.exit(1)

    is_dir = target_path.is_dir()
    file_type = "folder" if is_dir else target_path.suffix.lower()
    print(f"📖 {'Folder' if is_dir else file_type.upper()}: {target_path}")
    print("🤖 Agent working...\n")

    agent = build_agent()
    result = agent.invoke({
        "messages": [{
            "role": "user",
            "content": f"请阅读并生成笔记：{target_path}"
        }]
    })

    for msg in result["messages"]:
        if msg.type == "ai":
            print(msg.content)
        elif msg.type == "tool":
            print(f"🔧 {msg.name}: {str(msg.content)[:300]}...")

    print("\n✅ Done")


if __name__ == "__main__":
    main()
