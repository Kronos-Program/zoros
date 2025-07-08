"""Simple check that whispercpp loads."""

# See architecture: docs/zoros_architecture.md#component-overview

def main() -> None:
    try:
        from whispercpp import Whisper  # type: ignore

        # Initialize with the base model
        _ = Whisper.from_pretrained("base")
        print("WhisperCPP OK")
    except Exception as exc:
        print("FAILED to load WhisperCPP:")
        print(exc)

if __name__ == "__main__":
    main()
