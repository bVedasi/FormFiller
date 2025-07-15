import speech_recognition as sr
import pyttsx3
import time
from playwright.sync_api import sync_playwright
import re
import os
import glob
from pathlib import Path

recognizer = sr.Recognizer()
tts_engine = pyttsx3.init()
tts_engine.setProperty('rate', 160)

def speak(text):
    print(f"[Bot]: {text}")
    tts_engine.say(text)
    tts_engine.runAndWait()

def listen(timeout=8):
    with sr.Microphone() as source:
        print("[Listening...]")
        audio = recognizer.listen(source, phrase_time_limit=timeout)
    try:
        text = recognizer.recognize_google(audio)
        print(f"[User]: {text}")
        return text
    except sr.UnknownValueError:
        speak("Sorry, I didn't catch that. Please repeat.")
        return listen(timeout)
    except sr.RequestError:
        speak("API unavailable. Try again.")
        return ""

def get_letter_by_letter(text):
    return ' '.join(list(text))

def get_digit_by_digit(text):
    """Convert numbers to digit-by-digit reading, preserving non-numeric characters"""
    result = []
    for char in text:
        if char.isdigit():
            result.append(char)
        else:
            result.append(char)
    return ' '.join(result)

def analyze_form_fields(page):
    """Analyze the form and extract field information"""
    fields = []
    
    # Find all input, select, and textarea elements
    form_elements = page.query_selector_all("input, select, textarea")
    
    for element in form_elements:
        field_info = {}
        
        # Get element type
        tag_name = element.evaluate("el => el.tagName.toLowerCase()")
        input_type = element.get_attribute("type") or "text"
        
        # Skip hidden, submit, and button inputs
        if input_type in ["hidden", "submit", "button", "reset"]:
            continue
            
        # Get field label
        label = get_field_label(page, element)
        if not label:
            continue
            
        # Determine field type and purpose
        field_info["element"] = element
        field_info["label"] = label
        field_info["selector"] = get_element_selector(element)
        field_info["required"] = element.get_attribute("required") is not None
        
        if tag_name == "select":
            field_info["type"] = "dropdown"
            field_info["options"] = get_dropdown_options(element)
        elif tag_name == "textarea":
            field_info["type"] = "textarea"
        elif input_type == "checkbox":
            field_info["type"] = "checkbox"
        elif input_type == "radio":
            field_info["type"] = "radio"
        elif input_type in ["email", "tel", "phone"]:
            field_info["type"] = input_type
        else:
            field_info["type"] = "text"
            
        # Determine field purpose based on label/name/id
        field_info["purpose"] = determine_field_purpose(label, element)
        
        fields.append(field_info)
    
    return fields

def get_field_label(page, element):
    """Get the label for a form field"""
    # Try to find associated label
    element_id = element.get_attribute("id")
    if element_id:
        label_element = page.query_selector(f"label[for='{element_id}']")
        if label_element:
            return label_element.inner_text().strip()
    
    # Try to find parent label
    parent_label = element.query_selector("xpath=ancestor::label")
    if parent_label:
        return parent_label.inner_text().strip()
    
    # Try placeholder
    placeholder = element.get_attribute("placeholder")
    if placeholder:
        return placeholder
    
    # Try name attribute
    name = element.get_attribute("name")
    if name:
        return name.replace("_", " ").replace("-", " ").title()
    
    # Try nearby text
    nearby_text = element.evaluate("""
        el => {
            const prev = el.previousElementSibling;
            if (prev && prev.textContent.trim()) return prev.textContent.trim();
            const parent = el.parentElement;
            if (parent) {
                const text = parent.textContent.replace(el.value || '', '').trim();
                if (text) return text;
            }
            return '';
        }
    """)
    
    return nearby_text or "Unknown Field"

def get_element_selector(element):
    """Generate a selector for the element"""
    element_id = element.get_attribute("id")
    if element_id:
        return f"#{element_id}"
    
    name = element.get_attribute("name")
    if name:
        return f"[name='{name}']"
    
    return element.evaluate("el => el.tagName.toLowerCase()")

def get_dropdown_options(element):
    """Get options for a dropdown"""
    options = []
    option_elements = element.query_selector_all("option")
    for option in option_elements:
        text = option.inner_text().strip()
        value = option.get_attribute("value")
        if text and text.lower() not in ["select", "choose", "pick"]:
            options.append({"text": text, "value": value})
    return options

