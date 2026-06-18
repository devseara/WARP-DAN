#!/usr/bin/env python3
"""
BOH License Generator
=====================
Generates a boh_features.ini for a specific customer.
Run: python gen_license.py --customer "ServerName" --features ItemColors,ExtendedNames
"""

import argparse
import os

ALL_FEATURES = {
    "ItemColors":    "Custom item name colors",
    "ExtendedNames": "Extended character names",
    "RuneVisual":    "Rune set rendering",
    "FpsOverlay":    "/fps slash command",
    "PingOverlay":   "/ping slash command",
}

def main():
    parser = argparse.ArgumentParser(description="Generate BOH license file")
    parser.add_argument("--customer", required=True, help="Customer/server name")
    parser.add_argument("--features", default="",
                        help="Comma-separated feature names to enable")
    parser.add_argument("--all", action="store_true",
                        help="Enable all features except HatTrace")
    parser.add_argument("--hat-trace", action="store_true",
                        help="Include HatTrace (dev only)")
    parser.add_argument("-o", "--output", default="boh_features.ini",
                        help="Output file path")
    args = parser.parse_args()

    if args.all:
        enabled = set(ALL_FEATURES.keys())
        if not args.hat_trace:
            enabled.discard("HatTrace")
    else:
        enabled = set()
        if args.features:
            for f in args.features.split(","):
                f = f.strip()
                if f in ALL_FEATURES:
                    enabled.add(f)
                else:
                    print(f"WARNING: Unknown feature '{f}' — skipping")

    lines = []
    lines.append(f"# BOH Feature License — {args.customer}")
    lines.append(f"# Generated: {__import__('datetime').datetime.now().isoformat()}")
    lines.append("# ==================================================")
    lines.append("")

    for name, desc in ALL_FEATURES.items():
        value = "1" if name in enabled else "0"
        lines.append(f"{name}={value}")

    lines.append("")

    output = "\n".join(lines)
    with open(args.output, "w") as f:
        f.write(output)

    print(f"License written to: {os.path.abspath(args.output)}")
    print(f"Customer: {args.customer}")
    print(f"Features enabled: {', '.join(sorted(enabled)) if enabled else '(none)'}")

if __name__ == "__main__":
    main()
