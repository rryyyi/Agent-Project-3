"""CLI entrypoints used in README, CI and local demonstrations."""

import argparse
import json
import logging
import sys
from importlib.resources import files
from pathlib import Path

from .evaluation import benchmark, evaluate, load_cases
from .factory import build_agent


def emit(value, output=None):
    text = json.dumps(value, ensure_ascii=False, indent=2)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    print(text)


def main(argv=None) -> int:
    # Windows terminals often default to a code page that cannot print JSON examples.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        prog="mtr-agent", description="MTR multilingual Agent portfolio"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    chat = commands.add_parser("chat", help="one grounded question, JSON output")
    chat.add_argument("message")
    chat.add_argument("--session-id")
    commands.add_parser("demo", help="offline multilingual, contextual and unsupported examples")
    evaluation = commands.add_parser("evaluate", help="run authored regression evaluation")
    evaluation.add_argument("--dataset")
    evaluation.add_argument("--output")
    bench = commands.add_parser("benchmark", help="warm-cache in-process offline timing")
    bench.add_argument("--iterations", type=int, default=200)
    bench.add_argument("--concurrency", type=int, default=8)
    bench.add_argument("--output")
    pdf = commands.add_parser("parse-pdf", help="extract unreviewed vector PDF evidence")
    pdf.add_argument("path")
    pdf.add_argument("--output")
    serve = commands.add_parser("serve", help="run HTTP service")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    commands.add_parser("mcp", help="run official MCP stdio transport")
    args = parser.parse_args(argv)
    try:
        if args.command == "chat":
            emit(build_agent().chat(args.message, args.session_id))
        elif args.command == "demo":
            agent = build_agent()
            messages = [
                "由Central去紅磡點搭？",
                "咁去旺角呢？",
                "Octopus payment 點用？",
                "Central去火星站",
                "Central去紅磡尾班車幾點",
                "quantum banana weather",
            ]
            emit(
                [
                    {"question": message, "response": agent.chat(message, "demo-session")}
                    for message in messages
                ]
            )
        elif args.command == "evaluate":
            if args.dataset:
                cases = load_cases(args.dataset)
            else:
                resource = files("mtr_agent").joinpath("data/eval.jsonl")
                cases = [
                    json.loads(line)
                    for line in resource.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            report = evaluate(cases, build_agent())
            emit(report, args.output)
            return int(bool(report["failures"]))
        elif args.command == "benchmark":
            emit(benchmark(args.iterations, args.concurrency), args.output)
        elif args.command == "parse-pdf":
            from .pdf import extract_pdf

            emit(extract_pdf(args.path), args.output)
        elif args.command == "serve":
            import uvicorn

            from .api import create_app

            uvicorn.run(
                create_app(build_agent()),
                host=args.host,
                port=args.port,
                log_level="info",
                access_log=False,
            )
        elif args.command == "mcp":
            from .mcp_server import create_mcp

            create_mcp(build_agent()).run(transport="stdio")
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    raise SystemExit(main())
