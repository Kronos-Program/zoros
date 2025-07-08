# See architecture: docs/zoros_architecture.md#component-overview
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Callable, Set

from utils import ConfigManager


class InputEvent(Enum):
    KEY_PRESS = auto()
    KEY_RELEASE = auto()
    MOUSE_PRESS = auto()
    MOUSE_RELEASE = auto()


class KeyCode(Enum):
    # Modifier keys
    CTRL_LEFT = auto()
    CTRL_RIGHT = auto()
    SHIFT_LEFT = auto()
    SHIFT_RIGHT = auto()
    ALT_LEFT = auto()
    ALT_RIGHT = auto()
    META_LEFT = auto()
    META_RIGHT = auto()

    # Function keys
    F1 = auto()
    F2 = auto()
    F3 = auto()
    F4 = auto()
    F5 = auto()
    F6 = auto()
    F7 = auto()
    F8 = auto()
    F9 = auto()
    F10 = auto()
    F11 = auto()
    F12 = auto()
    F13 = auto()
    F14 = auto()
    F15 = auto()
    F16 = auto()
    F17 = auto()
    F18 = auto()
    F19 = auto()
    F20 = auto()
    F21 = auto()
    F22 = auto()
    F23 = auto()
    F24 = auto()

    # Number keys
    ONE = auto()
    TWO = auto()
    THREE = auto()
    FOUR = auto()
    FIVE = auto()
    SIX = auto()
    SEVEN = auto()
    EIGHT = auto()
    NINE = auto()
    ZERO = auto()

    # Letter keys
    A = auto()
    B = auto()
    C = auto()
    D = auto()
    E = auto()
    F = auto()
    G = auto()
    H = auto()
    I = auto()
    J = auto()
    K = auto()
    L = auto()
    M = auto()
    N = auto()
    O = auto()
    P = auto()
    Q = auto()
    R = auto()
    S = auto()
    T = auto()
    U = auto()
    V = auto()
    W = auto()
    X = auto()
    Y = auto()
    Z = auto()

    # Special keys
    SPACE = auto()
    ENTER = auto()
    TAB = auto()
    BACKSPACE = auto()
    ESC = auto()
    INSERT = auto()
    DELETE = auto()
    HOME = auto()
    END = auto()
    PAGE_UP = auto()
    PAGE_DOWN = auto()
    CAPS_LOCK = auto()
    NUM_LOCK = auto()
    SCROLL_LOCK = auto()
    PAUSE = auto()
    PRINT_SCREEN = auto()

    # Arrow keys
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()

    # Numpad keys
    NUMPAD_0 = auto()
    NUMPAD_1 = auto()
    NUMPAD_2 = auto()
    NUMPAD_3 = auto()
    NUMPAD_4 = auto()
    NUMPAD_5 = auto()
    NUMPAD_6 = auto()
    NUMPAD_7 = auto()
    NUMPAD_8 = auto()
    NUMPAD_9 = auto()
    NUMPAD_ADD = auto()
    NUMPAD_SUBTRACT = auto()
    NUMPAD_MULTIPLY = auto()
    NUMPAD_DIVIDE = auto()
    NUMPAD_DECIMAL = auto()
    NUMPAD_ENTER = auto()

    # Additional special characters
    MINUS = auto()
    EQUALS = auto()
    LEFT_BRACKET = auto()
    RIGHT_BRACKET = auto()
    SEMICOLON = auto()
    QUOTE = auto()
    BACKQUOTE = auto()
    BACKSLASH = auto()
    COMMA = auto()
    PERIOD = auto()
    SLASH = auto()

    # Media keys
    MUTE = auto()
    VOLUME_DOWN = auto()
    VOLUME_UP = auto()
    PLAY_PAUSE = auto()
    NEXT_TRACK = auto()
    PREV_TRACK = auto()

    # Additional Media and Special Function Keys
    MEDIA_PLAY = auto()
    MEDIA_PAUSE = auto()
    MEDIA_PLAY_PAUSE = auto()
    MEDIA_STOP = auto()
    MEDIA_PREVIOUS = auto()
    MEDIA_NEXT = auto()
    MEDIA_REWIND = auto()
    MEDIA_FAST_FORWARD = auto()
    AUDIO_MUTE = auto()
    AUDIO_VOLUME_UP = auto()
    AUDIO_VOLUME_DOWN = auto()
    MEDIA_SELECT = auto()
    WWW = auto()
    MAIL = auto()
    CALCULATOR = auto()
    COMPUTER = auto()
    APP_SEARCH = auto()
    APP_HOME = auto()
    APP_BACK = auto()
    APP_FORWARD = auto()
    APP_STOP = auto()
    APP_REFRESH = auto()
    APP_BOOKMARKS = auto()
    BRIGHTNESS_DOWN = auto()
    BRIGHTNESS_UP = auto()
    DISPLAY_SWITCH = auto()
    KEYBOARD_ILLUMINATION_TOGGLE = auto()
    KEYBOARD_ILLUMINATION_DOWN = auto()
    KEYBOARD_ILLUMINATION_UP = auto()
    EJECT = auto()
    SLEEP = auto()
    WAKE = auto()
    EMOJI = auto()
    MENU = auto()
    CLEAR = auto()
    LOCK = auto()

    # Mouse Buttons
    MOUSE_LEFT = auto()
    MOUSE_RIGHT = auto()
    MOUSE_MIDDLE = auto()
    MOUSE_BACK = auto()
    MOUSE_FORWARD = auto()
    MOUSE_SIDE1 = auto()
    MOUSE_SIDE2 = auto()
    MOUSE_SIDE3 = auto()