def determine_field_purpose(label, element):
    """Determine what kind of information the field is asking for"""
    label_lower = label.lower()
    name_attr = (element.get_attribute("name") or "").lower()
    id_attr = (element.get_attribute("id") or "").lower()
    input_type = (element.get_attribute("type") or "").lower()
    
    combined = f"{label_lower} {name_attr} {id_attr}"
    
    # Check for file upload first
    if input_type == "file" or any(word in combined for word in ["upload", "file", "attach", "document", "resume", "cv"]):
        return "file_upload"
    elif any(word in combined for word in ["first", "fname", "firstname"]):
        return "first_name"
    elif any(word in combined for word in ["last", "lname", "lastname", "surname"]):
        return "last_name"
    elif any(word in combined for word in ["email", "mail"]):
        return "email"
    elif any(word in combined for word in ["phone", "tel", "mobile", "number"]):
        return "phone"
    elif any(word in combined for word in ["address", "street"]):
        return "address"
    elif any(word in combined for word in ["city", "town"]):
        return "city"
    elif any(word in combined for word in ["state", "province"]):
        return "state"
    elif any(word in combined for word in ["zip", "postal", "pincode"]):
        return "zip"
    elif any(word in combined for word in ["country"]):
        return "country"
    elif any(word in combined for word in ["age", "birth", "dob", "date"]):
        return "age_date"
    elif any(word in combined for word in ["gender", "sex"]):
        return "gender"
    elif any(word in combined for word in ["company", "organization"]):
        return "company"
    elif any(word in combined for word in ["message", "comment", "feedback"]):
        return "message"
    else:
        return "other"

def confirm_entry(field_name, value, is_name=False, is_numeric=False):
    speak(f"You entered for {field_name}:")
    if is_name:
        speak(get_letter_by_letter(value))
    elif is_numeric:
        speak(get_digit_by_digit(value))
    else:
        speak(value)
    speak("Do you want to confirm? Say Yes or No.")
    confirmation = listen().lower()
    return 'yes' in confirmation

def fill_field_by_purpose(page, field):
    """Fill field based on its purpose"""
    purpose = field["purpose"]
    label = field["label"]
    element = field["element"]
    
    # Check if element is visible and enabled
    if not element.is_visible() or not element.is_enabled():
        speak(f"Skipping {label} - field not accessible")
        return
    
    if field["type"] == "text":
        if purpose in ["first_name", "last_name"]:
            fill_name_field(page, field)
        elif purpose == "email":
            fill_email_field(page, field)
        elif purpose == "phone":
            fill_phone_field(page, field)
        elif purpose == "zip":
            fill_zip_field(page, field)
        elif purpose == "age_date":
            fill_date_field(page, field)
        elif purpose == "file_upload":
            handle_file_upload(page, field)
        else:
            fill_text_field(page, field)
    elif field["type"] == "dropdown":
        handle_dropdown(page, field)
    elif field["type"] == "checkbox":
        handle_checkbox(page, field)
    elif field["type"] == "textarea":
        fill_textarea_field(page, field)
    elif purpose == "file_upload":  # Handle file input type
        handle_file_upload(page, field)

def fill_name_field(page, field):
    """Fill name fields with letter-by-letter confirmation"""
    while True:
        speak(f"Please say your {field['label']}")
        response = listen(timeout=8)
        if confirm_entry(field["label"], response, is_name=True):
            field["element"].fill(response)
            break
        else:
            speak("Let's try again.")

def fill_email_field(page, field):
    """Fill email field"""
    while True:
        speak(f"Please say your {field['label']}")
        response = listen(timeout=10)
        if confirm_entry(field["label"], response):
            field["element"].fill(response)
            break
        else:
            speak("Let's try again.")

def fill_phone_field(page, field):
    """Fill phone field"""
    while True:
        speak(f"Please say your {field['label']}")
        response = listen(timeout=10)
        if confirm_entry(field["label"], response, is_numeric=True):
            field["element"].fill(response)
            break
        else:
            speak("Let's try again.")

def fill_zip_field(page, field):
    """Fill zip/postal code field"""
    while True:
        speak(f"Please say your {field['label']}")
        response = listen(timeout=10)
        if confirm_entry(field["label"], response, is_numeric=True):
            field["element"].fill(response)
            break
        else:
            speak("Let's try again.")

def fill_date_field(page, field):
    """Fill date/age field (no digit-by-digit reading)"""
    while True:
        speak(f"Please say your {field['label']}")
        response = listen(timeout=10)
        if confirm_entry(field["label"], response):
            field["element"].fill(response)
            break
        else:
            speak("Let's try again.")

def fill_text_field(page, field):
    """Fill generic text field"""
    while True:
        speak(f"Please say your {field['label']}")
        response = listen(timeout=10)
        if confirm_entry(field["label"], response):
            field["element"].fill(response)
            break
        else:
            speak("Let's try again.")

