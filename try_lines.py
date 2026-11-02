"""Interactive and Batch Normalization Runner for text_frontend.

Usage Examples:
    # 1. Run sample sentences from my_sentences.txt
    python try_lines.py

    # 2. Run one sentence directly from command line
    python try_lines.py "Dr. Smith bought 3 items for $12.50 at 2:30pm."

    # 3. Interactive prompt (type any sentence)
    python try_lines.py -i

    # 4. Use different locale (e.g. en-IN or en-GB)
    python try_lines.py --locale en-IN "Price is Rs. 1,50,000/-"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from text_frontend import normalize


def print_result(raw_text: str, locale: str = "en-US", show_details: bool = False):
    """Normalizes input text and prints a formatted before/after view."""
    res = normalize(raw_text, locale=locale)
    print("=" * 70)
    print(f"INPUT     : {raw_text}")
    print(f"NORMALIZED: {res.normalized_text}")
    print(f"STATUS    : {res.status}")
    if res.warnings:
        warn_str = ", ".join(f"{w.code} ({w.severity})" for w in res.warnings)
        print(f"WARNINGS  : {warn_str}")
    
    if show_details and res.transformations:
        print("\nTRANSFORMATIONS:")
        for t in res.transformations:
            orig = raw_text[t.original_span[0] : t.original_span[1]]
            norm = res.normalized_text[t.output_span[0] : t.output_span[1]]
            print(f"  [{t.category:<12}] '{orig}' -> '{norm}' (original chars: {t.original_span})")
    print("=" * 70)


def run_interactive(locale: str = "en-US", show_details: bool = True):
    """Runs an interactive loop prompting the user for text."""
    print("\n" + "=" * 70)
    print(f" Interactive Text Normalizer ({locale})")
    print(" Type any sentence and press Enter to see normalized output.")
    print(" Type 'exit' or 'q' to quit.")
    print("=" * 70 + "\n")

    while True:
        try:
            user_input = input("Enter text > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break
            print_result(user_input, locale=locale, show_details=show_details)
            print()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break


def run_file(file_path: Path, locale: str = "en-US"):
    """Reads lines from a file and normalizes each non-empty line."""
    if not file_path.exists():
        print(f"Error: File '{file_path}' not found.")
        return

    print(f"\nProcessing sentences from: {file_path} (locale: {locale})\n")
    with open(file_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not line.strip() or line.strip().startswith("#"):
                continue
            print_result(line, locale=locale)
            print()


def main():
    parser = argparse.ArgumentParser(
        description="Text Normalization CLI for Text-to-Speech Frontend"
    )
    parser.add_argument(
        "text",
        nargs="*",
        help="Optional sentence to normalize directly from command line",
    )
    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Launch interactive prompt to enter sentences interactively",
    )
    parser.add_argument(
        "-l",
        "--locale",
        default="en-US",
        choices=["en-US", "en-GB", "en-IN", "en-CA", "en-AU"],
        help="Locale code (default: en-US; use en-IN for Indian English)",
    )
    parser.add_argument(
        "-f",
        "--file",
        default="my_sentences.txt",
        help="Input text file containing sentences (default: my_sentences.txt)",
    )
    parser.add_argument(
        "-d",
        "--details",
        action="store_true",
        help="Show detailed transformation span coordinates",
    )

    args = parser.parse_args()

    # Case 1: Direct text passed as CLI arguments
    if args.text:
        raw_text = " ".join(args.text)
        print_result(raw_text, locale=args.locale, show_details=args.details or True)
        return

    # Case 2: Interactive mode requested
    if args.interactive:
        run_interactive(locale=args.locale, show_details=True)
        return

    # Case 3: Default batch run from file
    file_path = Path(args.file)
    if file_path.exists():
        run_file(file_path, locale=args.locale)
        print("Tip: Run 'python try_lines.py -i' for interactive mode,")
        print("     or pass text directly: python try_lines.py \"Your sentence here\"\n")
    else:
        # Fall back to interactive mode if file doesn't exist
        run_interactive(locale=args.locale, show_details=True)


if __name__ == "__main__":
    main()
