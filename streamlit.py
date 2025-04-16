import streamlit as st
import whisper
import speech_recognition as sr
from googletrans import Translator, LANGUAGES
from gtts import gTTS
import sqlite3
import hashlib
import tempfile
import time
import pandas as pd
from io import BytesIO
import smtplib
from email.mime.text import MIMEText
import re
from pydub import AudioSegment
from pydub.silence import split_on_silence
import random
import string
import pyaudio
import os
import numpy as np
from PIL import Image
import pytesseract
import fitz
import io
import cv2
import yt_dlp
import cv2
import pytesseract
from deep_translator import GoogleTranslator
import ffmpeg


# Initialize translator
translator = Translator()
languages = list(LANGUAGES.keys())

# ------------------- Whisper Model Setup -------------------
# Load the Whisper model (consider caching for efficiency)
@st.cache_resource
def load_whisper_model():
    model = whisper.load_model("medium")  # You can change the model size: "tiny", "base", "small", "medium", "large"
    return model


# ------------------- Database Setup -------------------
DATABASE_FILE = "sqli.db"

def setup_database():
    """Set up the database with 'users' and 'history' tables if they don't already exist."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # Create the 'users' table (no DROP TABLE to preserve existing data)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT NOT NULL
        )
    """)

    # Create the 'history' table (no DROP TABLE to preserve existing data)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            original_text TEXT NOT NULL,
            translated_text TEXT NOT NULL,
            target_language TEXT NOT NULL,
            source_language TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()

def hash_password(password):
    """Hash a password using SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()

def send_otp_email(to_email, otp):
    sender_email = "ssaisaravanan74@gmail.com"  # Replace with your Gmail
    sender_password = "kvrxtxgkbtpyjcyy"  # Replace with your new App Password

    msg = MIMEText(f"Your OTP for password reset is: {otp}")
    msg['Subject'] = "OTP for Password Reset"
    msg['From'] = sender_email
    msg['To'] = to_email

    try:
        # Use SSL and correct Gmail SMTP server
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        st.success(f"OTP sent to {to_email}. Please check your inbox or spam folder.")
    except smtplib.SMTPAuthenticationError:
        st.error("Authentication failed. Ensure your app password is correct.")
    except Exception as e:
        st.error(f"Failed to send OTP email: {e}")



def generate_otp():
    """Generate a 6-digit OTP."""
    otp = ''.join(random.choices('0123456789', k=6))
    print(f"Generated OTP: {otp}")  # Debugging: Log the OTP
    return otp


def update_password(username, new_password):
    """Update a user's password in the database."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    hashed_password = hash_password(new_password)
    cursor.execute("UPDATE users SET password_hash = ? WHERE username = ?", (hashed_password, username))
    conn.commit()
    conn.close()


# ------------------- Authentication Functions -------------------
def add_user(username, password, email):
    """Add a new user to the database."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    hashed_password = hash_password(password)
    try:
        cursor.execute("INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)", (username, hashed_password, email))
        conn.commit()
        st.success("Account created successfully!")
    except sqlite3.IntegrityError:
        st.error("Username already exists!")
    conn.close()

def verify_user(username, password):
    """Verify a user's credentials."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return hash_password(password) == result[0]
    return False