def fill_textarea_field(page, field):
    """Fill textarea field"""
    while True:
        speak(f"Please provide your {field['label']}")
        response = listen(timeout=15)
        if confirm_entry(field["label"], response):
            field["element"].fill(response)
            break
        else:
            speak("Let's try again.")

def handle_dropdown(page, field):
    """Handle dropdown selection"""
    speak(f"Available options for {field['label']} are:")
    options = field["options"]
    for option in options:
        speak(option["text"])

    speak("Please say your choice.")
    choice = listen().lower()
    for option in options:
        if choice in option["text"].lower():
            field["element"].select_option(option["value"])
            speak(f"{option['text']} selected for {field['label']}")
            return
    speak("Option not found. Skipping.")

def handle_checkbox(page, field):
    """Handle checkbox"""
    speak(f"This is a checkbox for: {field['label']}. Do you want to check it?")
    response = listen().lower()
    if "yes" in response or "check" in response:
        field["element"].check()
        speak(f"Checkbox for {field['label']} has been checked.")
    else:
        speak(f"Checkbox for {field['label']} left unchecked.")

def search_file_by_name(filename):
    """Search for a file by name in the user's home directory and common locations"""
    home_dir = Path.home()
    
    # Common directories to search
    search_paths = [
        home_dir,
        home_dir / "Desktop",
        home_dir / "Documents",
        home_dir / "Downloads",
        home_dir / "Pictures",
        home_dir / "Videos",
    ]
    
    # Search patterns
    search_patterns = [
        f"**/{filename}",
        f"**/{filename}.*",
        f"**/*{filename}*",
        f"**/*{filename}*.*"
    ]
    
    found_files = []
    
    for search_path in search_paths:
        if search_path.exists():
            for pattern in search_patterns:
                try:
                    matches = list(search_path.glob(pattern))
                    for match in matches:
                        if match.is_file():
                            found_files.append(str(match))
                except:
                    continue
    
    # Remove duplicates and sort by relevance
    found_files = list(set(found_files))
    
    # Sort by exact match first, then by filename similarity
    def sort_key(filepath):
        file_name = os.path.basename(filepath).lower()
        filename_lower = filename.lower()
        
        if file_name == filename_lower:
            return 0  # Exact match
        elif file_name.startswith(filename_lower):
            return 1  # Starts with
        elif filename_lower in file_name:
            return 2  # Contains
        else:
            return 3  # Other matches
    
    found_files.sort(key=sort_key)
    return found_files[:5]  # Return top 5 matches