class InputBackend(ABC):
    """
    Abstract base class for input backends.
    This class defines the interface that all input backends must implement.
    """

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """
        Check if this input backend is available on the current system.

        Returns:
            bool: True if the backend is available, False otherwise.
        """
        pass

    @abstractmethod
    def start(self):
        """
        Start the input backend.
        This method should initialize any necessary resources and begin listening for input events.
        """
        pass

    @abstractmethod
    def stop(self):
        """
        Stop the input backend.
        This method should clean up any resources and stop listening for input events.
        """
        pass

    @abstractmethod
    def on_input_event(self, event: tuple[KeyCode, InputEvent]):
        """
        Handle an input event.
        This method is called when an input event is detected.

        :param event (Tuple[KeyCode, InputEvent]): A tuple containing the key code and the type of event.
        """
        pass


class KeyChord:
    """
    Represents a combination of keys that need to be pressed simultaneously.
    """

    def __init__(self, keys: Set[KeyCode | frozenset[KeyCode]]):
        """Initialize the KeyChord."""
        self.keys = keys
        self.pressed_keys: Set[KeyCode] = set()
        # Create an ordered list of keys for exact sequence matching
        self.key_sequence = []
        # Track when all required keys are pressed
        self.all_keys_pressed = False
        # Store the non-modifier key that should be pressed last (if any)
        self.target_key = None

        # Find the non-modifier key (like A, Z) in the required keys
        for key in keys:
            if not isinstance(key, frozenset):
                if key not in (KeyCode.CTRL_LEFT, KeyCode.CTRL_RIGHT,
                               KeyCode.SHIFT_LEFT, KeyCode.SHIFT_RIGHT,
                               KeyCode.ALT_LEFT, KeyCode.ALT_RIGHT,
                               KeyCode.META_LEFT, KeyCode.META_RIGHT):
                    self.target_key = key
                    break

    def update(self, key: KeyCode, event_type: InputEvent) -> bool:
        """Update the state of pressed keys and check if the chord is active."""
        if event_type == InputEvent.KEY_PRESS:
            # Add the key to pressed keys
            self.pressed_keys.add(key)

            # Only track key sequence if we haven't triggered yet
            if not self.all_keys_pressed and key not in self.key_sequence:
                self.key_sequence.append(key)
        elif event_type == InputEvent.KEY_RELEASE:
            # If the key is released, remove it from pressed keys
            self.pressed_keys.discard(key)

            # If releasing one of our required keys, reset all tracking
            if any(self._key_matches(key, required_key) for required_key in self.keys):
                self.all_keys_pressed = False
                self.key_sequence = []
                # print("Reset key sequence tracking")

        # Check if the combination is active
        is_now_active = self.is_active()
        return is_now_active

    def _key_matches(self, pressed_key: KeyCode, required_key) -> bool:
        """Check if a pressed key matches a required key (which might be a frozenset)."""
        if isinstance(required_key, frozenset):
            return pressed_key in required_key
        return pressed_key == required_key

    def is_active(self) -> bool:
        """
        Check if all keys in the chord are currently pressed in the correct sequence.
        For ctrl+shift+A, this ensures A is pressed only after ctrl and shift are already down.
        """
        # First check if all required keys are pressed
        all_required_are_pressed = True
        for req_key in self.keys:
            if isinstance(req_key, frozenset):
                if not any(k_in_set in self.pressed_keys for k_in_set in req_key):
                    all_required_are_pressed = False
                    break
            elif req_key not in self.pressed_keys:
                all_required_are_pressed = False
                break
        
        # print(f"DEBUG: KeyChord.is_active: All required keys physically pressed? {all_required_are_pressed}")

        # If this is the first time all keys are pressed, check the sequence
        if all_required_are_pressed and not self.all_keys_pressed:
            # Ensure the target key (like A) is pressed last 
            # This prevents triggering from just pressing ctrl+shift
            if self.target_key:
                if self.key_sequence and self.key_sequence[-1] == self.target_key:
                    self.all_keys_pressed = True # Latch: Chord is now active
                    return True
                else:
                    return False
            else: # No specific target key, any order is fine as long as all are pressed
                self.all_keys_pressed = True # Latch: Chord is now active
                return True
        
        # If not all required keys are pressed, the chord is definitely not active. Reset latch.
        if not all_required_are_pressed:
            self.all_keys_pressed = False
            return False

        # If all_required_are_pressed is true AND self.all_keys_pressed is true, it means the chord remains active.
        return self.all_keys_pressed


