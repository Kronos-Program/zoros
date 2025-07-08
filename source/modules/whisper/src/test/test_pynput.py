# See architecture: docs/zoros_architecture.md#component-overview
import pynput
from pynput import keyboard, mouse

def on_press(key):
    try:
        print(f"Key {key.char} pressed")
    except AttributeError:
        print(f"Special key {key} pressed")

def on_release(key):
    if key == pynput.keyboard.Key.esc:
        # Stop listener
        return False

# Start listening
with pynput.keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()
