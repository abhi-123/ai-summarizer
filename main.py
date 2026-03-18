from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager

from openai import OpenAI
import os
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
import re

# 🔑 Load env variables
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

# ✅ CORS (React/JS connect ke liye)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📥 Request body
class RequestData(BaseModel):
    url: str


# 🌐 Scraper function
def scrape_website(url):
    driver = None
    try:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-images")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")

        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )

        wait = WebDriverWait(driver, 20)

        driver.get(url)

        # ✅ Smart wait
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")

        title = soup.title.string.strip() if soup.title else "No title"

        if soup.body:
            for tag in soup(["script", "style", "img", "input", "noscript"]):
                tag.decompose()

            text = soup.body.get_text(separator="\n", strip=True)
        else:
            text = ""

        return (title + "\n\n" + text)[:3000]

    except Exception as e:
        return f"Error scraping: {e}"

    finally:
        if driver:
            driver.quit()
def extract_video_id(url):
    match = re.search(r"(?:v=|youtu\.be/)([^&\n?#]+)", url)
    return match.group(1) if match else None

def get_youtube_transcript(url):
    try:
        # video id extract
        video_id = extract_video_id(url)

        if not video_id:
         return "Invalid YouTube URL ❌"

        # 🔥 IMPORTANT FIX
        transcript = YouTubeTranscriptApi().fetch(video_id,languages=['en', 'hi', 'fr', 'es'])

        text = " ".join([item.text for item in transcript])

        return text[:3000]

    except Exception as e:
        return f"Error fetching transcript: {e}"


# 🤖 AI summary function
def summarize_text(text):
    try:
        print("🔥 OpenAI API called")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Summarize in bullet points, clean headings, avoid repetition, keep it concise and conver the content in english if not , and also i am using python selenium for scrapping, if you dont get the desired result please tell user that website summary cannot be given as something is missing like url is invalid or something .if error found please tell the user in a non technical way or in layman language"},
                {"role": "user", "content": text}
            ]
        )
        usage = response.usage

        print("📊 Tokens used:")
        print("Prompt:", usage.prompt_tokens)
        print("Completion:", usage.completion_tokens)
        print("Total:", usage.total_tokens)

        print("✅ Response received")

        return response.choices[0].message.content

    except Exception as e:
        return f"Error in AI: {e}"


# 🔗 API endpoint
@app.post("/summarize")
def summarize(data: RequestData):
    url = data.url

    # 🔥 YouTube handling
    if "youtube.com" in url or "youtu.be" in url:
        content = get_youtube_transcript(url)
    else:
        content = scrape_website(url)

    summary = summarize_text(content)

    return {
        "summary": summary
    }