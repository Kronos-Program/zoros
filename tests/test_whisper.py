# See architecture: docs/zoros_architecture.md#component-overview
import whisper

def main():
    try:
        model = whisper.load_model("base")
        print("Model loaded successfully.")
    except Exception as e:
        print("FAILED to load model:")
        print(e)

if __name__ == "__main__":
    main()
