import os
import pycountry
import traceback
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
Create a day-by-day itinerary for the given country and number of days.
The traveller is interested in: {interests}.
Return only the itinerary, no extra commentary.
Use bullet points for each day and include practical tips (transport, best neighbourhoods, local dishes to try). Do not include a packing list for each location.
At the beginning of the itinerary, include a short summary of the expected climate during the trip.
At the end of the itinerary, include a single, comprehensive packing list covering the entire trip, based on the climate and activities. Assume that the user wants to pack as light as possible.
Keep the tone friendly and concise."""


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
        climate = await get_climate_info(req.country, req.arrivalDate)
        print("Climate info passed to LLM:", climate)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(req.country, req.days, req.interests, climate)},
        ]

        response = client.chat.complete(
            model="mistral-tiny",
            messages=messages,
            temperature=0.5,
            max_tokens=1800,
        )

        itinerary = response.choices[0].message.content.strip()
        return ItineraryResponse(itinerary=itinerary)
    except Exception as e:
        print("Backend error:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


geolocator = Nominatim(user_agent="travel-app")

def get_country_coords(country_name: str):
    try:
        country = pycountry.countries.lookup(country_name)
        ci = CountryInfo(country.name)

        capital = ci.capital()
        latlon = ci.info().get("latlng")

        if latlon and len(latlon) == 2:
            return {"lat": latlon[0], "lon": latlon[1], "capital": capital}

        location = geolocator.geocode(f"{capital}, {country.name}")
        if location:
            return {"lat": location.latitude, "lon": location.longitude, "capital": capital}

    except Exception as e:
        print(f"Error finding coordinates for {country_name}: {e}")
        return None

async def get_climate_info(country: str, arrivalDate: str) -> str:
    import datetime, httpx

    coords = get_country_coords(country)
    if not coords:
        return "Climate data unavailable"

    date_obj = datetime.datetime.strptime(arrivalDate, "%Y-%m-%d")
    year_month = date_obj.strftime("%Y-%m")
    month_index = date_obj.month  # 1–12

    url = (
        f"https://climate-api.open-meteo.com/v1/climate?"
        f"latitude={coords['lat']}&longitude={coords['lon']}"
        f"&monthly_temperature_2m_mean=true&monthly_precipitation_sum=true"
    )

    async with httpx.AsyncClient() as client:
        r = await client.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()

    print("🌦 Open-Meteo response:", data)

    monthly = data.get("monthly")
    if monthly:
        tavg_list = monthly.get("temperature_2m_mean", [])
        rain_list = monthly.get("precipitation_sum", [])
        if tavg_list and rain_list and len(tavg_list) >= month_index and len(rain_list) >= month_index:
            tavg = tavg_list[month_index - 1]
            rain = rain_list[month_index - 1]
            return f"{coords['capital']} climate in {year_month}: Avg temp {tavg:.1f}°C, {rain:.1f} mm rain"

    # fallback
    return get_generic_climate(country, month_index)

def get_generic_climate(country_name: str, month: int) -> str:
    if month in [12, 1, 2]:
        season = "winter"
    elif month in [3, 4, 5]:
        season = "spring"
    elif month in [6, 7, 8]:
        season = "summer"
    else:
        season = "autumn"
    return f"Generally {season} conditions, with moderate temperatures and occasional rainfall."
