from pathlib import Path


TARGET = Path("planning/unreal_plan_executor.py")
OLD = '            if expected_start_frame is not None and expected_end_frame is not None: evidence=verify_sequencer_playback_range(evidence,expected_start_frame,expected_end_frame)'
NEW = '            if operation.name == "verify_sequencer_playback_range" and expected_start_frame is not None and expected_end_frame is not None: evidence=verify_sequencer_playback_range(evidence,expected_start_frame,expected_end_frame)'


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    if NEW in text:
        print("Render verification fix already applied.")
        return
    if text.count(OLD) != 1:
        raise SystemExit(
            f"Expected exactly one render/sequencer verification line, found {text.count(OLD)}."
        )
    TARGET.write_text(text.replace(OLD, NEW), encoding="utf-8")
    print(f"Updated {TARGET}")


if __name__ == "__main__":
    main()
