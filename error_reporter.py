# error_reporter.py
# Centralized error logging and reporting system

import logging
import sys
import traceback
from datetime import datetime
import socket
import platform
import json
import requests
from tkinter import messagebox
import threading


# Set up logger
logger = logging.getLogger("BrowserControl")
logger.setLevel(logging.DEBUG)

# Console handler (important messages only)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(levelname)s: %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)


def get_system_info():
    """Gather system information for error reports"""
    try:
        hostname = socket.gethostname()
    except:
        hostname = "Unknown"
    
    return {
        "hostname": hostname,
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "timestamp": datetime.now().isoformat()
    }


def create_github_issue(title, body, labels=None):
    """
    Create a GitHub issue for critical errors
    
    Args:
        title: Issue title
        body: Issue body (markdown formatted)
        labels: List of labels (default: ['bug', 'auto-reported'])
    
    Returns:
        Tuple of (success: bool, message: str, issue_url: str)
    """
    if labels is None:
        labels = ['bug', 'auto-reported']
    
    # Import here to avoid circular imports
    try:
        from constants import GITHUB_TOKEN, GITHUB_ISSUES_REPO
    except ImportError:
        return False, "GitHub configuration not found in constants.py", ""
    
    # GitHub API configuration
    GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_ISSUES_REPO}/issues"
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {GITHUB_TOKEN}"
    }
    
    data = {
        "title": title,
        "body": body,
        "labels": labels
    }
    
    try:
        response = requests.post(
            GITHUB_API_URL,
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 201:
            issue_url = response.json().get("html_url", "")
            return True, "GitHub issue created successfully", issue_url
        elif response.status_code == 401:
            return False, f"GitHub authentication failed: {response.text}", ""
        else:
            return False, f"GitHub API error {response.status_code}: {response.text}", ""
            
    except requests.RequestException as e:
        return False, f"Failed to create GitHub issue: {str(e)}", ""


def report_critical_error(error_type, error_message, traceback_str=None, 
                          create_issue=True, show_popup=True):
    """
    Report a critical error with full logging and optional GitHub issue creation
    
    Args:
        error_type: Type of error (e.g., "ChromeDriver", "LDAP", "Startup")
        error_message: Human-readable error message
        traceback_str: Full traceback string (optional)
        create_issue: Whether to create a GitHub issue
        show_popup: Whether to show a popup to the user
    
    Returns:
        Dict with report details
    """
    system_info = get_system_info()
    
    # Log the error
    logger.error(f"CRITICAL ERROR [{error_type}]: {error_message}")
    if traceback_str:
        logger.error(f"Traceback:\n{traceback_str}")
    logger.error(f"System Info: {json.dumps(system_info, indent=2)}")
    
    # Prepare report
    report = {
        "error_type": error_type,
        "error_message": error_message,
        "traceback": traceback_str,
        "system_info": system_info,
    }
    
    # Create GitHub issue in background thread
    issue_url = None
    if create_issue:
        def create_issue_async():
            nonlocal issue_url
            
            logger.info("Creating GitHub issue...")
            
            # Format GitHub issue body
            body = f"""## Critical Error: {error_type}

**Error Message:**
```
{error_message}
```

**System Information:**
- **Hostname:** {system_info['hostname']}
- **Platform:** {system_info['platform']} {system_info['platform_release']}
- **Architecture:** {system_info['architecture']}
- **Python Version:** {system_info['python_version']}
- **Timestamp:** {system_info['timestamp']}

**Traceback:**
```python
{traceback_str or 'No traceback available'}
```

---
*This issue was automatically created by the error reporting system.*
"""
            
            title = f"[Auto-Report] {error_type}: {error_message[:80]}"
            success, message, url = create_github_issue(title, body)
            
            if success:
                logger.info(f"✅ GitHub issue created: {url}")
                issue_url = url
            else:
                logger.error(f"❌ Could not create GitHub issue: {message}")
        
        thread = threading.Thread(target=create_issue_async, daemon=True)
        thread.start()
        # Give the thread a moment to start
        thread.join(timeout=5)  # Wait up to 5 seconds for issue creation
    
    # Show popup to user
    if show_popup:
        popup_message = f"""A critical error occurred:

{error_type}: {error_message}

Please contact support if the issue persists."""
        
        if create_issue:
            popup_message += "\n\nAn automatic error report has been submitted."
        
        try:
            messagebox.showerror("Critical Error", popup_message)
        except:
            # If messagebox fails, just log it
            logger.error("Could not show error popup to user")
    
    return report


def log_chrome_version_mismatch(chromedriver_version, chrome_version):
    """Specific handler for ChromeDriver version mismatch"""
    error_message = (
        f"ChromeDriver version mismatch!\n"
        f"ChromeDriver supports Chrome {chromedriver_version}\n"
        f"Current Chrome browser is version {chrome_version}"
    )
    
    traceback_str = traceback.format_exc()
    
    return report_critical_error(
        error_type="ChromeDriver Version Mismatch",
        error_message=error_message,
        traceback_str=traceback_str,
        create_issue=True,
        show_popup=True
    )


def log_startup_error(exception):
    """Log startup errors with full context"""
    error_message = str(exception)
    traceback_str = traceback.format_exc()
    
    return report_critical_error(
        error_type="Startup Error",
        error_message=error_message,
        traceback_str=traceback_str,
        create_issue=True,
        show_popup=True
    )


def log_chrome_launch_error(exception):
    """Log Chrome launch errors with full context"""
    error_message = str(exception)
    traceback_str = traceback.format_exc()
    
    # Check if it's a version mismatch
    if "This version of ChromeDriver" in error_message and "Current browser version is" in error_message:
        # Parse versions from error message
        import re
        chromedriver_match = re.search(r'supports Chrome version (\d+)', error_message)
        chrome_match = re.search(r'Current browser version is (\d+)', error_message)
        
        if chromedriver_match and chrome_match:
            return log_chrome_version_mismatch(
                chromedriver_match.group(1),
                chrome_match.group(1)
            )
    
    return report_critical_error(
        error_type="Chrome Launch Failed",
        error_message=error_message,
        traceback_str=traceback_str,
        create_issue=True,
        show_popup=True
    )


# Set up exception hook to catch unhandled exceptions
def exception_hook(exc_type, exc_value, exc_traceback):
    """Global exception handler"""
    if issubclass(exc_type, KeyboardInterrupt):
        # Don't report keyboard interrupts
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    error_message = str(exc_value)
    traceback_str = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    
    report_critical_error(
        error_type=exc_type.__name__,
        error_message=error_message,
        traceback_str=traceback_str,
        create_issue=True,
        show_popup=True
    )

# Install global exception hook
sys.excepthook = exception_hook


# Export logger and functions
__all__ = [
    'logger',
    'report_critical_error',
    'log_chrome_version_mismatch',
    'log_startup_error',
    'log_chrome_launch_error',
    'get_system_info',
]