def get_email(username):
    """Get the email of a user."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


# ------------------- Email Sending Function -------------------


def update_password(username, new_password):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
    cursor.execute("UPDATE users SET password_hash = ? WHERE username = ?", (hashed_password, username))
    conn.commit()
    conn.close()

def get_user(username):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    return user

# ------------------- Translation and TTS Functions -------------------
def split_text_to_sentences(text):
    return re.split(r'(?<=[.!?]) +', text)  # Split at punctuation

# Load the Whisper model (consider caching for efficiency)
@st.cache_resource
def load_whisper_model():
    model = whisper.load_model("medium")  # You can change the model size: "tiny", "base", 
    return model

def get_language_code(language_name):
    for code, name in LANGUAGES.items():
        if name.lower() == language_name.lower():
            return code
    return None

def process_speech_to_speech(file=None, target_languages=[], recording=False, model=None):
    if model is None:
        model = whisper.load_model("medium")  # Load the Whisper Medium model for better transcription accuracy
    
    recognized_text = ''
    source_language_name = None

    if file:
        # Process uploaded audio file
        try:
            audio_data = AudioSegment.from_file(file)
            chunks = split_on_silence(audio_data, min_silence_len=500, silence_thresh=-40)

            for chunk in chunks:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio_file:
                    chunk.export(temp_audio_file.name, format="wav")
                    try:
                        result = model.transcribe(temp_audio_file.name)
                        recognized_text += result["text"] + " " if result and result["text"] else "[Error with Whisper] "
                    except Exception as e:
                        recognized_text += f"[Error with Whisper]: {e}"
                    finally:
                        temp_audio_file.close()
                        time.sleep(1)
                        os.unlink(temp_audio_file.name)
        except Exception as e:
            st.error(f"Error processing audio file: {e}")
            return None, None, None, None

    elif recording:
        # Process microphone input using Whisper AI
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            st.info("🎤 Listening... Speak now.")
            recognizer.adjust_for_ambient_noise(source)
            audio = recognizer.listen(source)
            st.info("Processing speech...")

        # Save microphone input as a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
            temp_audio.write(audio.get_wav_data())
            temp_filename = temp_audio.name

        try:
            # Transcribe speech using Whisper AI
            result = model.transcribe(temp_filename)
            recognized_text = result["text"] if result and result["text"] else "[No speech detected]"
            os.remove(temp_filename)  # Clean up
        except Exception as e:
            st.error(f"⚠️ Whisper AI Error: {e}")
            return None, None, {}, {}

    else:
        st.error("⚠️ No input method selected!")
        return None, None, {}, {}

    if not recognized_text.strip():
        st.error("⚠️ No speech detected!")
        return None, None, {}, {}

    # Detect the source language
    translator = Translator()
    try:
        detected_lang = translator.detect(recognized_text).lang
        source_language_name = LANGUAGES.get(detected_lang, detected_lang)
        st.info(f"🌍 Detected Language: {source_language_name}")
    except:
        source_language_name = "Unknown"

    # Translate text and convert to speech
    translations = {}
    tts_files = {}
    
    for lang in target_languages:
        lang_code = next((code for code, name in LANGUAGES.items() if name.lower() == lang.lower()), None)
        if lang_code:
            try:
                # Translate the recognized text using Google Translate API
                translated_text = translator.translate(recognized_text, dest=lang_code).text
                translations[lang] = translated_text
                
                # Convert the translated text to speech using gTTS
                tts = gTTS(translated_text, lang=lang_code)
                tts_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                tts.save(tts_file.name)
                tts_files[lang] = tts_file.name
                st.audio(tts_file.name)
            except Exception as e:
                st.error(f"⚠️ Translation Error ({lang}): {e}")
                continue

    return source_language_name, recognized_text, translations, tts_files

def text_to_speech(text, target_languages):
    tts_files = {}
    for lang in target_languages:
        lang_code = get_language_code(lang)
        if lang_code:
            sentences = split_text_to_sentences(text)
            combined_audio = BytesIO()
            for sentence in sentences:
                tts = gTTS(sentence, lang=lang_code)
                temp_file = BytesIO()
                tts.write_to_fp(temp_file)
                combined_audio.write(temp_file.getvalue())
            tts_files[lang] = combined_audio
    return tts_files

def translate_image(image, target_language):
    try:
        text = pytesseract.image_to_string(image)
        translated_text = translator.translate(text, dest=target_language).text
        return translated_text
    except Exception as e:
        st.error(f"Error processing image: {e}")
        return None


def translate_document(doc, target_language):
    translated_text = ""
    for page in doc:
        text = page.get_text("text")
        try:
            translated_page = translator.translate(text, dest=target_language).text
            translated_text += translated_page + "\n\n"
        except Exception as e:
            st.error(f"Error translating page: {e}")
            translated_text += f"Translation Error on this page:\n{text}\n\n"
    return translated_text

def download_video(youtube_url, output_video="video.mp4"):
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': output_video,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])
        return output_video
    except Exception as e:
        st.error(f"Error downloading video: {e}")
        return None

def download_audio(youtube_url, output_audio=None):
    if output_audio is None:
        output_audio = f"video_audio_{int(time.time())}.mp3"  # Unique filename
    ydl_opts = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'mp3',
        'outtmpl': output_audio,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])
        return output_audio
    except Exception as e:
        st.error(f"Error downloading audio: {e}")
        return None

def transcribe_audio(audio_path):
    try:
        model = load_whisper_model()
        st.write(f"Transcribing file: {audio_path}")  # Debugging
        result = model.transcribe(audio_path)
        return result['text']
    except Exception as e:
        st.error(f"Error transcribing audio: {e}")
        return None

def translate_text(text, target_language):
    try:
        st.write(f"Translating: {text[:50]}...")  # Log first 50 characters
        translator = Translator()
        translated = translator.translate(text, dest=target_language)
        return translated.text
    except Exception as e:
        st.error(f"Error translating text: {e}")
        return None

# Function to generate translated speech
def generate_subtitles(translated_text, output_srt="subtitles.srt"):
    try:
        with open(output_srt, "w", encoding="utf-8") as file:  # Specify encoding
            file.write("1\n00:00:00,000 --> 00:00:10,000\n" + translated_text + "\n")
        return output_srt
    except Exception as e:
        st.error(f"Error generating subtitles: {e}")
        return None

def generate_translated_speech(text, target_language, output_audio="translated_audio.mp3"):
    try:
        tts = gTTS(text=text, lang=target_language)
        tts.save(output_audio)
        return output_audio
    except Exception as e:
        st.error(f"Error generating translated speech: {e}")
        return None

# Function to wait for file to be written
def wait_for_file(filepath, timeout=30):
    start_time = time.time()
    last_size = -1
    while time.time() - start_time < timeout:
        try:
            current_size = os.path.getsize(filepath)
            if current_size == last_size and current_size > 0:
                return True
            last_size = current_size
            time.sleep(1)
        except OSError:
            pass  # File might not exist yet
    return False

# Function to extract audio from uploaded video using ffmpeg
def extract_audio_from_video(video_path, output_audio="extracted_audio.mp3"):
    try:
        ffmpeg.input(video_path).output(output_audio).run(overwrite_output=True)
        return output_audio
    except Exception as e:
        st.error(f"Error extracting audio from video: {e}")
        return None

def is_valid_youtube_link(youtube_link):
    """Very basic check if the link seems like a YouTube link."""
    return "youtube.com" in youtube_link or "youtu.be" in youtube_link

# ------------------- Main Pages -------------------
def login_page():
    st.header("Login")
    username = st.text_input("Username")
    if st.button("Send OTP"):
        email = get_email(username)
        if email:
            otp = generate_otp()
            st.session_state.otp = otp
            st.session_state.username = username
            send_otp_email(email, otp)
            st.success(f"OTP sent to {email}")
        else:
            st.error("Username not found!")

    if "otp" in st.session_state:
        otp_input = st.text_input("Enter OTP sent to your email:")
        if st.button("Verify OTP"):
            if otp_input == st.session_state.otp:
                st.success("Login successful!")
                st.session_state.logged_in = True
                st.session_state.user_id = username
                del st.session_state.otp
            else:
                st.error("Invalid OTP. Please try again.")

def create_account_page():
    st.header("Create Account")
    username = st.text_input("New Username")
    password = st.text_input("New Password", type="password")
    confirm_password = st.text_input("Confirm Password", type="password")
    if st.button("Create Account"):
        if password == confirm_password:
            add_user(username, password)
        else:
            st.error("Passwords do not match.")

def forgot_password_page():
    st.header("Forgot Password")
    
    username = st.text_input("Username")
    email = st.text_input("Registered Email")  # Ask for the registered email
    
    if st.button("Send OTP"):
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user:
            if user[0] == email:
                otp = generate_otp()
                send_otp_email(email, otp)
                st.session_state.otp = otp
                st.session_state.username = username
                st.session_state.otp_sent = True
                st.success("OTP sent to your email. Please check your inbox.")
            else:
                st.error("The provided email does not match the registered email.")
        else:
            st.error("Username not found!")

    if st.session_state.get("otp_sent", False):
        otp_input = st.text_input("Enter OTP")
        new_password = st.text_input("Enter New Password", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")

        if st.button("Reset Password"):
            if otp_input == st.session_state.otp:
                if new_password == confirm_password:
                    update_password(st.session_state.username, new_password)
                    st.success("Your password has been reset successfully.")
                    del st.session_state.otp
                    del st.session_state.username
                    del st.session_state.otp_sent
                else:
                    st.error("Passwords do not match.")
            else:
                st.error("Invalid OTP. Please try again.")

def speech_to_speech_page():
    st.header("Speech-to-Speech Translation")
    input_method = st.radio("Input Method", ["Upload Audio", "Speak Now"])
    target_languages = st.multiselect("Select Target Languages", list(LANGUAGES.values()), default=["english"])

    output_placeholder = st.empty()

    if input_method == "Upload Audio":
        audio_file = st.file_uploader("Upload an audio file", type=["wav", "mp3"])
        if audio_file and st.button("Translate"):
            try:
                source_lang, recognized_text, translations, tts_files = process_speech_to_speech(audio_file, target_languages)
                if recognized_text:
                    st.write(f"**Recognized Speech:** {recognized_text}")
                    st.write(f"**Source Language:** {source_lang}")  # Display the source language
                    for lang, text in translations.items():
                        st.write(f"**{lang} Translation:** {text}")
                        st.audio(tts_files[lang])
                        save_translation(st.session_state.user_id, recognized_text, text, lang, source_lang,"Speech to Speech")
            except Exception as e:
                st.error(f"An error has occurred while processing file input: {e}")


    elif input_method == "Speak Now":
        if st.button("Start Listening", key="start_listening_button"):
            source_lang, recognized_text, translations, tts_files = process_speech_to_speech(None, target_languages, recording=True)
            if recognized_text:
                 st.write(f"**Recognized Speech:** {recognized_text}")
                 st.write(f"**Source Language:** {source_lang}")
                 for lang, text in translations.items():
                     st.write(f"**{lang} Translation:** {text}")
                     st.audio(tts_files[lang])

def text_to_speech(text, target_languages):
    """Generate speech from translated text."""
    tts_files = {}
    translator = Translator()

    # Translate text to each selected language
    for lang in target_languages:
        lang_code = get_language_code(lang)
        if lang_code:
            # Translate the input text to the target language
            translated_text = translator.translate(text, dest=lang_code).text
            # Convert the translated text to speech
            tts = gTTS(translated_text, lang=lang_code)
            tts_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            tts.save(tts_file.name)
            tts_files[lang] = tts_file.name
    return tts_files

# ------------------- Function to Save Translation -------------------

def save_translation(user_id, original_text, translated_text, target_language, source_language, translation_type):
    """Save translation history in the database (including speech, text, video, and image translations)."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    # Convert short codes to full language names
    full_target_language = LANGUAGES.get(target_language, target_language).capitalize()
    full_source_language = LANGUAGES.get(source_language, source_language).capitalize()

    cursor.execute("""
        INSERT INTO history (user_id, original_text, translated_text, target_language, source_language, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, original_text, translated_text, full_target_language, full_source_language, timestamp))

    conn.commit()
    conn.close()



def text_to_speech_page():
    st.header("Text-to-Speech Translation")

    # Input text area for text-to-speech conversion
    text = st.text_area("Enter Text to Convert into Speech:")

    # Select target languages for translation and speech
    target_languages = st.multiselect("Select Target Languages", list(LANGUAGES.values()), default=["english"])

    # Display the input text
    if text:
        st.write(f"**Input Text:** {text}")

    if st.button("Convert to Speech"):
        if text:
            # Detect source language using Google Translate
            translator = Translator()
            detected_lang = translator.detect(text).lang
            source_language_name = LANGUAGES.get(detected_lang, detected_lang)

            # Convert text to speech in selected languages
            tts_files = text_to_speech(text, target_languages)

            # Display the translated text and play the corresponding speech
            for lang, file in tts_files.items():
                translated_text = translator.translate(text, dest=get_language_code(lang)).text
                st.write(f"**{lang} Translation:** {translated_text}")  # Show the translated text
                st.audio(file)  # Play the audio for the translation

                # Save the translation history in the database
                save_translation(st.session_state.user_id, text, translated_text, lang, source_language_name,"Text to Speech")
        else:
            st.error("Please enter some text to convert to speech.")

def video_translation_page():
    st.header("YouTube Video & Upload Translator")

    # Radio buttons for video source
    video_source = st.radio(
        "Choose Video Source",
        options=["YouTube Link", "Upload Video"]
    )

    audio_path = None

    if video_source == "YouTube Link":
        youtube_link = st.text_input("Paste YouTube Video Link:")
        if youtube_link:
            if not is_valid_youtube_link(youtube_link):
                st.error("Invalid YouTube link format. Please provide a valid link.")
            else:
                try:
                    st.info("Downloading audio...")
                    audio_path = download_audio(youtube_link)
                    if audio_path is None:
                        st.error("Failed to download audio from YouTube link.")
                except Exception as e:
                    st.error(f"Error downloading audio: {e}")

    elif video_source == "Upload Video":
        video_file = st.file_uploader("Upload a Video", type=["mp4"])
        if video_file is not None:
            try:
                st.info("Converting Uploaded File to Audio...")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tfile:
                    tfile.write(video_file.read())
                    temp_video_path = tfile.name  # Store the temporary file path
                audio_path = extract_audio_from_video(temp_video_path)  # Convert local file instead
                if audio_path is None:
                    st.error("Failed to extract audio from uploaded video.")
            except Exception as e:
                st.error(f"Error processing uploaded video: {e}")

    # Multi-select for target languages
    target_languages = st.multiselect(
        "Select Target Languages:",
        list(LANGUAGES.values())  # Display full language names
    )

    # Checkbox to include original audio
    include_original_audio = st.checkbox("Include Original Audio", value=True)

    if st.button("Translate Video"):
        if audio_path:
            try:
                st.info("Transcribing audio...")
                transcribed_text = transcribe_audio(audio_path)

                if transcribed_text:
                    st.text_area("Original Text:", transcribed_text)

                    # ✅ Detect source language correctly
                    detected_lang = Translator().detect(transcribed_text).lang
                    source_language = LANGUAGES.get(detected_lang, detected_lang).capitalize()

                    # ✅ Show and allow downloading of the original audio
                    if include_original_audio:
                        st.info("🔊 Playing Original Audio:")
                        st.audio(audio_path, format="audio/mp3")

                        st.download_button(
                            label="📥 Download Original Audio",
                            data=open(audio_path, "rb").read(),
                            file_name="original_audio.mp3",
                            mime="audio/mp3",
                        )

                    # ✅ Translate and generate speech for each target language
                    for language_name in target_languages:
                        language_code = next((code for code, name in LANGUAGES.items() if name == language_name), None)

                        if language_code:
                            st.info(f"Translating to {language_name}...")
                            translated_text = translate_text(transcribed_text, language_code)

                            if translated_text:
                                st.text_area(f"Translated Text ({language_name}):", translated_text)

                                st.info(f"Generating translated speech for {language_name}...")
                                translated_audio = generate_translated_speech(
                                    translated_text, language_code, output_audio=f"translated_audio_{language_code}.mp3"
                                )

                                if translated_audio:
                                    st.audio(translated_audio, format="audio/mp3")
                                    st.download_button(
                                        label=f"📥 Download Translated Audio ({language_name})",
                                        data=open(translated_audio, "rb").read(),
                                        file_name=f"translated_audio_{language_code}.mp3",
                                        mime="audio/mp3",
                                    )

                                    # ✅ Save translation to history with full language names
                                    save_translation(
                                        st.session_state.user_id, 
                                        transcribed_text, 
                                        translated_text, 
                                        language_code, 
                                        source_language,  # No more "Original"
                                        "video"
                                    )

                            else:
                                st.error(f"Translation to {language_name} failed.")
                        else:
                            st.error(f"Could not find language code for {language_name}")

                else:
                    st.error("Transcription failed")

            except Exception as e:
                st.error(f"Error during translation process: {e}")

        else:
            st.warning("Please enter a valid YouTube link or upload a video.")

def history_page():
    st.header("Translation History")
    conn = sqlite3.connect(DATABASE_FILE)
    
    history_df = pd.read_sql(
        "SELECT original_text, translated_text, target_language, source_language, timestamp FROM history WHERE user_id = ?",
        conn,
        params=(st.session_state.user_id,)
    )

    # Convert short language codes to full names
    history_df["target_language"] = history_df["target_language"].map(lambda x: LANGUAGES.get(x, x).capitalize())
    history_df["source_language"] = history_df["source_language"].map(lambda x: LANGUAGES.get(x, x).capitalize())

    st.dataframe(history_df)  

    if st.button("Clear History"):
        cursor = conn.cursor()
        cursor.execute("DELETE FROM history WHERE user_id = ?", (st.session_state.user_id,))
        conn.commit()
        st.success("History cleared.")
    conn.close()


def visualization_page():
    st.header("Language Usage Statistics")
    conn = sqlite3.connect(DATABASE_FILE)

    # Fetch history and convert short codes to full names
    history_df = pd.read_sql("SELECT target_language FROM history WHERE user_id = ?", conn, params=(st.session_state.user_id,))
    history_df["target_language"] = history_df["target_language"].map(lambda x: LANGUAGES.get(x, x).capitalize())

    # Aggregate counts correctly
    language_counts = history_df["target_language"].value_counts()

    st.bar_chart(language_counts)
    conn.close()

def logout():
    st.session_state.logged_in = False
    st.success("Logged out successfully!")
    st.rerun()

def main_app():
    st.title("Real-time Translator Tool")

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "login_success" not in st.session_state:
        st.session_state.login_success = False  # Flag for success message

    if not st.session_state.logged_in:
        auth_choice = st.sidebar.radio("Choose an option", ["Login", "Create Account", "Forgot Password"])

        if auth_choice == "Login":
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                user_id = verify_user(username, password)
                if user_id:
                    st.session_state.logged_in = True
                    st.session_state.user_id = user_id
                    st.session_state.login_success = True  # Set the flag for success message
                    st.rerun()  # Force the app to reload
                else:
                    st.error("Invalid username or password.")

        elif auth_choice == "Create Account":
            new_username = st.text_input("New Username")
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            new_email = st.text_input("Email")
            if st.button("Create Account"):
                if new_password == confirm_password:
                    if get_user(new_username):
                        st.error("Username already exists!")
                    else:
                        add_user(new_username, new_password, new_email)
                        st.success("Account created successfully!")
                else:
                    st.error("Passwords do not match.")

        elif auth_choice == "Forgot Password":
            forgot_password_page()
            st.stop()

    else:
        # Show success message after login
        if st.session_state.login_success:
            st.success("You have logged in successfully!")
            st.session_state.login_success = False  # Reset the flag after showing the message

        # Show the sidebar and pages only if the user is logged in
        st.sidebar.title("Options")
        page = st.sidebar.radio("Go to", [
            "Speech-to-Speech", "Text-to-Speech", "Image/Document Translation",
            "Video Translation", "History", "Visualization", "Logout"
        ])

        if page == "Logout":
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.success("You have logged out successfully!")
            time.sleep(1)
            st.rerun()

        elif page == "Speech-to-Speech":
            speech_to_speech_page()

        elif page == "Text-to-Speech":
            text_to_speech_page()

        elif page == "Image/Document Translation":
            uploaded_files = st.file_uploader(
                "Upload Images or PDFs", type=["png", "jpg", "jpeg", "pdf"], accept_multiple_files=True
            )
            target_languages = st.multiselect("Select Target Languages", languages, format_func=lambda x: LANGUAGES[x])

            if uploaded_files and target_languages:
                for uploaded_file in uploaded_files:
                    if uploaded_file.type.startswith("image"):
                        image = Image.open(uploaded_file)
                        st.image(image, caption=f"Original Image - {uploaded_file.name}")

                        # Extract text from image
                        extracted_text = pytesseract.image_to_string(image).strip()

                        if extracted_text:
                            # Detect source language
                            detected_lang = Translator().detect(extracted_text).lang
                            source_language = LANGUAGES.get(detected_lang, detected_lang).capitalize()

                            for target_language in target_languages:
                                translated_text = translate_image(image, target_language)
                                if translated_text:
                                    st.write(f"**Translation to {LANGUAGES[target_language]}:**")
                                    st.write(translated_text)

                                    # ✅ Save translation to history
                                    save_translation(
                                        st.session_state.user_id, 
                                        extracted_text, 
                                        translated_text, 
                                        target_language, 
                                        source_language, 
                                        "image"
                                    )

                    elif uploaded_file.type == "application/pdf":
                        try:
                            doc = fitz.open(stream=uploaded_file.read())
                            document_text = ""

                            for page in doc:
                                document_text += page.get_text("text") + "\n"

                            if document_text.strip():
                                # Detect source language
                                detected_lang = Translator().detect(document_text).lang
                                source_language = LANGUAGES.get(detected_lang, detected_lang).capitalize()

                                for target_language in target_languages:
                                    translated_doc = translate_document(doc, target_language)
                                    if translated_doc:
                                        st.write(f"**Translation to {LANGUAGES[target_language]}:**")
                                        st.write(translated_doc)

                                        # ✅ Save translation to history
                                        save_translation(
                                            st.session_state.user_id, 
                                            document_text, 
                                            translated_doc, 
                                            target_language, 
                                            source_language, 
                                            "document"
                                        )

                                        # ✅ Allow download of translated document
                                        st.download_button(
                                            label=f"📥 Download Translated Text ({LANGUAGES[target_language]})",
                                            data=translated_doc.encode(),
                                            file_name=f"translated_{uploaded_file.name}_{target_language}.txt",
                                            mime="text/plain",
                                        )
                        except Exception as e:
                            st.error(f"Error processing PDF: {e}")

        elif page == "Video Translation":
            video_translation_page()

        elif page == "History":
            history_page()

        elif page == "Visualization":
            visualization_page()


# ------------------- Run the App -------------------
if __name__ == "__main__":
    setup_database()  # Set up the database before running the app
    main_app()