class KeyListener:
    """
    Manages input backends and listens for specific key combinations.
    """

    def __init__(self):
        """Initialize the KeyListener with backends and activation keys."""
        self.backends = []
        self.active_backend = None
        self.key_chord = None
        self.callbacks = {
            "on_activate": [],
            "on_deactivate": []
        }
        self.load_activation_keys()
        self.initialize_backends()
        self.select_backend_from_config()

    def initialize_backends(self):
        """Initialize available input backends."""
        backend_classes = [PynputBackend]  # Only use PynputBackend on Windows
        self.backends = [backend_class() for backend_class in backend_classes if backend_class.is_available()]
        print(
            f"Initialized {len(self.backends)} backend(s): {[b.__class__.__name__ for b in self.backends]}"
        )

    def select_backend_from_config(self):
        """Select the active backend based on configuration."""
        preferred_backend = ConfigManager.get_config_value('recording_options', 'input_backend')
        print(f"Preferred backend from config: {preferred_backend}")

        if preferred_backend == 'auto':
            self.select_active_backend()
        else:
            backend_map = {
                'pynput': PynputBackend
            }

            if preferred_backend in backend_map:
                try:
                    self.set_active_backend(backend_map[preferred_backend])
                except ValueError:
                    print(
                        f"Preferred backend '{preferred_backend}' is not available. Falling back to auto selection."
                    )
                    self.select_active_backend()
            else:
                print(
                    f"Unknown backend '{preferred_backend}'. Falling back to auto selection."
                )
                self.select_active_backend()

    def select_active_backend(self):
        """Select the first available backend as active."""
        if not self.backends:
            raise RuntimeError("No supported input backend found")
        self.active_backend = self.backends[0]
        self.active_backend.on_input_event = self.on_input_event

    def set_active_backend(self, backend_class):
        """Set a specific backend as active."""
        new_backend = next((b for b in self.backends if isinstance(b, backend_class)), None)
        if new_backend:
            if self.active_backend:
                self.stop()
            self.active_backend = new_backend
            self.active_backend.on_input_event = self.on_input_event
            self.start()
        else:
            raise ValueError(f"Backend {backend_class.__name__} is not available")

    def update_backend(self):
        """Update the active backend based on current configuration."""
        self.select_backend_from_config()

    def start(self):
        """Start the active backend."""
        if self.active_backend:
            self.active_backend.start()
        else:
            raise RuntimeError("No active backend selected")

    def stop(self):
        """Stop the active backend."""
        if self.active_backend:
            self.active_backend.stop()

    def load_activation_keys(self):
        """Load activation keys from configuration."""
        key_combination = ConfigManager.get_config_value('recording_options', 'activation_key')
        keys = self.parse_key_combination(key_combination)
        self.set_activation_keys(keys)

    def parse_key_combination(self, combination_string: str) -> Set[KeyCode | frozenset[KeyCode]]:
        """Parse a string representation of key combination into a set of KeyCodes."""
        keys = set()
        key_map = {
            'CTRL': frozenset({KeyCode.CTRL_LEFT, KeyCode.CTRL_RIGHT}),
            'SHIFT': frozenset({KeyCode.SHIFT_LEFT, KeyCode.SHIFT_RIGHT}),
            'ALT': frozenset({KeyCode.ALT_LEFT, KeyCode.ALT_RIGHT}),
            'META': frozenset({KeyCode.META_LEFT, KeyCode.META_RIGHT}),
        }

        for key in combination_string.upper().split('+'):
            key = key.strip()
            if key in key_map:
                keys.add(key_map[key])
            else:
                try:
                    keycode = KeyCode[key]
                    keys.add(keycode)
                except KeyError:
                    print(f"Unknown key: {key}")
        return keys

    def set_activation_keys(self, keys: Set[KeyCode]):
        """Set the activation keys for the KeyChord."""
        self.key_chord = KeyChord(keys)

    def on_input_event(self, event):
        """Handle input events and trigger callbacks if the key chord becomes active or inactive."""
        if not self.key_chord or not self.active_backend: # Ensure key_chord and active_backend are initialized
            return

        key, event_type = event
        # Mask mouse events: Only process keyboard events
        if key in [KeyCode.MOUSE_LEFT, KeyCode.MOUSE_RIGHT, KeyCode.MOUSE_MIDDLE, KeyCode.MOUSE_BACK, KeyCode.MOUSE_FORWARD, KeyCode.MOUSE_SIDE1, KeyCode.MOUSE_SIDE2, KeyCode.MOUSE_SIDE3]:
            return

        was_active = self.key_chord.is_active() # Check state BEFORE update
        
        is_active = self.key_chord.update(key, event_type) # Update state and get new state

        if not was_active and is_active:
            self._trigger_callbacks("on_activate")
        elif was_active and not is_active:
            self._trigger_callbacks("on_deactivate")

    def add_callback(self, event: str, callback: Callable):
        """Add a callback function for a specific event."""
        if event in self.callbacks:
            self.callbacks[event].append(callback)

    def _trigger_callbacks(self, event: str):
        """Trigger all callbacks associated with a specific event."""
        for callback in self.callbacks.get(event, []):
            callback()

    def update_activation_keys(self):
        """Update activation keys from the current configuration."""
        self.load_activation_keys()

