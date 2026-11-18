        "method": "One subprocess per real Tk case; real SQLite; button.invoke; message/file dialogs intercepted",
        "limits": "Records this machine only; not staff acceptance, physical input or full accessibility testing",
        "screenshots": screenshots,
        "cases": [],
        "issues": [],
    }
    target = out / "gui-test-results.json"
    atomic_json(target, payload)
    print(f"Running {len(names)} GUI tests, one fresh process per case.", flush=True)
    print(
        "Windows opening and closing are expected. Progress appears below.", flush=True
    )
    print("Evidence: " + str(out), flush=True)
    with (out / "gui-test-run.txt").open("w", encoding="utf-8", buffering=1) as log:
        log.write("Isolated GUI test run " + payload["run_at"] + "\n")
        with tempfile.TemporaryDirectory(prefix="sunrise-gui-results-") as directory:
            for index, case in enumerate(names, 1):
                print(
                    f"[{index}/{len(names)}] {case.rsplit('.', 1)[-1]} ...",
                    end=" ",
                    flush=True,
                )
                result_path = Path(directory) / f"{index}.json"
                command = [
                    sys.executable,
                    "-u",
                    str(Path(__file__).resolve()),
                    "--worker",
                    case,
                    "--result",
                    str(result_path),
                ]
                if screenshots:
                    command.append("--screenshots")
                try:
                    completed = subprocess.run(
                        command,
                        cwd=ROOT,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=timeout,
                    )
                    transcript = completed.stdout + completed.stderr
                    result = None
                    if result_path.exists():
                        try:
                            result = json.loads(result_path.read_text(encoding="utf-8"))
                        except (OSError, ValueError):
                            pass
                    status, detail = assess_case(case, completed.returncode, result)
                    if status != "PASS":
                        detail += "\n" + transcript
                except subprocess.TimeoutExpired:
                    status, detail = (
                        "ERROR",
                        f"Case exceeded the {timeout}-second timeout.",
                    )
                    transcript = detail
                except OSError as exc:
                    status, detail = "ERROR", "Unable to start test process: " + str(
                        exc
                    )
                    transcript = detail
                print(status, flush=True)
                log.write(f"\n[{index}/{len(names)}] {case}: {status}\n{transcript}\n")
                payload["tests_run"] += 1
                payload["cases"].append({"test": case, "result": status})
                if status == "PASS":
                    payload["passed"] += 1
                else:
                    payload["failures" if status == "FAIL" else "errors"] += 1
                    payload["issues"].append({"test": case, "detail": detail})
                atomic_json(target, payload)
        success = bool(names) and payload["passed"] == len(names)
        payload["status"] = "PASS" if success else "FAIL"
        atomic_json(target, payload)
        summary = (
            f"Ran {payload['tests_run']} of {len(names)} GUI tests: "
            f"{payload['passed']} passed, {payload['failures']} failures, "
            f"{payload['errors']} errors.\n"
            + (
                "OK - ALL GUI TESTS PASSED"
                if success
                else "FAILED - see evidence/gui-test-run.txt"
            )
        )
        log.write("\n" + summary + "\n")
        print("\n" + summary, flush=True)
    return 0 if success else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--screenshots", action="store_true", help="Optional PNGs; requires Pillow"
    )
    parser.add_argument(
        "--timeout", type=int, default=180, help="Seconds per case (default 180)"
    )
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    parser.add_argument("--result", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    if args.worker:
        allowed = set(
            case_names(unittest.defaultTestLoader.loadTestsFromModule(test_ui))
        )
        if args.worker not in allowed or args.result is None:
            parser.error("Invalid internal worker arguments")
        return worker(args.worker, args.result, args.screenshots)
    return controller(args.screenshots, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
