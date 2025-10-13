# userscript_injector.py
# Direct userscript injection via Selenium (no Tampermonkey needed!)

import os
import sys
import glob
from utils import resource_path
from constants import USERSCRIPTS_DIR

def get_userscripts_directory() -> str:
    """Get the absolute path to the userscripts directory."""
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        return os.path.join(exe_dir, USERSCRIPTS_DIR)
    return resource_path(USERSCRIPTS_DIR)

def read_all_userscripts() -> str:
    """
    Read and combine ALL userscripts from the userscripts directory.
    Strips Tampermonkey headers since we're injecting directly.
    The @namespace, @match, etc. metadata is only for Tampermonkey - we ignore it.
    
    Returns:
        Combined JavaScript content from all .user.js files
    """
    userscripts_dir = get_userscripts_directory()
    
    if not os.path.exists(userscripts_dir):
        print(f"[WARNING] Userscripts directory not found: {userscripts_dir}")
        return ""
    
    # Find all .user.js files
    script_files = glob.glob(os.path.join(userscripts_dir, "*.user.js"))
    
    if not script_files:
        print(f"[WARNING] No .user.js files found in {userscripts_dir}")
        return ""
    
    combined_content = []
    
    for script_path in sorted(script_files):
        script_name = os.path.basename(script_path)
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Remove Tampermonkey metadata block (not needed for direct injection)
            # Keep only the actual JavaScript code
            if "// ==UserScript==" in content and "// ==/UserScript==" in content:
                start = content.index("// ==/UserScript==") + len("// ==/UserScript==")
                content = content[start:].strip()
            
            # Add to combined content with separator comment
            combined_content.append(f"\n// ===== {script_name} =====\n")
            combined_content.append(content)
            
            print(f"[INFO] Loaded {script_name}: {len(content):,} bytes")
            
        except Exception as e:
            print(f"[ERROR] Failed to load {script_name}: {e}")
            continue
    
    final_content = "\n".join(combined_content)
    print(f"[INFO] Total userscript content: {len(final_content):,} bytes from {len(script_files)} files")
    
    return final_content

def inject_userscript(driver):
    """
    Inject ALL userscripts into the current page.
    Call this after each page load.
    
    Args:
        driver: Selenium WebDriver instance
    
    Returns:
        bool: True if injection successful
    """
    try:
        script_content = read_all_userscripts()
        if not script_content:
            print("[WARNING] No userscript content to inject")
            return False
        
        # Add marker to track injection
        marker = "window.ScalePlusInjected = true;"
        
        # Wrap the script in try-catch to capture any errors
        # Use template strings carefully to avoid breaking the script
        wrapped_script = marker + "\n" + "try {\n" + script_content + "\n} catch(e) { console.error('[USERSCRIPT ERROR]', e.message, e.stack); window.ScalePlusError = e.message; }"
        
        # Inject the script into the page
        driver.execute_script(wrapped_script)
        print("[SUCCESS] Userscripts injected directly into page!")
        
        # Verify it worked
        try:
            result = driver.execute_script("return window.ScalePlusInjected;")
            error = driver.execute_script("return window.ScalePlusError;")
            
            if error:
                print(f"[ERROR] ❌ Userscript execution error: {error}")
            elif result:
                print("[VERIFY] ✅ Injection confirmed - marker detected!")
            else:
                print("[VERIFY] ⚠️ Injection may have failed - marker not found")
        except Exception as e:
            print(f"[VERIFY] Could not verify injection: {e}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to inject userscript: {e}")
        import traceback
        traceback.print_exc()
        return False

def setup_auto_injection(driver):
    """
    Set up automatic injection of ALL userscripts on every page load.
    Uses Chrome DevTools Protocol (CDP) to inject before page scripts run.
    
    Args:
        driver: Selenium WebDriver instance
    
    Returns:
        bool: True if setup successful
    """
    try:
        script_content = read_all_userscripts()
        if not script_content:
            print("[ERROR] No userscript content to inject")
            return False
        
        # Add marker to track injection
        marker = "window.ScalePlusInjected = true;\nconsole.log('[USERSCRIPT] ScalePlus injected via CDP');"
        full_script = marker + "\n" + script_content
        
        print(f"[DEBUG] Attempting CDP injection ({len(full_script):,} bytes)...")
        
        # Use CDP to inject script on every new document
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': full_script
        })
        
        print("[SUCCESS] ✅ Auto-injection enabled via CDP!")
        print("[INFO] Script will run on every new page automatically")
        return True
        
    except Exception as e:
        print(f"[WARNING] ⚠️ CDP auto-injection failed: {e}")
        print("[INFO] Falling back to manual injection...")
        import traceback
        traceback.print_exc()
        return False

def inject_on_scale_pages(driver):
    """
    Check if current page is a Scale page and inject ALL userscripts.
    Safe to call repeatedly.
    
    Args:
        driver: Selenium WebDriver instance
    """
    try:
        current_url = driver.current_url
        
        # Only inject on Scale pages
        if "scale" in current_url.lower() and "byjasco.com" in current_url.lower():
            # Check if already injected (look for our marker)
            already_injected = driver.execute_script(
                "return window.ScalePlusInjected === true;"
            )
            
            if not already_injected:
                script_content = read_all_userscripts()
                if script_content:
                    # Add marker to prevent duplicate injection
                    marker = "window.ScalePlusInjected = true;"
                    driver.execute_script(marker + "\n" + script_content)
                    print(f"[INFO] ScalePlus injected on {current_url}")
            else:
                print(f"[DEBUG] ScalePlus already active on {current_url}")
        else:
            print(f"[DEBUG] Skipping injection - not a Scale page: {current_url}")
            
    except Exception as e:
        print(f"[DEBUG] Injection check failed: {e}")