class PynputBackend(InputBackend):
    """
    Input backend implementation using the pynput library.
    """

    @classmethod
    def is_available(cls) -> bool:
        """Check if pynput library is available."""
        try:
            import pynput
            return True
        except ImportError:
            return False

    def __init__(self):
        """Initialize PynputBackend."""
        self.keyboard_listener = None
        self.mouse_listener = None
        self.keyboard = None
        self.mouse = None
        self.key_map = None
        # Debug flag to print additional key information
        self.debug_mode = ConfigManager.is_debug_enabled()

    def start(self):
        """Start listening for keyboard and mouse events."""
        if self.keyboard is None or self.mouse is None:
            from pynput import keyboard, mouse
            self.keyboard = keyboard
            self.mouse = mouse
            self.key_map = self._create_key_map()
        
        # print("Starting keyboard listener...")
        self.keyboard_listener = self.keyboard.Listener(
            on_press=self._on_keyboard_press,
            on_release=self._on_keyboard_release
        )
        self.mouse_listener = self.mouse.Listener(
            on_click=self._on_mouse_click
        )
        self.keyboard_listener.start()
        self.mouse_listener.start()
        # print("Keyboard listener started successfully")

    def stop(self):
        """Stop listening for keyboard and mouse events."""
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None

    def _translate_key_event(self, native_event) -> tuple[KeyCode, InputEvent]:
        """Translate a pynput event to our internal event representation."""
        pynput_key, is_press = native_event
        
        # Special handling for letter keys (pynput.keyboard.KeyCode objects)
        if hasattr(pynput_key, 'char') and pynput_key.char:
            # For character keys, we look them up by the exact character
            char = pynput_key.char.lower()
            if char == 'a':
                event_type = InputEvent.KEY_PRESS if is_press else InputEvent.KEY_RELEASE
                return KeyCode.A, event_type
            elif 'a' <= char <= 'z':
                # Map other letters directly
                key_enum_name = char.upper()
                key_code = getattr(KeyCode, key_enum_name)
                event_type = InputEvent.KEY_PRESS if is_press else InputEvent.KEY_RELEASE
                return key_code, event_type
        
        # Handle specific virtual key codes for common letters
        if hasattr(pynput_key, 'vk'):
            # Windows virtual key code for 'A' is typically 65
            if pynput_key.vk == 65:  # VK code for 'A'
                event_type = InputEvent.KEY_PRESS if is_press else InputEvent.KEY_RELEASE
                return KeyCode.A, event_type
        
        # Try to look up by direct reference
        key_code = self.key_map.get(pynput_key)
        
        # For Windows: if we have no mapping but we have a virtual key code,
        # try to find it by vk code
        if key_code is None and hasattr(pynput_key, 'vk'):
            vk_to_keycode = {
                65: KeyCode.A, 66: KeyCode.B, 67: KeyCode.C, 68: KeyCode.D,
                69: KeyCode.E, 70: KeyCode.F, 71: KeyCode.G, 72: KeyCode.H,
                73: KeyCode.I, 74: KeyCode.J, 75: KeyCode.K, 76: KeyCode.L,
                77: KeyCode.M, 78: KeyCode.N, 79: KeyCode.O, 80: KeyCode.P,
                81: KeyCode.Q, 82: KeyCode.R, 83: KeyCode.S, 84: KeyCode.T,
                85: KeyCode.U, 86: KeyCode.V, 87: KeyCode.W, 88: KeyCode.X,
                89: KeyCode.Y, 90: KeyCode.Z
            }
            key_code = vk_to_keycode.get(pynput_key.vk)
            if key_code:
                pass
        
        # Fall back to standard key_map lookup if the special cases didn't work
        if key_code is None:
            # Check if any of our mappings have the same vk
            for k, v in self.key_map.items():
                if hasattr(k, 'vk') and hasattr(pynput_key, 'vk') and k.vk == pynput_key.vk:
                    key_code = v
                    break
        
        # Still no mapping? Rely on string representation as a fallback
        if key_code is None and str(pynput_key) == "'a'":
            key_code = KeyCode.A
        
        # Final fallback
        if key_code is None:
            return pynput_key, InputEvent.KEY_PRESS if is_press else InputEvent.KEY_RELEASE
        
        event_type = InputEvent.KEY_PRESS if is_press else InputEvent.KEY_RELEASE
        return key_code, event_type

    def _on_keyboard_press(self, key):
        """Handle keyboard press events."""
        try:
            translated_event = self._translate_key_event((key, True))
            self.on_input_event(translated_event)
        except Exception as e:
            print(f"Error handling keyboard press: {e}")

    def _on_keyboard_release(self, key):
        """Handle keyboard release events."""
        try:
            translated_event = self._translate_key_event((key, False))
            self.on_input_event(translated_event)
        except Exception as e:
            print(f"Error handling keyboard release: {e}")

    def _on_mouse_click(self, x, y, button, pressed):
        """Handle mouse click events."""
        translated_event = self._translate_key_event((button, pressed))
        self.on_input_event(translated_event)

    def _create_key_map(self):
        """Create a mapping from pynput keys to our internal KeyCode enum."""
        key_map = {
            # Modifier keys
            self.keyboard.Key.ctrl_l: KeyCode.CTRL_LEFT,
            self.keyboard.Key.ctrl_r: KeyCode.CTRL_RIGHT,
            self.keyboard.Key.shift_l: KeyCode.SHIFT_LEFT,
            self.keyboard.Key.shift_r: KeyCode.SHIFT_RIGHT,
            self.keyboard.Key.alt_l: KeyCode.ALT_LEFT,
            self.keyboard.Key.alt_r: KeyCode.ALT_RIGHT,
            self.keyboard.Key.cmd_l: KeyCode.META_LEFT,
            self.keyboard.Key.cmd_r: KeyCode.META_RIGHT,

            # Function keys
            self.keyboard.Key.f1: KeyCode.F1,
            self.keyboard.Key.f2: KeyCode.F2,
            self.keyboard.Key.f3: KeyCode.F3,
            self.keyboard.Key.f4: KeyCode.F4,
            self.keyboard.Key.f5: KeyCode.F5,
            self.keyboard.Key.f6: KeyCode.F6,
            self.keyboard.Key.f7: KeyCode.F7,
            self.keyboard.Key.f8: KeyCode.F8,
            self.keyboard.Key.f9: KeyCode.F9,
            self.keyboard.Key.f10: KeyCode.F10,
            self.keyboard.Key.f11: KeyCode.F11,
            self.keyboard.Key.f12: KeyCode.F12,
            self.keyboard.Key.f13: KeyCode.F13,
            self.keyboard.Key.f14: KeyCode.F14,
            self.keyboard.Key.f15: KeyCode.F15,
            self.keyboard.Key.f16: KeyCode.F16,
            self.keyboard.Key.f17: KeyCode.F17,
            self.keyboard.Key.f18: KeyCode.F18,
            self.keyboard.Key.f19: KeyCode.F19,
            self.keyboard.Key.f20: KeyCode.F20,

            # Special keys
            self.keyboard.Key.space: KeyCode.SPACE,
            self.keyboard.Key.enter: KeyCode.ENTER,
            self.keyboard.Key.tab: KeyCode.TAB,
            self.keyboard.Key.backspace: KeyCode.BACKSPACE,
            self.keyboard.Key.esc: KeyCode.ESC,
            self.keyboard.Key.delete: KeyCode.DELETE,
            self.keyboard.Key.home: KeyCode.HOME,
            self.keyboard.Key.end: KeyCode.END,
            self.keyboard.Key.page_up: KeyCode.PAGE_UP,
            self.keyboard.Key.page_down: KeyCode.PAGE_DOWN,
            self.keyboard.Key.caps_lock: KeyCode.CAPS_LOCK,
            # self.keyboard.Key.num_lock: KeyCode.NUM_LOCK,
            # self.keyboard.Key.scroll_lock: KeyCode.SCROLL_LOCK,
            # self.keyboard.Key.pause: KeyCode.PAUSE,
            # self.keyboard.Key.print_screen: KeyCode.PRINT_SCREEN,

            # Arrow keys
            self.keyboard.Key.up: KeyCode.UP,
            self.keyboard.Key.down: KeyCode.DOWN,
            self.keyboard.Key.left: KeyCode.LEFT,
            self.keyboard.Key.right: KeyCode.RIGHT,
        }

        try:
            key_map[self.keyboard.Key.insert] = KeyCode.INSERT
        except AttributeError:
            print("Warning: pynput.keyboard.Key.insert is not available on this platform.")
        
        try:
            key_map[self.keyboard.Key.num_lock] = KeyCode.NUM_LOCK
        except AttributeError:
            print("Warning: pynput.keyboard.Key.num_lock is not available on this platform.")

        try:
            key_map[self.keyboard.Key.scroll_lock] = KeyCode.SCROLL_LOCK
        except AttributeError:
            print("Warning: pynput.keyboard.Key.scroll_lock is not available on this platform.")

        try:
            key_map[self.keyboard.Key.pause] = KeyCode.PAUSE
        except AttributeError:
            print("Warning: pynput.keyboard.Key.pause is not available on this platform.")

        try:
            key_map[self.keyboard.Key.print_screen] = KeyCode.PRINT_SCREEN
        except AttributeError:
            print("Warning: pynput.keyboard.Key.print_screen is not available on this platform.")
        
        # Add letter keys (both lowercase and uppercase)
        letter_mapping = {
            'a': KeyCode.A, 'b': KeyCode.B, 'c': KeyCode.C, 'd': KeyCode.D,
            'e': KeyCode.E, 'f': KeyCode.F, 'g': KeyCode.G, 'h': KeyCode.H,
            'i': KeyCode.I, 'j': KeyCode.J, 'k': KeyCode.K, 'l': KeyCode.L,
            'm': KeyCode.M, 'n': KeyCode.N, 'o': KeyCode.O, 'p': KeyCode.P,
            'q': KeyCode.Q, 'r': KeyCode.R, 's': KeyCode.S, 't': KeyCode.T,
            'u': KeyCode.U, 'v': KeyCode.V, 'w': KeyCode.W, 'x': KeyCode.X,
            'y': KeyCode.Y, 'z': KeyCode.Z
        }
        
        for char, code in letter_mapping.items():
            key_map[self.keyboard.KeyCode.from_char(char)] = code
            # Also map uppercase
            key_map[self.keyboard.KeyCode.from_char(char.upper())] = code
        
        # Add number keys
        for i in range(10):
            char = str(i)
            key_map[self.keyboard.KeyCode.from_char(char)] = getattr(KeyCode, 'ZERO' if i == 0 else 
                                                                       ['ONE', 'TWO', 'THREE', 'FOUR', 'FIVE',
                                                                       'SIX', 'SEVEN', 'EIGHT', 'NINE'][i-1])
        
        # Add special character keys
        special_chars = {
            '-': KeyCode.MINUS, '=': KeyCode.EQUALS, '[': KeyCode.LEFT_BRACKET,
            ']': KeyCode.RIGHT_BRACKET, ';': KeyCode.SEMICOLON, "'": KeyCode.QUOTE,
            '`': KeyCode.BACKQUOTE, '\\': KeyCode.BACKSLASH, ',': KeyCode.COMMA,
            '.': KeyCode.PERIOD, '/': KeyCode.SLASH
        }
        
        for char, code in special_chars.items():
            key_map[self.keyboard.KeyCode.from_char(char)] = code
        
        # Add numpad keys - Windows specific virtual key codes
        numpad_vks = {
            96: KeyCode.NUMPAD_0, 97: KeyCode.NUMPAD_1, 98: KeyCode.NUMPAD_2,
            99: KeyCode.NUMPAD_3, 100: KeyCode.NUMPAD_4, 101: KeyCode.NUMPAD_5,
            102: KeyCode.NUMPAD_6, 103: KeyCode.NUMPAD_7, 104: KeyCode.NUMPAD_8,
            105: KeyCode.NUMPAD_9, 106: KeyCode.NUMPAD_MULTIPLY, 107: KeyCode.NUMPAD_ADD,
            109: KeyCode.NUMPAD_SUBTRACT, 110: KeyCode.NUMPAD_DECIMAL, 111: KeyCode.NUMPAD_DIVIDE
        }
        
        for vk, code in numpad_vks.items():
            key_map[self.keyboard.KeyCode.from_vk(vk)] = code
        
        # Add media keys if available (platform dependent)
        if hasattr(self.keyboard.Key, 'media_volume_mute'):
            media_keys = {
                self.keyboard.Key.media_volume_mute: KeyCode.AUDIO_MUTE,
                self.keyboard.Key.media_volume_down: KeyCode.AUDIO_VOLUME_DOWN,
                self.keyboard.Key.media_volume_up: KeyCode.AUDIO_VOLUME_UP,
                getattr(self.keyboard.Key, 'media_play_pause', None): KeyCode.MEDIA_PLAY_PAUSE
            }
            
            for k, v in media_keys.items():
                if k is not None:
                    key_map[k] = v
        
        # Mouse buttons
        mouse_buttons = {
            self.mouse.Button.left: KeyCode.MOUSE_LEFT,
            self.mouse.Button.right: KeyCode.MOUSE_RIGHT,
            self.mouse.Button.middle: KeyCode.MOUSE_MIDDLE
        }
        key_map.update(mouse_buttons)
        
        print("Key mapping initialized with" + " " + str(len(key_map)) + " keys")
        return key_map

    def on_input_event(self, event):
        """
        Callback method to be set by the KeyListener.
        This method is called for each processed input event.
        """
        pass

