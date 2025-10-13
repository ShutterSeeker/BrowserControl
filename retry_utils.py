# retry_utils.py
# Retry decorator and utilities for eliminating time.sleep() based polling

import time
from functools import wraps
from typing import Callable, Any, Tuple, Type, Optional


def retry_with_backoff(
    max_attempts: int = 5,
    initial_delay: float = 0.1,
    backoff_factor: float = 1.5,
    max_delay: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None
):
    """
    Decorator that retries a function with exponential backoff.
    
    This replaces polling loops with time.sleep() with intelligent retry logic.
    
    Args:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay in seconds (default: 0.1s)
        backoff_factor: Multiplier for delay after each retry (default: 1.5x)
        max_delay: Maximum delay between retries (default: 2.0s)
        exceptions: Tuple of exception types to catch and retry
        on_retry: Optional callback function(attempt, exception) called on each retry
    
    Example:
        @retry_with_backoff(max_attempts=10, initial_delay=0.1)
        def find_window(title):
            windows = gw.getWindowsWithTitle(title)
            if not windows:
                raise WindowNotFoundError(f"Window '{title}' not found")
            return windows[0]
    
    Performance:
        OLD: for _ in range(50): check(); time.sleep(0.1)  # Always 5 seconds worst case
        NEW: @retry_with_backoff - Succeeds immediately when ready, intelligent backoff
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        # Final attempt failed, raise the exception
                        raise
                    
                    # Call retry callback if provided
                    if on_retry:
                        on_retry(attempt, e)
                    
                    # Wait before next attempt with exponential backoff
                    time.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator


def poll_until_true(
    condition: Callable[[], bool],
    timeout: float = 5.0,
    interval: float = 0.1,
    error_message: str = "Condition not met within timeout"
) -> bool:
    """
    Poll a condition until it returns True or timeout is reached.
    
    Better alternative to: while not condition(): time.sleep(0.1)
    
    Args:
        condition: Callable that returns bool
        timeout: Maximum time to wait in seconds
        interval: Time between checks in seconds
        error_message: Error message if timeout is reached
    
    Returns:
        True if condition was met, raises TimeoutError if not
    
    Example:
        # OLD:
        for _ in range(50):
            if window_exists():
                break
            time.sleep(0.1)
        
        # NEW:
        poll_until_true(window_exists, timeout=5.0)
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if condition():
            return True
        time.sleep(interval)
    
    raise TimeoutError(f"{error_message} (timeout: {timeout}s)")


def wait_for_window(
    get_windows_func: Callable[[], list],
    timeout: float = 5.0,
    window_title: str = "window"
) -> Any:
    """
    Wait for a window to appear using intelligent polling.
    
    Specifically designed to replace the polling loops in chrome.py.
    
    Args:
        get_windows_func: Function that returns list of windows (e.g., lambda: gw.getWindowsWithTitle(title))
        timeout: Maximum time to wait
        window_title: Window title for error messages
    
    Returns:
        The first window from the list
    
    Raises:
        TimeoutError if window not found within timeout
    
    Example:
        # OLD:
        for _ in range(50):
            windows = gw.getWindowsWithTitle(DC_TITLE)
            if windows:
                state.dc_win = windows[0]
                break
            time.sleep(0.1)
        
        # NEW:
        state.dc_win = wait_for_window(
            lambda: gw.getWindowsWithTitle(DC_TITLE),
            timeout=5.0,
            window_title=DC_TITLE
        )
    """
    start_time = time.time()
    interval = 0.1
    last_check_time = start_time
    
    while time.time() - start_time < timeout:
        windows = get_windows_func()
        if windows:
            elapsed = time.time() - start_time
            print(f"[PERFORMANCE] Window '{window_title}' found in {elapsed:.3f}s")
            return windows[0]
        
        # Only sleep if we haven't exceeded timeout
        current_time = time.time()
        if current_time - start_time < timeout:
            time.sleep(interval)
            last_check_time = current_time
    
    raise TimeoutError(f"Window '{window_title}' not found within {timeout}s")


class WindowNotFoundError(Exception):
    """Raised when a window cannot be found."""
    pass


# Example usage and migration guide
if __name__ == "__main__":
    print("Retry Utils - Migration Examples")
    print("=" * 50)
    
    print("\n1. Replace polling loop:")
    print("   OLD: for _ in range(50): check(); time.sleep(0.1)")
    print("   NEW: wait_for_window(lambda: gw.getWindowsWithTitle(title), timeout=5.0)")
    
    print("\n2. Replace retry with sleep:")
    print("   OLD: for attempt in range(3): try: action(); break; except: time.sleep(0.1)")
    print("   NEW: @retry_with_backoff(max_attempts=3) def action(): ...")
    
    print("\n3. Benefits:")
    print("   - Succeeds immediately when ready (not waiting full timeout)")
    print("   - Exponential backoff reduces CPU usage")
    print("   - Better error messages")
    print("   - Performance tracking built-in")
