import os
from mistralai import Mistral
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from mistralai.client import MistralClient

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ItineraryRequest(BaseModel):
    country: str
    days: int
    interests: List[str]

class ItineraryResponse(BaseModel):
    itinerary: str

MISTRAL_KEY = os.getenv("MISTRAL_API_KEY")
if not MISTRAL_KEY:
    raise RuntimeError("MISTRAL_API_KEY not found in env vars")
client = Mistral(api_key=MISTRAL_KEY)

SYSTEM_PROMPT = """You are an experienced travel planner.
Create a day-by-day itinerary for the given country and number of days.
The traveller is interested in: {interests}.
Return only the itinerary, no extra commentary.
Use bullet points for each day and include practical tips (transport, best neighbourhoods, local dishes to try).
Keep the tone friendly and concise."""

def build_user_prompt(country: str, days: int, interests: List[str]) -> str:
    interests_str = ", ".join(interests) if interests else "general sightseeing"
    return f"{days} days in {country}. Interests: {interests_str}."

@app.post("/generate-itinerary", response_model=ItineraryResponse)
async def generate_itinerary(req: ItineraryRequest):
    try:
        messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": build_user_prompt(req.country, req.days, req.interests)}
]
        response = client.chat.complete(          # <- add .complete
            model="mistral-tiny",
            messages=messages,
            temperature=0.7,
            max_tokens=1200
        )
        itinerary = response.choices[0].message.content.strip()
        return ItineraryResponse(itinerary=itinerary)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))