if __name__ == "__main__":
    import time
    import logging
    from zoros.logger import get_logger

    # Configure logging for better output
    logging.basicConfig(level=logging.INFO)
    logger = get_logger(__name__)

    def on_activation():
        logger.info("Key chord ACTIVATED!")

    def on_deactivation():
        logger.info("Key chord DEACTIVATED!")

    logger.info("Initializing KeyListener for testing...")
    logger.info("Press the configured activation key (e.g., CTRL+SHIFT+A) to test.")
    logger.info("Press Ctrl+C to exit.")

    try:
        ConfigManager.initialize()
        ConfigManager.load_config() 
        if not ConfigManager.get_config_value('recording_options', 'activation_key'):
            logger.warning("Activation key not found in config. Setting default 'CTRL+SHIFT+A' for testing.")
            if 'recording_options' not in ConfigManager.config_data:
                ConfigManager.config_data['recording_options'] = {}
            ConfigManager.config_data['recording_options']['activation_key'] = 'CTRL+SHIFT+A'
            ConfigManager.config_data['recording_options']['input_backend'] = 'auto'

    except Exception as e:
        logger.error(f"Error during initial ConfigManager setup: {e}. Using fallback defaults.")
        ConfigManager.config_data = {
            'recording_options': {
                'activation_key': 'CTRL+SHIFT+A',
                'input_backend': 'auto'
            }
        }

    key_listener = KeyListener()
    key_listener.add_callback("on_activate", on_activation)
    key_listener.add_callback("on_deactivate", on_deactivation)

    try:
        key_listener.start()
        logger.info("KeyListener started. Listening for key combinations...")
        while True:
            time.sleep(0.1)  # Keep the main thread alive
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Stopping KeyListener...")
    except Exception as e:
        logger.error(f"An error occurred during KeyListener operation: {e}", exc_info=True)
    finally:
        logger.info("Stopping KeyListener...")
        key_listener.stop()
        logger.info("KeyListener stopped.")