def handle_file_upload(page, field):
    """Handle file upload field"""
    speak(f"This is a file upload field for: {field['label']}")
    
    try:
        # First, click the file upload element to trigger file explorer or options
        speak("Clicking upload button...")
        field["element"].click()
        
        # Wait a moment to see if file explorer opens or options appear
        time.sleep(1)
        
        # Check if we can directly upload (file explorer opened)
        try:
            # Try to upload a dummy file to test if file explorer is open
            # This will fail if file explorer isn't open, which is what we want
            test_file = str(Path.home() / "test_dummy_file_that_doesnt_exist.txt")
            field["element"].set_input_files([])  # Clear any existing files
            
            # If we reach here, file explorer is ready - proceed with file selection
            speak("File explorer is ready. Please tell me the name of the file you want to upload.")
            
        except Exception:
            # File explorer didn't open directly, look for upload options
            speak("Looking for upload options...")
            time.sleep(1)
            
            # Check if there are upload options (like "Choose from Drive", "Upload from Computer")
            upload_options = page.query_selector_all("button, div, span, a")
            relevant_options = []
            
            for option in upload_options:
                if option.is_visible():
                    text = option.inner_text().strip().lower()
                    # More specific filtering for upload options
                    if (any(keyword in text for keyword in ["upload", "choose", "browse", "select"]) and 
                        any(keyword in text for keyword in ["computer", "device", "pc", "local", "file", "system"]) and
                        len(text) < 100):  # Avoid long text blocks
                        
                        if any(keyword in text for keyword in ["computer", "device", "pc", "local", "browse"]):
                            relevant_options.append({"element": option, "text": text, "priority": 1})
                        else:
                            relevant_options.append({"element": option, "text": text, "priority": 2})
            
            # Sort by priority (computer/device options first)
            relevant_options.sort(key=lambda x: x["priority"])
            
            # If we found upload options, present them to user
            if relevant_options:
                speak("I found upload options. Available choices are:")
                for i, option in enumerate(relevant_options[:3], 1):  # Show top 3 options
                    speak(f"Option {i}: {option['text']}")
                
                speak("Please say the number of your choice, or say 'first' for option 1.")
                choice = listen().lower()
                
                selected_option = None
                if "first" in choice or "1" in choice:
                    selected_option = relevant_options[0]
                elif "second" in choice or "2" in choice and len(relevant_options) >= 2:
                    selected_option = relevant_options[1]
                elif "third" in choice or "3" in choice and len(relevant_options) >= 3:
                    selected_option = relevant_options[2]
                
                if selected_option:
                    speak(f"Selecting: {selected_option['text']}")
                    selected_option["element"].click()
                    time.sleep(2)
                else:
                    speak("Invalid choice. Trying default file upload.")
            else:
                speak("No specific upload options found. Proceeding with file selection.")
            
            speak("Please tell me the name of the file you want to upload.")
        
        # Now handle the actual file selection
        while True:
            filename = listen(timeout=10)
            if not filename:
                speak("No filename provided. Skipping this field.")
                return
            
            speak(f"Searching for file: {filename}")
            found_files = search_file_by_name(filename)
            
            if not found_files:
                speak(f"No files found with name '{filename}'. Would you like to try a different name?")
                response = listen().lower()
                if "yes" in response:
                    continue
                else:
                    speak("Skipping file upload.")
                    return
            
            # If multiple files found, let user choose
            if len(found_files) == 1:
                selected_file = found_files[0]
                speak(f"Found file: {os.path.basename(selected_file)}")
            else:
                speak(f"Found {len(found_files)} files. Here are the options:")
                for i, filepath in enumerate(found_files, 1):
                    speak(f"Option {i}: {os.path.basename(filepath)}")
                
                speak("Please say the number of the file you want to upload, or say 'first' for option 1.")
                choice = listen().lower()
                
                selected_file = None
                if "first" in choice or "1" in choice:
                    selected_file = found_files[0]
                elif "second" in choice or "2" in choice and len(found_files) >= 2:
                    selected_file = found_files[1]
                elif "third" in choice or "3" in choice and len(found_files) >= 3:
                    selected_file = found_files[2]
                elif "fourth" in choice or "4" in choice and len(found_files) >= 4:
                    selected_file = found_files[3]
                elif "fifth" in choice or "5" in choice and len(found_files) >= 5:
                    selected_file = found_files[4]
                
                if not selected_file:
                    speak("Invalid choice. Skipping file upload.")
                    return
            
            # Confirm file selection
            speak(f"Selected file: {os.path.basename(selected_file)}")
            speak("Do you want to upload this file? Say Yes or No.")
            confirmation = listen().lower()
            
            if "yes" in confirmation:
                try:
                    # Try to upload the file to the original element
                    field["element"].set_input_files(selected_file)
                    speak(f"File {os.path.basename(selected_file)} uploaded successfully.")
                    return
                except Exception as e:
                    # If that fails, try to find a file input that appeared after clicking options
                    file_inputs = page.query_selector_all("input[type='file']")
                    upload_success = False
                    
                    for file_input in file_inputs:
                        if file_input.is_visible():
                            try:
                                file_input.set_input_files(selected_file)
                                speak(f"File {os.path.basename(selected_file)} uploaded successfully.")
                                upload_success = True
                                break
                            except:
                                continue
                    
                    if not upload_success:
                        speak(f"Error uploading file: {str(e)}")
                        speak("The file explorer should be open. Please manually select the file and I'll continue with the next field.")
                        input("Press Enter after you've selected the file...")
                        return
            else:
                speak("Would you like to try a different file?")
                response = listen().lower()
                if "yes" not in response:
                    return
                    
    except Exception as e:
        speak(f"Error with file upload: {str(e)}")
        speak("Please manually handle the file upload and press Enter to continue.")
        input("Press Enter to continue...")

def run_voice_filler():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # Get form URL from user
        speak("Please provide the form URL")
        form_url = input("Enter the form URL: ")
        
        page.goto(form_url)
        
        # Wait for page to load
        time.sleep(3)
        
        speak("Analyzing form fields...")
        fields = analyze_form_fields(page)
        
        if not fields:
            speak("No form fields found on this page.")
            browser.close()
            return
        
        speak(f"Found {len(fields)} form fields. Starting voice form filling.")
        
        for field in fields:
            speak(f"Processing {field['label']}")
            fill_field_by_purpose(page, field)
            time.sleep(1)

        speak("Form filling completed.")
        input("Press Enter to close browser...")
        browser.close()

if __name__ == "__main__":
    run_voice_filler()
