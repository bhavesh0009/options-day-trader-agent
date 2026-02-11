#!/usr/bin/env python3
"""
Database Cleanup Script for ODTA

Clears test/runtime data from the database while preserving market data.

Usage:
    python cleanup_db.py              # Interactive mode with confirmation
    python cleanup_db.py --force      # Skip confirmation (use with caution)
    python cleanup_db.py --dry-run    # Show what would be deleted without deleting
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from odta.db.connection import get_db_connection


def get_table_counts(conn):
    """Get row counts for all tables."""
    tables = {
        # Runtime tables (will be cleaned)
        "trade_diary": "Runtime",
        "decision_log": "Runtime",
        "paper_positions": "Runtime",
        # Reference tables (will be preserved)
        "fno_stocks": "Reference",
        "daily_ohlcv": "Reference",
        "index_ohlcv": "Reference",
        "ban_list": "Reference",
    }

    counts = {}
    for table, table_type in tables.items():
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            counts[table] = {"count": count, "type": table_type}
        except Exception as e:
            counts[table] = {"count": "ERROR", "type": table_type, "error": str(e)}

    return counts


def print_table_counts(counts, title="Current Database State"):
    """Print table counts in a formatted way."""
    print(f"\n{'='*70}")
    print(f"{title:^70}")
    print(f"{'='*70}")

    # Group by type
    runtime_tables = {k: v for k, v in counts.items() if v.get("type") == "Runtime"}
    reference_tables = {k: v for k, v in counts.items() if v.get("type") == "Reference"}

    print(f"\n{'RUNTIME TABLES (WILL BE CLEANED)':^70}")
    print(f"{'-'*70}")
    for table, info in runtime_tables.items():
        count = info["count"]
        if count == "ERROR":
            print(f"  {table:.<30} ERROR: {info.get('error', 'Unknown')}")
        else:
            print(f"  {table:.<30} {count:>10,} rows")

    print(f"\n{'REFERENCE TABLES (WILL BE PRESERVED)':^70}")
    print(f"{'-'*70}")
    for table, info in reference_tables.items():
        count = info["count"]
        if count == "ERROR":
            print(f"  {table:.<30} ERROR: {info.get('error', 'Unknown')}")
        else:
            print(f"  {table:.<30} {count:>10,} rows")

    print(f"{'='*70}\n")


def cleanup_database(conn, dry_run=False):
    """Clean runtime tables and reset sequences."""
    runtime_tables = [
        "trade_diary",
        "decision_log",
        "paper_positions",
    ]

    deleted_counts = {}

    for table in runtime_tables:
        try:
            # Get count before deletion
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            deleted_counts[table] = count

            if not dry_run and count > 0:
                # Delete all rows
                conn.execute(f"DELETE FROM {table}")

                # Reset sequence
                sequence_name = f"{table}_id_seq"
                try:
                    conn.execute(f"DROP SEQUENCE IF EXISTS {sequence_name}")
                    conn.execute(f"CREATE SEQUENCE {sequence_name} START 1")
                except Exception as seq_error:
                    print(f"  Warning: Could not reset sequence for {table}: {seq_error}")

        except Exception as e:
            print(f"  Error cleaning {table}: {e}")
            deleted_counts[table] = f"ERROR: {e}"

    return deleted_counts


def main():
    """Main cleanup function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Clean test/runtime data from ODTA database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt (use with caution)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )

    args = parser.parse_args()

    try:
        conn = get_db_connection()

        # Show current state
        before_counts = get_table_counts(conn)
        print_table_counts(before_counts, "BEFORE CLEANUP")

        # Calculate total rows to delete
        total_to_delete = sum(
            v["count"] for v in before_counts.values()
            if v.get("type") == "Runtime" and isinstance(v["count"], int)
        )

        if total_to_delete == 0:
            print("✅ Database is already clean. No runtime data to delete.\n")
            return

        # Dry run mode
        if args.dry_run:
            print("🔍 DRY RUN MODE - No changes will be made")
            print(f"\nWould delete {total_to_delete:,} total rows from runtime tables.\n")
            return

        # Confirmation prompt (unless --force)
        if not args.force:
            print(f"⚠️  This will DELETE {total_to_delete:,} rows from runtime tables.")
            print("   Reference tables (market data) will NOT be affected.\n")
            response = input("Continue? (yes/no): ").strip().lower()

            if response not in ["yes", "y"]:
                print("\n❌ Cleanup cancelled.\n")
                return

        # Perform cleanup
        print("\n🧹 Cleaning database...")
        deleted_counts = cleanup_database(conn, dry_run=False)

        # Show deleted counts
        print("\n📊 Deleted rows:")
        total_deleted = 0
        for table, count in deleted_counts.items():
            if isinstance(count, int):
                print(f"  {table:.<30} {count:>10,} rows")
                total_deleted += count
            else:
                print(f"  {table:.<30} {count}")

        # Show final state
        after_counts = get_table_counts(conn)
        print_table_counts(after_counts, "AFTER CLEANUP")

        print(f"✅ Successfully deleted {total_deleted:,} rows from runtime tables.")
        print("✅ Reference tables (market data) preserved.\n")

    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
