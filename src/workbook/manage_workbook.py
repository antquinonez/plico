import sys
from .workbook_manager import WorkbookManager


def main():
    if len(sys.argv) != 2:
        print("Usage: python manage_workbook.py <path_to_parquet_file>")
        sys.exit(1)

    parquet_path = sys.argv[1]
    try:
        manager = WorkbookManager(parquet_path)
        manager.create_or_update_workbook()
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    main()
