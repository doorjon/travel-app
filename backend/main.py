import os
import pycountry
import traceback
import re
from countryinfo import CountryInfo
from geopy.geocoders import Nominatim
from mistralai import Mistral
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

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
    arrivalDate: str  # YYYY-MM-DD

class ItineraryResponse(BaseModel):
    itinerary: str

MISTRAL_KEY = os.getenv("MISTRAL_API_KEY")
if not MISTRAL_KEY:
    raise RuntimeError("MISTRAL_API_KEY not found in env vars")
client = Mistral(api_key=MISTRAL_KEY)

SYSTEM_PROMPT = """You are an experienced travel planner.

Your output must follow this exact structure:

1. Climate Summary  
2. Day-by-Day Itinerary  
3. Packing List

Each section should be clearly labeled.  

- Use bullet points for each day's itinerary.
- Each day's heading should start with the city name only (e.g., "Day 3: Tokyo"), not phrases like "Arrival in Tokyo".
- Include practical tips (transport, best neighbourhoods, local dishes).
- Packing list should be a single list covering the entire trip, based on the climate and activities.
- Do not include a packing list per day.
- Be friendly and concise."""



def build_user_prompt(country: str, days: int, interests: List[str], climate: str) -> str:
    interests_str = ", ".join(interests) if interests else "general sightseeing"
    return (
        f"Plan a {days}-day trip to {country} for someone interested in {interests_str}.\n"
        f"The expected climate during the trip is: {climate}.\n"
        f"Provide a day-by-day itinerary with activities, travel tips, and highlights.\n"
        f"At the end, include a single, comprehensive packing list that covers the entire trip based on the climate and activities.\n"
        f"Do not include a packing list per day."
    )


@app.post("/generate-itinerary", response_model=ItineraryResponse)
async def generate_itinerary(req: ItineraryRequest):
    try:
        # STEP 1: Generate initial itinerary without climate info
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(req.country, req.days, req.interests, "No climate data yet.")},
        ]

        response = client.chat.complete(
            model="mistral-tiny",
            messages=messages,
            temperature=0.5,
            max_tokens=1800,
        )

        initial_itinerary = response.choices[0].message.content.strip()

        # STEP 2: Extract cities and get detailed climate summary
        climate_summary = await build_citywise_climate_summary(initial_itinerary, req.country, req.arrivalDate)
        print("City-specific climate summary:", climate_summary)

        # STEP 3: Regenerate itinerary with real climate data
        final_prompt = build_user_prompt(req.country, req.days, req.interests, climate_summary)

        final_response = client.chat.complete(
            model="mistral-tiny",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": final_prompt},
            ],
            temperature=0.5,
            max_tokens=1800,
        )

        final_itinerary = final_response.choices[0].message.content.strip()
        return ItineraryResponse(itinerary=final_itinerary)

    except Exception as e:
        print("Backend error:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


geolocator = Nominatim(user_agent="travel-app")

def extract_cities(itinerary_text: str, country: str) -> List[str]:
    pattern = re.compile(r'Day \d+: (.*?)\n', re.IGNORECASE)
    matches = pattern.findall(itinerary_text)
    cities = []

    for match in matches:
        # Remove leading phrases like "Arrival in", "Transfer to", "Depart from"
        cleaned = re.sub(r'^(Arrival in|Transfer to|Depart(?:ure)? from|Drive to|Fly to|Travel to)\s+', '', match, flags=re.IGNORECASE)

        # Handle possible comma-separated details
        if ',' in cleaned:
            cleaned = cleaned.split(',')[0]

        city = cleaned.strip()
        if city and city.lower() != country.lower():
            cities.append(city)

    return list(set(cities))


def get_city_coords(city: str, country: str):
    try:
        location = geolocator.geocode(f"{city}, {country}")
        if location:
            return {"city": city, "lat": location.latitude, "lon": location.longitude}
    except Exception as e:
        print(f"Failed to get location for {city}, {country}: {e}")
    return None

async def get_city_climate(lat: float, lon: float, arrivalDate: str) -> str:
    import datetime
    import httpx

    try:
        date_obj = datetime.datetime.strptime(arrivalDate, "%Y-%m-%d")
        end_date = date_obj + datetime.timedelta(days=6)
        start_date_str = f"2022-{date_obj.month:02d}-{date_obj.day:02d}"
        end_date_str = f"2022-{end_date.month:02d}-{end_date.day:02d}"

        url = (
            f"https://historical-forecast-api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&start_date={start_date_str}&end_date={end_date_str}"
            f"&hourly=temperature_2m,precipitation"
            f"&temperature_unit=celsius&precipitation_unit=mm"
        )

        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()

        temps = data.get("hourly", {}).get("temperature_2m", [])
        rain = data.get("hourly", {}).get("precipitation", [])
        if temps and rain:
            avg_temp = sum(temps) / len(temps)
            total_rain = sum(rain)
            return f"Avg temp: {avg_temp:.1f}°C, Rainfall: {total_rain:.1f} mm"

    except Exception as e:
        print(f"Error fetching weather for city: {e}")

    return "Climate data unavailable"

async def build_citywise_climate_summary(itinerary_text: str, country: str, arrivalDate: str):
    cities = extract_cities(itinerary_text, country)
    summaries = []

    for city in cities:
        coords = get_city_coords(city, country)
        if coords:
            climate = await get_city_climate(coords['lat'], coords['lon'], arrivalDate)
            summaries.append(f"{city}: {climate}")
        else:
            summaries.append(f"{city}: Climate data unavailable")

    return "\n".join(summaries)
