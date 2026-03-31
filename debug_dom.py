#!/usr/bin/env python3
"""
Quick debug script to inspect ZipRecruiter's actual DOM structure.
Specifically: right pane buttons, filter panel, and apply button selectors.
"""
import json
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from dotenv import load_dotenv

load_dotenv()

# Launch browser
options = Options()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)
options.add_experimental_option("detach", True)
driver = webdriver.Chrome(options=options)
driver.implicitly_wait(1)

print("🚀 Browser launched. Navigating to login page...")
driver.get("https://www.ziprecruiter.com/login")

# Auto-fill email
email = os.getenv("ZIPRECRUITER_EMAIL", "")
if email:
    time.sleep(3)
    try:
        email_field = driver.find_element(By.CSS_SELECTOR, "input[type='email'], input[name='email'], #email")
        for char in email:
            email_field.send_keys(char)
            time.sleep(0.05)
        print(f"✅ Email entered: {email[:3]}***")
    except Exception as e:
        print(f"⚠️ Could not enter email: {e}")

print("\n" + "="*60)
print("👉 PLEASE LOG IN MANUALLY in the browser window.")
print("   Then press ENTER here when you're logged in...")
print("="*60)
input()

# Navigate to search
url = "https://www.ziprecruiter.com/jobs-search?search=Data+Engineer&location=USA&days=1&quick_apply=true"
print(f"\n🔍 Navigating to: {url}")
driver.get(url)
time.sleep(5)

# Remove overlays
driver.execute_script("""
    document.querySelectorAll('div[role="dialog"]').forEach(el => el.remove());
    document.querySelectorAll('[class*="backdrop"], [class*="Backdrop"]').forEach(el => el.remove());
    document.body.style.overflow = 'auto';
""")
time.sleep(1)

# Click first job card
print("\n📋 Clicking first job card...")
result = driver.execute_script("""
    let card = document.querySelector("article[id^='job-card-']");
    if (card) { 
        card.click(); 
        return 'Clicked: ' + card.id; 
    }
    return 'No card found';
""")
print(f"   {result}")

# Wait for right pane to load
time.sleep(4)

# Remove overlays again
driver.execute_script("""
    document.querySelectorAll('div[role="dialog"]').forEach(el => el.remove());
    document.querySelectorAll('[class*="backdrop"], [class*="Backdrop"]').forEach(el => el.remove());
    document.body.style.overflow = 'auto';
""")
time.sleep(1)

# ═══════════════════════════════════════════════════════════
# INSPECT 1: All buttons and links in the right half of the page
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("🔍 INSPECTION 1: All clickable elements on right side")
print("="*60)

data = driver.execute_script("""
    let results = [];
    let els = document.querySelectorAll('button, a, input[type="submit"]');
    for (let el of els) {
        let rect = el.getBoundingClientRect();
        // Only elements on the right half or big enough
        if (rect.left > window.innerWidth * 0.3 || rect.width > window.innerWidth * 0.5) {
            if (rect.height > 0 && rect.width > 0) {
                results.push({
                    tag: el.tagName,
                    text: (el.innerText || '').trim().substring(0, 80),
                    class: (el.className || '').toString().substring(0, 120),
                    id: el.id || '',
                    href: (el.getAttribute('href') || '').substring(0, 80),
                    ariaLabel: el.getAttribute('aria-label') || '',
                    dataTestId: el.getAttribute('data-testid') || el.getAttribute('data-test-id') || '',
                    type: el.getAttribute('type') || '',
                    x: Math.round(rect.left),
                    y: Math.round(rect.top),
                    w: Math.round(rect.width),
                    h: Math.round(rect.height),
                    visible: el.offsetHeight > 0,
                });
            }
        }
    }
    return JSON.stringify(results, null, 2);
""")

parsed = json.loads(data)
for item in parsed:
    text_preview = item['text'][:60] if item['text'] else '(empty)'
    print(f"  <{item['tag']}> text=\"{text_preview}\"")
    if item['class']:
        print(f"     class=\"{item['class'][:80]}\"")
    if item['ariaLabel']:
        print(f"     aria-label=\"{item['ariaLabel']}\"")
    if item['dataTestId']:
        print(f"     data-testid=\"{item['dataTestId']}\"")
    if item['href']:
        print(f"     href=\"{item['href']}\"")
    print(f"     pos=({item['x']},{item['y']}) size={item['w']}x{item['h']}")
    print()

