import sys
from .prompt_workbook_manager import PromptWorkbookManager


def main():
    if len(sys.argv) != 2:
        print("Usage: python manage_prompt_workbook.py <workbook_path>")
        sys.exit(1)

    workbook_path = sys.argv[1]
    manager = PromptWorkbookManager(workbook_path)
    manager.create_or_update_workbook()


if __name__ == "__main__":
    main()