# ═══════════════════════════════════════════════════════════
# INSPECT 2: The filter panel / sidebar structure
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("🔍 INSPECTION 2: Filter panel elements")
print("="*60)

filters_data = driver.execute_script("""
    let results = [];
    // Look for radio buttons and their labels
    let radios = document.querySelectorAll('input[type="radio"]');
    for (let r of radios) {
        let label = '';
        if (r.id) {
            let labelEl = document.querySelector('label[for="' + r.id + '"]');
            if (labelEl) label = labelEl.innerText.trim();
        }
        results.push({
            type: 'radio',
            name: r.name || '',
            value: r.value || '',
            id: r.id || '',
            label: label,
            checked: r.checked,
            visible: r.offsetHeight > 0 || (r.parentElement && r.parentElement.offsetHeight > 0),
        });
    }
    // Look for checkboxes
    let checks = document.querySelectorAll('input[type="checkbox"]');
    for (let c of checks) {
        let label = '';
        if (c.id) {
            let labelEl = document.querySelector('label[for="' + c.id + '"]');
            if (labelEl) label = labelEl.innerText.trim();
        }
        results.push({
            type: 'checkbox',
            name: c.name || '',
            value: c.value || '',
            id: c.id || '',
            label: label,
            checked: c.checked,
            visible: c.offsetHeight > 0 || (c.parentElement && c.parentElement.offsetHeight > 0),
        });
    }
    return JSON.stringify(results, null, 2);
""")

filter_parsed = json.loads(filters_data)
for item in filter_parsed:
    status = "✅" if item['checked'] else "⬜"
    vis = "👁" if item['visible'] else "🚫"
    print(f"  {status} {vis} [{item['type']}] name=\"{item['name']}\" value=\"{item['value']}\" label=\"{item['label']}\"")

# ═══════════════════════════════════════════════════════════
# INSPECT 3: Anything with "apply" in text/class/aria
# ═══════════════════════════════════════════════════════════
print("\n" + "="*60)
print("🔍 INSPECTION 3: Elements containing 'apply' text")
print("="*60)

apply_data = driver.execute_script("""
    let results = [];
    let all = document.querySelectorAll('*');
    for (let el of all) {
        let text = (el.innerText || el.textContent || '').trim().toLowerCase();
        let aria = (el.getAttribute('aria-label') || '').toLowerCase();
        let cls = (el.className || '').toString().toLowerCase();
        if ((text.includes('apply') || aria.includes('apply') || cls.includes('apply'))
            && el.tagName !== 'HTML' && el.tagName !== 'BODY'
            && (el.tagName === 'BUTTON' || el.tagName === 'A' || el.tagName === 'INPUT'
                || el.tagName === 'SPAN' || el.tagName === 'DIV')) {
            let rect = el.getBoundingClientRect();
            results.push({
                tag: el.tagName,
                text: (el.innerText || '').trim().substring(0, 100),
                class: (el.className || '').toString().substring(0, 120),
                ariaLabel: el.getAttribute('aria-label') || '',
                dataTestId: el.getAttribute('data-testid') || el.getAttribute('data-test-id') || '',
                href: (el.getAttribute('href') || '').substring(0, 80),
                x: Math.round(rect.left),
                y: Math.round(rect.top),
                w: Math.round(rect.width),
                h: Math.round(rect.height),
                visible: rect.height > 0 && rect.width > 0,
            });
        }
    }
    return JSON.stringify(results, null, 2);
""")

apply_parsed = json.loads(apply_data)
for item in apply_parsed:
    vis = "👁" if item['visible'] else "🚫"
    print(f"  {vis} <{item['tag']}> text=\"{item['text'][:80]}\"")
    if item['class']:
        print(f"     class=\"{item['class'][:80]}\"")
    if item['ariaLabel']:
        print(f"     aria-label=\"{item['ariaLabel']}\"")
    if item['dataTestId']:
        print(f"     data-testid=\"{item['dataTestId']}\"")
    print(f"     pos=({item['x']},{item['y']}) size={item['w']}x{item['h']}")
    print()

print("\n" + "="*60)
print("✅ Done! Copy the output above and share it.")
print("   The browser is still open for manual inspection.")
print("="*60)
